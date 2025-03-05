import salabim as sim
import logging
from collections import deque
from production_units.base_unit import BaseProductionUnit

logger = logging.getLogger(__name__)

class EnhancedLMFStation(BaseProductionUnit):
    """
    Ladle Metallurgy Furnace (LMF) station with enhanced logic.
    
    The LMF refines the steel chemistry and temperature. It can hold ladles
    in a queue to keep them warm, but must enforce minimum process times.
    """
    
    def __init__(self, env, bay, unit_id=0, name="LMF", 
                 process_time=30, min_process_time=30, capacity=1, **kwargs):
        """
        Initialize the LMF station.
        
        Args:
            env: Simulation environment
            bay: Bay identifier
            unit_id: Unit identifier
            name: Name of the LMF station
            process_time: Process time in minutes
            min_process_time: Minimum process time in minutes
            capacity: Capacity (number of ladles)
        """
        # Error handling for required parameters
        if env is None:
            raise ValueError("LMF initialization error: Simulation environment (env) is required")
        if not isinstance(bay, str):
            raise ValueError(f"LMF initialization error: Bay must be a string, got {type(bay)}")
        
        # Calculate position based on unit_id
        x_position = kwargs.get('x', 300)  # Default x position for LMF
        y_position = kwargs.get('y', 100) + (unit_id * 80)  # Vertical spacing
        
        # Call parent constructor with proper keyword arguments
        super().__init__(
            name=name,
            process_time=process_time, 
            capacity=capacity,
            env=env,
            x=x_position,
            y=y_position, 
            bay=bay,
            color=kwargs.get('color', 'blue'),  # LMF stations are typically blue
            **kwargs
        )
        
        self.unit_id = unit_id
        self.min_process_time = min_process_time
        self.active = True  # Unit is active by default
        
        # Queue for ladles to be processed - using deque for consistency with current implementation
        self.heat_queue = deque()
        
        # Queue for ladles being kept warm
        self.warming_queue = deque()
        
        # Maximum time to hold a ladle for warming
        try:
            if hasattr(env, 'config') and isinstance(env.config, dict):
                self.max_warming_time = env.config.get("ladle_warming_time", 15)
            else:
                self.max_warming_time = 15
        except Exception as e:
            logger.warning(f"Error accessing config, using default warming time: {e}")
            self.max_warming_time = 15
        
        # Downstream status tracking
        self.downstream_ready = True
        
        # Add a start_time attribute for process tracking
        self.start_time = None
        
        # Don't create a process object - instead, activate the component
        self.activate()
        
        logger.info(f"EnhancedLMFStation {unit_id} initialized in bay {bay}")
    
    def calculate_process_time(self, heat):
        """
        Calculate the appropriate process time for a heat based on grade and requirements.
        
        Args:
            heat: Heat object being processed
            
        Returns:
            float: Adjusted process time
        """
        # Start with default process time
        base_time = self.process_time
        
        # Apply grade-specific adjustments
        try:
            if heat.grade == "high_clean":
                # High clean grades need longer processing
                base_time += 15
            elif heat.grade == "decarb":
                # Decarburization requires additional processing
                base_time += 10
            elif heat.grade == "temp_sensitive":
                # Temperature sensitive grades need precise processing
                base_time += 5
                
            # Check for grade-specific properties
            if hasattr(heat, 'grade_specific_props'):
                if 'lmf_time' in heat.grade_specific_props:
                    base_time = heat.grade_specific_props['lmf_time']
        except Exception as e:
            logger.warning(f"Error calculating process time for heat {heat.id}, using default: {e}")
                
        # Apply minimum process time constraint
        return max(base_time, self.min_process_time)
    
    def is_available(self):
        return self.ispassive() or (self.state.value() == "idle" and len(self.heat_queue) < self.capacity * 2)
    
    def process(self):
        """Main processing loop for the LMF station."""
        while True:
            try:
                if not self.active:
                    yield self.env.timeout(1)
                    continue
                    
                # Check if we have a heat in the queue
                if self.heat_queue and self.is_available():
                    # Get the next heat from the queue
                    heat = self.heat_queue.popleft()
                    
                    # Start processing
                    self.status = "processing"
                    self.current_heat = heat
                    
                    # Calculate process time
                    process_time = self.calculate_process_time(heat)
                    
                    # Log start of processing
                    logger.info(f"{self.name} {self.unit_id} in bay {self.bay} started processing heat {heat.id}")
                    
                    # Record process start
                    self.start_time = self.env.now()
                    
                    # Process for the calculated time
                    yield self.env.timeout(process_time)
                    
                    # Record process in heat history
                    if hasattr(heat, 'record_process'):
                        heat.record_process("LMF", self.start_time, self.env.now(), self.bay)
                    
                    # Update heat temperature
                    if hasattr(heat, 'update_temperature'):
                        heat.update_temperature(self.env.now())
                    
                    # Check downstream availability
                    if not self.check_downstream_availability():
                        # Move to warming queue if downstream not ready
                        logger.info(f"Moving heat {heat.id} to warming queue - downstream not ready")
                        self.warming_queue.append({
                            "heat": heat,
                            "start_time": self.env.now()
                        })
                        
                        # Reset status
                        self.status = "idle"
                        self.current_heat = None
                    else:
                        # Finish processing normally
                        self.complete_heat(heat)
                
                # Check warming queue
                self._manage_warming_queue()
                
                # No work to do - wait
                if not self.heat_queue and not self.warming_queue:
                    self.status = "idle"
                    self.current_heat = None
                    yield self.env.timeout(1)
            except Exception as e:
                logger.error(f"Error in LMF {self.unit_id} process: {e}")
                # Continue operation despite error
                yield self.env.timeout(1)
    
    
    def _manage_warming_queue(self):
        """Manage ladles in the warming queue."""
        try:
            # Check if any ladles can be moved from warming queue
            if not self.warming_queue:
                return
                
            if self.downstream_ready:
                current_time = self.env.now()
                warm_ladle = self.warming_queue[0]
                
                if current_time - warm_ladle["start_time"] <= self.max_warming_time:
                    # Heat hasn't been warming too long - check temperature
                    heat = warm_ladle["heat"]
                    
                    # Update heat temperature
                    if hasattr(heat, 'update_temperature'):
                        heat.update_temperature(current_time)
                    
                    if getattr(heat, 'temperature', 1500) > 1480:
                        # Temperature is still good, move heat to next step
                        self.warming_queue.popleft()
                        self.complete_heat(heat)
                        logger.info(f"Heat {heat.id} moved from warming queue to next step, temp: {getattr(heat, 'temperature', 'N/A')}")
                else:
                    # Heat has been warming too long - must move along even if downstream is busy
                    warm_ladle = self.warming_queue.popleft()
                    heat = warm_ladle["heat"]
                    
                    # Update heat temperature
                    if hasattr(heat, 'update_temperature'):
                        heat.update_temperature(current_time)
                    
                    self.complete_heat(heat)
                    logger.warning(f"Heat {heat.id} moved from warming queue (max time reached), temp: {getattr(heat, 'temperature', 'N/A')}")
        except Exception as e:
            logger.error(f"Error managing warming queue in LMF {self.unit_id}: {e}")
    
    def check_downstream_availability(self):
        """
        Check if downstream equipment is available to receive a heat.
        
        In a real implementation, this would check with the route manager
        to see if the next step in the route has capacity.
        
        Returns:
            bool: True if downstream is ready to receive a heat
        """
        try:
            # Find the next equipment type for the current heat
            if self.current_heat:
                route_manager = getattr(self.env, "route_manager", None)
                if route_manager:
                    # Get current route for the heat
                    route_info = route_manager.heat_routes.get(self.current_heat.id, {})
                    route = route_info.get("route", [])
                    current_step = route_info.get("current_step", 0)
                    
                    # Find what's next after LMF
                    for i in range(current_step, len(route)):
                        if route[i][1] == "LMF":
                            # Found current step, check next
                            if i + 1 < len(route):
                                next_bay, next_type, next_unit = route[i + 1]
                                
                                # Check if next unit is available
                                if hasattr(next_unit, "is_available"):
                                    return next_unit.is_available()
                                    
                                # Simple check for other units
                                next_status = getattr(next_unit, "status", None)
                                return next_status != "processing"
        except Exception as e:
            logger.error(f"Error checking downstream availability: {e}")
            
        # Default to available
        return True
    
    def add_heat(self, heat):
        """
        Add a heat to the LMF station's queue.
        
        Args:
            heat: Heat object to be processed
            
        Returns:
            bool: True if heat was successfully added to queue
        """
        try:
            # Ensure heat is valid
            if heat is None:
                logger.error("Attempted to add None heat to LMF queue")
                return False
                
            # Check if we have capacity in our queue
            if len(self.heat_queue) < self.capacity * 2:  # Allow queue up to 2x capacity
                self.heat_queue.append(heat)
                logger.info(f"Heat {heat.id} added to LMF {self.unit_id} queue in bay {self.bay}")
                return True
                
            logger.warning(f"LMF {self.unit_id} in bay {self.bay} queue full, cannot add heat {heat.id}")
            return False
        except Exception as e:
            logger.error(f"Error adding heat to LMF {self.unit_id}: {e}")
            return False
    
    def complete_heat(self, heat):
        """
        Complete processing of a heat and move it to the next step.
        
        Args:
            heat: Heat object that completed processing
        """
        try:
            # Reset status
            self.status = "idle"
            self.current_heat = None
            
            # Update metrics
            self.heats_processed += 1
            
            # In actual implementation, this would hand off to the route manager
            route_manager = getattr(self.env, "route_manager", None)
            if route_manager and hasattr(route_manager, "mark_step_complete"):
                route_manager.mark_step_complete(heat)
            
            # Log completion
            logger.info(f"Heat {heat.id} completed LMF processing in bay {self.bay}")
        except Exception as e:
            logger.error(f"Error completing heat in LMF {self.unit_id}: {e}")