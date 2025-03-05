import salabim as sim
import logging
from threading import Lock

logger = logging.getLogger(__name__)

class BaseLadleCar(sim.Component):
    def __init__(self, env, car_id, car_type, home_bay, speed=150, spatial_manager=None, on_idle_callback=None, name=None, **kwargs):
        """
        Initialize a base ladle car.

        Args:
            env: Salabim simulation environment.
            car_id: Unique identifier for the car.
            car_type: Type of ladle car ("tapping", "treatment", "rh").
            home_bay: Starting bay location.
            speed: Movement speed in units per minute (default: 150).
            spatial_manager: SpatialManager instance for pathfinding and positioning.
            on_idle_callback: Callback function to trigger when the car becomes idle.
            name: Custom name for the car (optional).
        """
        # Validate car_type
        valid_types = ["tapping", "treatment", "rh"]
        if car_type.lower() not in valid_types:
            raise ValueError(f"Invalid car_type '{car_type}'. Must be one of {valid_types}")
        
        # Input validation    
        if not isinstance(car_id, (int, str)):
            raise TypeError(f"car_id must be int or str, got {type(car_id)}")
        if not isinstance(home_bay, str):
            raise TypeError(f"home_bay must be str, got {type(home_bay)}")
        if not speed > 0:
            raise ValueError(f"speed must be positive, got {speed}")
            
        super().__init__(env=env, name=name or f"{car_type.capitalize()}Car_{car_id}", **kwargs)
        self.car_id = car_id
        self.car_type = car_type.lower()
        self.home_bay = home_bay
        self.speed = speed
        self.spatial_manager = spatial_manager
        self.on_idle_callback = on_idle_callback
        
        # Store the string state explicitly to handle Salabim's State.value returning a Monitor
        self._status_string = "idle"
        
        # Create the State object for Salabim but access via our property/methods
        self._car_status_state = sim.State("car_status", value=self._status_string, env=env)
        
        self.current_bay = home_bay
        
        # Initialize position with error handling
        try:
            self.position = spatial_manager.get_bay_position(home_bay) if spatial_manager else {"x": 0, "y": 0}
        except (AttributeError, KeyError, TypeError) as e:
            logger.error(f"Error getting bay position for {home_bay}: {e}", exc_info=True)
            self.position = {"x": 0, "y": 0}
            
        self.current_heat = None
        self.current_ladle = None
        self.destination = None
        self.path = []
        self.move_queue = []  # Ensure move_queue is initialized
        self.current_path_segment = 0
        self.total_distance_traveled = 0.0
        
        # Thread safety and error recovery
        self.status_lock = Lock()
        self.last_status_time = 0
        self.error_count = 0
        self.deadlock_timeout = 15  # minutes
        
        # Performance metrics
        self.task_count = 0
        self.movement_times = []
        self.waiting_times = []
        
        self.activate()
        logger.info(f"{self.name()} initialized at {home_bay}", extra={
            "component": "ladle_car",
            "car_id": car_id,
            "car_type": car_type,
            "bay": home_bay,
            "position": self.position
        })

    # Property to access car_status with an adapter to handle Salabim's behavior
    @property
    def car_status(self):
        """Get the car's status State object."""
        return self._car_status_state
    
    # Disable direct assignment to car_status
    @car_status.setter
    def car_status(self, value):
        """Prevent direct assignment to car_status."""
        logger.error(f"Attempted direct assignment to car_status on {self.name()}. Use set_status() instead.")
        raise AttributeError("Use set_status() method to modify car status")

    # Helper method to get the actual status string safely
    def get_status_string(self):
        """
        Get the current status as a string, safely handling Salabim's Monitor objects.
        
        Returns:
            str: Current status string
        """
        # Return our explicitly tracked status string
        return self._status_string

    def set_status(self, new_status):
        """
        Set the ladle car's status and trigger callback if idle.

        Args:
            new_status (str): New status ("idle", "moving", "loading", "unloading").
            
        Returns:
            bool: True if successful, False otherwise
        """
        # Enhanced validation with type checking
        if not isinstance(new_status, str):
            logger.error(f"Invalid status type for {self.name()}: {type(new_status)}. Expected string.",
                        extra={"component": "ladle_car", "car_id": self.car_id})
            return False
            
        valid_statuses = ["idle", "moving", "loading", "unloading", "error"]
        if new_status not in valid_statuses:
            logger.warning(f"Invalid status '{new_status}' for {self.name()}; ignoring",
                          extra={"component": "ladle_car", "car_id": self.car_id})
            return False
        
        # Thread-safe status update
        with self.status_lock:
            # Only update if status has changed
            if new_status != self._status_string:
                logger.debug(f"{self.name()} status changing from {self._status_string} to {new_status}",
                            extra={"component": "ladle_car", "car_id": self.car_id, 
                                  "old_status": self._status_string, "new_status": new_status})
                
                # Update both our internal string and the Salabim State
                self._status_string = new_status
                self._car_status_state.set(new_status)
                self.last_status_time = self.env.now()
                
                if new_status == "idle" and callable(self.on_idle_callback):
                    try:
                        logger.info(f"{self.name()} is idle, triggering callback",
                                   extra={"component": "ladle_car", "car_id": self.car_id})
                        self.on_idle_callback()
                    except Exception as e:
                        logger.error(f"Error in on_idle_callback for {self.name()}: {e}", exc_info=True)
                        self.error_count += 1
                        return False
        return True

    def process(self):
        """
        Main process loop for the ladle car.

        Manages states:
        - idle: Wait for tasks.
        - moving: Travel along the assigned path.
        - loading: Acquire heat using a crane.
        - unloading: Deliver heat to the destination unit using a crane.
        """
        while True:
            try:
                current_time = self.env.now()
                # Get current status with our safe method
                current_status = self.get_status_string()
                
                # Deadlock detection
                if current_status != "idle" and current_time - self.last_status_time > self.deadlock_timeout:
                    logger.warning(f"Potential deadlock: {self.name()} stuck in {current_status} for {current_time - self.last_status_time} min",
                                  extra={"component": "ladle_car", "car_id": self.car_id, "status": current_status})

                if current_status == "idle":
                    # Wait for a task assignment; callback may trigger new tasks
                    if callable(self.on_idle_callback):
                        try:
                            self.on_idle_callback()
                        except Exception as e:
                            logger.error(f"Idle callback failed for {self.name()}: {e}", exc_info=True)
                            self.error_count += 1
                    yield self.hold(1)  # Minimal wait to avoid tight looping

                elif current_status == "moving":
                    try:
                        # Path validation
                        if not self.path or self.current_path_segment >= len(self.path):
                            logger.warning(f"{self.name()} in 'moving' state with invalid path; resetting to idle",
                                          extra={"component": "ladle_car", "car_id": self.car_id})
                            self.set_status("idle")
                            self.path = []
                            self.current_path_segment = 0
                            self.destination = None
                            continue

                        segment = self.path[self.current_path_segment]
                        travel_time = segment.get("travel_time", 0)
                        to_point = segment.get("to", {"x": 0, "y": 0})

                        # Validate travel time
                        if travel_time <= 0:
                            logger.warning(f"Invalid travel time {travel_time} for segment; using default 1 unit", 
                                          extra={"component": "ladle_car", "car_id": self.car_id})
                            travel_time = 1

                        # Calculate distance for this segment
                        try:
                            from_x = float(self.position.get('x', 0))
                            from_y = float(self.position.get('y', 0))
                            to_x = float(to_point.get('x', 0))
                            to_y = float(to_point.get('y', 0))
                            distance = ((from_x - to_x)**2 + (from_y - to_y)**2)**0.5
                            self.total_distance_traveled += distance
                        except (ValueError, TypeError, AttributeError) as e:
                            logger.error(f"Error calculating distance for {self.name()}: {e}", exc_info=True)
                            distance = 10  # Default fallback
                            
                        # Record movement metrics
                        start_time = self.env.now()

                        logger.info(f"{self.name()} moving from ({self.position.get('x', 0)}, {self.position.get('y', 0)}) "
                                   f"to ({to_point.get('x', 0)}, {to_point.get('y', 0)}), ETA: {travel_time:.1f} min",
                                   extra={"component": "ladle_car", "car_id": self.car_id, 
                                          "from": self.position, "to": to_point, "eta": travel_time})
                        yield self.hold(travel_time)
                        
                        # Add to movement time records
                        actual_time = self.env.now() - start_time
                        self.movement_times.append(actual_time)

                        # Update position and path progress atomically
                        with self.status_lock:
                            self.position = to_point
                            self.current_path_segment += 1
                            self.last_status_time = self.env.now()

                        # Update heat temperature if carrying one
                        if self.current_heat:
                            try:
                                self.current_heat.update_temperature(self.env.now())
                            except AttributeError as e:
                                logger.warning(f"Heat {self.current_heat.id} lacks update_temperature method: {e}", 
                                              extra={"component": "ladle_car", "heat_id": self.current_heat.id})
                            except Exception as e:
                                logger.error(f"Error updating heat temperature: {e}", exc_info=True)

                        # Check if journey is complete
                        if self.current_path_segment >= len(self.path):
                            if self.destination:
                                self.current_bay = self.destination.get("bay", self.current_bay)
                                self.set_status("unloading" if self.current_heat else "idle")
                                if not self.current_heat:
                                    self.destination = None
                                    self.path = []
                                    self.current_path_segment = 0
                            else:
                                logger.error(f"{self.name()} completed path but has no destination", 
                                           extra={"component": "ladle_car", "car_id": self.car_id})
                                self.set_status("idle")
                    except Exception as e:
                        logger.error(f"Error during movement for {self.name()}: {e}", exc_info=True)
                        self.error_count += 1
                        self.set_status("error")
                        yield self.hold(3)  # Wait before resetting
                        self.set_status("idle")

                elif current_status == "loading":
                    try:
                        # Validate current bay
                        if not self.current_bay:
                            raise ValueError(f"No current bay defined for {self.name()}")
                            
                        waiting_start = self.env.now()
                        crane = self._request_crane(self.current_bay, "loading")
                        if crane:
                            load_time = crane.assign_task(source="unit", destination=f"{self.name()}")
                            
                            # Monitor wait time
                            wait_time = self.env.now() - waiting_start
                            if wait_time > 0:
                                self.waiting_times.append(wait_time)
                                
                            logger.info(f"{self.name()} loading heat {self.current_heat.id if self.current_heat else 'None'} with crane, "
                                       f"time: {load_time:.1f} min", 
                                       extra={"component": "ladle_car", "car_id": self.car_id, 
                                              "heat_id": self.current_heat.id if self.current_heat else None,
                                              "crane": crane.name(), "load_time": load_time})
                            yield self.hold(load_time)
                            
                            # Transition to moving state
                            with self.status_lock:
                                self.set_status("moving")
                                self.last_status_time = self.env.now()
                        else:
                            logger.debug(f"{self.name()} waiting for crane in bay {self.current_bay}",
                                        extra={"component": "ladle_car", "car_id": self.car_id, "bay": self.current_bay})
                            yield self.hold(1)  # Wait and retry
                    except (ValueError, TypeError, AttributeError) as e:
                        logger.error(f"Error during loading for {self.name()}: {e}", exc_info=True)
                        self.error_count += 1
                        self.set_status("error")
                        yield self.hold(3)  # Wait before resetting
                        self.set_status("idle")

                elif current_status == "unloading":
                    try:
                        # Validate current bay
                        if not self.current_bay:
                            raise ValueError(f"No current bay defined for {self.name()}")
                            
                        waiting_start = self.env.now()
                        crane = self._request_crane(self.current_bay, "unloading")
                        if crane:
                            # Validate destination
                            target_unit = self.destination.get("unit") if self.destination else None
                            if not target_unit:
                                raise ValueError(f"{self.name()} has missing destination unit")
                                
                            if not hasattr(target_unit, "add_heat"):
                                raise AttributeError(f"Destination unit {target_unit.name()} lacks add_heat method")

                            unload_time = crane.assign_task(source=f"{self.name()}", destination="unit")
                            
                            # Monitor wait time
                            wait_time = self.env.now() - waiting_start
                            if wait_time > 0:
                                self.waiting_times.append(wait_time)
                                
                            logger.info(f"{self.name()} unloading heat {self.current_heat.id if self.current_heat else 'None'} with crane, "
                                       f"time: {unload_time:.1f} min",
                                       extra={"component": "ladle_car", "car_id": self.car_id, 
                                              "heat_id": self.current_heat.id if self.current_heat else None,
                                              "crane": crane.name(), "unload_time": unload_time})
                            yield self.hold(unload_time)

                            # Transfer heat to the target unit
                            try:
                                success = target_unit.add_heat(self.current_heat)
                                if success:
                                    logger.info(f"Heat {self.current_heat.id} transferred to {target_unit.name()}",
                                               extra={"component": "ladle_car", "heat_id": self.current_heat.id,
                                                      "destination_unit": target_unit.name()})
                                else:
                                    logger.warning(f"Failed to transfer heat {self.current_heat.id} to {target_unit.name()}",
                                                  extra={"component": "ladle_car", "heat_id": self.current_heat.id,
                                                         "destination_unit": target_unit.name()})
                            except Exception as e:
                                logger.error(f"Error transferring heat: {e}", exc_info=True)
                                self.error_count += 1
                                
                            # Reset regardless of heat transfer success
                            self.current_heat = None
                            self.destination = None
                            self.path = []
                            self.current_path_segment = 0
                            
                            # Transition to idle
                            with self.status_lock:
                                self.set_status("idle")
                                self.last_status_time = self.env.now()
                        else:
                            logger.debug(f"{self.name()} waiting for crane in bay {self.current_bay}",
                                        extra={"component": "ladle_car", "car_id": self.car_id, "bay": self.current_bay})
                            yield self.hold(1)  # Wait and retry
                    except (ValueError, TypeError, AttributeError) as e:
                        logger.error(f"Error during unloading for {self.name()}: {e}", exc_info=True)
                        self.error_count += 1
                        self.set_status("error")
                        yield self.hold(3)  # Wait before resetting
                        self.set_status("idle")
                        
                elif current_status == "error":
                    # Recovery from error state
                    logger.info(f"{self.name()} recovering from error state",
                               extra={"component": "ladle_car", "car_id": self.car_id})
                    yield self.hold(5)  # Wait 5 minutes before recovery
                    
                    # Reset to safe state
                    self.path = []
                    self.current_path_segment = 0
                    if self.current_bay != self.home_bay and self.spatial_manager:
                        try:
                            # Try to get a path back to home bay for recovery
                            self.path = self.spatial_manager.get_path(self.current_bay, self.home_bay, 
                                                                      car_type=self.car_type)
                            if self.path:
                                logger.info(f"{self.name()} returning to home bay {self.home_bay} for recovery",
                                          extra={"component": "ladle_car", "car_id": self.car_id})
                                self.set_status("moving")
                                continue
                        except Exception as e:
                            logger.error(f"Error getting recovery path: {e}", exc_info=True)
                    
                    # If we couldn't get a recovery path, reset to idle
                    self.set_status("idle")
                    
                else:
                    logger.warning(f"Unknown status '{current_status}' for {self.name()}; defaulting to idle",
                                  extra={"component": "ladle_car", "car_id": self.car_id})
                    self.set_status("idle")
                    yield self.hold(1)
            except Exception as e:
                logger.error(f"Error in {self.name()} process: {e}", exc_info=True)
                self.error_count += 1
                # Reset to a safe state
                self.set_status("idle")
                yield self.hold(1)

    def assign_heat(self, heat, destination):
        """
        Assign a heat to the ladle car for transportation.

        Args:
            heat: Heat object to transport.
            destination: Dict with target info (e.g., {"bay": "bay2", "unit": unit_object}).

        Returns:
            bool: True if assignment succeeds, False otherwise.
        """
        # Validate inputs
        if heat is None:
            logger.error(f"Cannot assign null heat to {self.name()}",
                        extra={"component": "ladle_car", "car_id": self.car_id})
            return False
            
        if not destination or not isinstance(destination, dict):
            logger.error(f"Invalid destination format for {self.name()}: {destination}",
                        extra={"component": "ladle_car", "car_id": self.car_id})
            return False
            
        if not destination.get("bay") or not destination.get("unit"):
            logger.error(f"Destination missing required keys for {self.name()}: {destination}",
                        extra={"component": "ladle_car", "car_id": self.car_id})
            return False
        
        # Thread-safe status check and assignment
        with self.status_lock:
            # Check availability using our safe status method
            if self.get_status_string() != "idle":
                logger.warning(f"{self.name()} busy (status: {self.get_status_string()}), cannot assign heat {heat.id}",
                              extra={"component": "ladle_car", "car_id": self.car_id, 
                                     "status": self.get_status_string(), "heat_id": heat.id})
                return False
                
            # Proceed with assignment
            self.current_heat = heat
            self.destination = destination
            self.task_count += 1
            
        # Log assignment details
        from_bay = self.current_bay
        to_bay = destination.get("bay")
        
        logger.info(f"{self.name()} assigned heat {heat.id} (task #{self.task_count})",
                   extra={"component": "ladle_car", "car_id": self.car_id, 
                          "heat_id": heat.id, "from_bay": from_bay, "to_bay": to_bay})
        
        # Get path with error handling
        if not self.spatial_manager:
            logger.error(f"No spatial manager for {self.name()}; using fallback path",
                        extra={"component": "ladle_car", "car_id": self.car_id})
            self.path = [{"from": self.position, "to": self.position, "travel_time": 0}]
        else:
            try:
                self.path = self.spatial_manager.get_path(from_bay, to_bay, car_type=self.car_type)
                
                # Validate path
                if not self.path or not isinstance(self.path, list):
                    raise ValueError(f"Invalid path returned: {self.path}")
                    
                # Check each segment has required fields
                for i, seg in enumerate(self.path):
                    if not isinstance(seg, dict) or "travel_time" not in seg or "to" not in seg:
                        raise ValueError(f"Path segment {i} missing required fields: {seg}")
            except Exception as e:
                logger.error(f"Error getting path from {from_bay} to {to_bay} for {self.name()}: {e}",
                            extra={"component": "ladle_car", "car_id": self.car_id}, exc_info=True)
                self.current_heat = None
                self.destination = None
                return False
                
        self.current_path_segment = 0
        logger.info(f"{self.name()} assigned heat {heat.id} from {from_bay} to {to_bay}, path segments: {len(self.path)}",
                   extra={"component": "ladle_car", "car_id": self.car_id, 
                          "heat_id": heat.id, "path_segments": len(self.path)})
                          
        # Change status with timeout protection
        try:
            success = self.set_status("loading")
            if not success:
                raise ValueError(f"Failed to set status to loading for {self.name()}")
            return True
        except Exception as e:
            logger.error(f"Error setting status for {self.name()}: {e}", exc_info=True)
            self.current_heat = None
            self.destination = None
            self.path = []
            return False

    def is_available(self):
        """
        Check if the ladle car is available for a new task.

        Returns:
            bool: True if idle, False otherwise.
        """
        with self.status_lock:
            return self.get_status_string() == "idle"

    def _request_crane(self, bay, operation):
        """
        Request a crane in the specified bay for loading or unloading.

        Args:
            bay (str): Bay ID where the crane is needed.
            operation (str): "loading" or "unloading".

        Returns:
            Crane: Available crane object, or None if unavailable.
        """
        # Validate inputs
        if not bay:
            logger.error(f"Invalid bay for crane request: {bay}",
                        extra={"component": "ladle_car", "car_id": self.car_id})
            return None
            
        # Check transport manager exists
        if not hasattr(self.env, 'transport_manager') or not self.env.transport_manager:
            logger.error(f"TransportManager not initialized in environment for {self.name()}",
                        extra={"component": "ladle_car", "car_id": self.car_id})
            return None
            
        try:
            # Request crane from transport manager with proper error handling
            cranes = self.env.transport_manager.cranes.get(bay, [])
            if not cranes:
                logger.warning(f"No cranes registered in bay {bay} for {self.name()}",
                              extra={"component": "ladle_car", "car_id": self.car_id, "bay": bay})
                return None
                
            # Find available crane
            for crane in cranes:
                if not hasattr(crane, "is_available"):
                    logger.warning(f"Crane {crane.name()} lacks is_available method",
                                  extra={"component": "ladle_car", "crane": crane.name()})
                    continue
                    
                if crane.is_available():
                    logger.debug(f"{self.name()} assigned crane {crane.name()} for {operation} in bay {bay}",
                                extra={"component": "ladle_car", "car_id": self.car_id, 
                                       "crane": crane.name(), "operation": operation})
                    return crane
                    
            logger.info(f"No available cranes for {operation} in bay {bay} by {self.name()}",
                       extra={"component": "ladle_car", "car_id": self.car_id, 
                              "bay": bay, "operation": operation})
            return None
            
        except Exception as e:
            logger.error(f"Error requesting crane in {bay} for {self.name()}: {e}", exc_info=True)
            return None
            
    def get_metrics(self):
        """
        Get operational metrics for the ladle car.
        
        Returns:
            dict: Dictionary of metrics
        """
        return {
            "car_id": self.car_id,
            "car_type": self.car_type,
            "current_bay": self.current_bay,
            "status": self.get_status_string(),
            "task_count": self.task_count,
            "total_distance": self.total_distance_traveled,
            "error_count": self.error_count,
            "avg_movement_time": sum(self.movement_times) / len(self.movement_times) if self.movement_times else 0,
            "avg_waiting_time": sum(self.waiting_times) / len(self.waiting_times) if self.waiting_times else 0
        }