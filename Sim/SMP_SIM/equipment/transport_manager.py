import logging
import time
from heapq import heappush, heappop
from threading import Lock
from equipment.ladle_car import BaseLadleCar
from equipment.crane import Crane

logger = logging.getLogger(__name__)

class TransportManager:
    def __init__(self, env, config, spatial_manager):
        """
        Initialize the transportation manager.
        
        Args:
            env: Simulation environment
            config: Configuration dictionary
            spatial_manager: Reference to the spatial manager
        """
        self.env = env
        self.config = config or {}
        self.spatial_manager = spatial_manager
        self._ladle_cars = []  # Private storage for ladle cars
        self.cranes = {}
        
        # Thread-safe request queue with lock
        self.pending_requests = []
        self.request_lock = Lock()
        
        # Cache for distance calculations
        self.distance_cache = {}
        
        # Resource tracking
        self.crane_resources = {}  # Mapping of bay -> list of resource objects
        
        # Setup transport equipment
        self._setup_transport_equipment()
        logger.info("TransportManager initialized with %d ladle cars and %d bays", 
                    len(self._ladle_cars), len(self.cranes))
    
    def update_config(self, config):
        """
        Update the configuration.
        
        Args:
            config: New configuration dictionary
        """
        self.config = config
        # Configuration changes might require rebuilding equipment
        # For now, we'll just log it
        logger.info("TransportManager configuration updated")

    @property
    def ladle_cars(self):
        """
        Return a copy of the ladle cars list to prevent direct modification.
        """
        return self._ladle_cars.copy()

    def create_ladle_car(self, car_id, car_type, home_bay):
        """
        Factory method to create ladle cars with consistent configuration.
        
        Args:
            car_id: Unique identifier for the car
            car_type: Type of car ("tapping", "treatment", "rh")
            home_bay: Bay where the car is initially located
            
        Returns:
            BaseLadleCar: Newly created ladle car
        """
        try:
            return BaseLadleCar(
                env=self.env, 
                car_id=car_id, 
                car_type=car_type, 
                home_bay=home_bay,
                speed=self.config.get("ladle_car_speed", 150), 
                spatial_manager=self.spatial_manager,
                on_idle_callback=self._process_pending_requests
            )
        except (ValueError, TypeError) as e:
            logger.error(f"Error creating ladle car: {e}", exc_info=True)
            return None

    def _setup_transport_equipment(self):
        """
        Initialize ladle cars and cranes based on configuration.
        """
        # Configuration-driven approach for ladle cars
        car_types = self.config.get("ladle_car_types", ["tapping", "treatment", "rh"])
        n_per_type = self.config.get("n_ladle_cars_per_type", 1)
        n_bays = self.config.get("n_bays", 2)
        
        # Fallback to old approach if specific configuration is missing
        if not self.config.get("ladle_car_types"):
            n_ladle_cars = self.config.get("n_ladle_cars", 3)
            car_id = 1
            for i in range(n_ladle_cars):
                home_bay = f"bay{(i % n_bays) + 1}"
                car_type = "tapping" if i % 3 == 0 else "treatment" if i % 3 == 1 else "rh"
                car = self.create_ladle_car(car_id, car_type, home_bay)
                if car:
                    self._ladle_cars.append(car)
                    car_id += 1
        else:
            # Use configuration-driven approach
            car_id = 1
            for car_type in car_types:
                for _ in range(n_per_type):
                    home_bay = f"bay{((car_id - 1) % n_bays) + 1}"
                    car = self.create_ladle_car(car_id, car_type, home_bay)
                    if car:
                        self._ladle_cars.append(car)
                        car_id += 1
        
        # Initialize cranes per bay
        n_cranes_per_bay = self.config.get("n_cranes_per_bay", 2)
        crane_speed = self.config.get("crane_speed", 100)
        
        # Create crane resources
        import salabim as sim
        
        for bay_id in range(1, n_bays + 1):
            bay_name = f"bay{bay_id}"
            self.cranes[bay_name] = []
            
            # Create resource object for crane usage
            self.crane_resources[bay_name] = sim.Resource(f"Crane_Resource_{bay_name}", capacity=n_cranes_per_bay, env=self.env)
            
            for j in range(n_cranes_per_bay):
                try:
                    crane = Crane(
                        env=self.env, 
                        crane_id=j+1, 
                        bay=bay_name, 
                        speed=crane_speed, 
                        spatial_manager=self.spatial_manager
                    )
                    crane.activate(process="process")
                    self.cranes[bay_name].append(crane)
                except Exception as e:
                    logger.error(f"Error creating crane {j+1} in bay {bay_name}: {e}", exc_info=True)

    def request_transport(self, heat, from_unit, to_unit, priority=0):
        """
        Request transport for a heat between units.
        
        Args:
            heat: Heat to transport
            from_unit: Source unit
            to_unit: Destination unit
            priority: Request priority (higher = more important)
            
        Returns:
            bool: True if request accepted
        """
        # Input validation
        if not heat:
            logger.error("Cannot request transport for null heat")
            return False
            
        if not from_unit or not to_unit:
            logger.error(f"Invalid transport request: from_unit={from_unit}, to_unit={to_unit}")
            return False
            
        # Extract bay information
        try:
            from_bay = getattr(from_unit, "bay", "unknown")
            to_bay = getattr(to_unit, "bay", "unknown")
            
            if from_bay == "unknown" or to_bay == "unknown":
                logger.error(f"Missing bay information for transport request: from={from_bay}, to={to_bay}")
                return False
        except AttributeError as e:
            logger.error(f"Error accessing unit bay information: {e}", exc_info=True)
            return False
        
        # Determine appropriate car type based on source and destination
        car_type = "tapping" if from_bay != to_bay else "treatment"
        if hasattr(to_unit, "name") and callable(to_unit.name) and "caster" in to_unit.name().lower():
            car_type = "treatment"  # Intra-bay to caster

        request = {
            "heat": heat,
            "from_unit": from_unit,
            "to_unit": to_unit,
            "from_bay": from_bay,
            "to_bay": to_bay,
            "car_type": car_type,
            "time_requested": self.env.now(),
            "status": "pending",
            "assigned_car": None
        }
        
        # Thread-safe queue update
        with self.request_lock:
            heappush(self.pending_requests, (-priority, self.env.now(), request))
        
        logger.info("Transport request queued for heat %s from %s to %s with car type %s", 
                    heat.id, from_unit.name(), to_unit.name(), car_type)
        
        # Process requests but don't wait for result
        self._process_pending_requests()
        return True

    def _process_pending_requests(self):
        """
        Process pending transport requests, assigning available cars.
        Limits processing to 10 requests per call for better simulation performance.
        """
        processed_count = 0
        
        # Thread-safe queue processing
        with self.request_lock:
            pending_queue_copy = self.pending_requests.copy()
            self.pending_requests = []
        
        # Process the copy outside the lock
        new_queue = []
        
        for priority, timestamp, request in pending_queue_copy:
            # Skip processed requests
            if request["status"] != "pending":
                continue
                
            # Stop processing at limit
            if processed_count >= 10:
                new_queue.append((priority, timestamp, request))
                continue
            
            # Find available car
            car_type = request["car_type"]
            available_cars = [car for car in self._ladle_cars 
                             if car.car_type == car_type and car.is_available()]
            
            if not available_cars:
                logger.info("No available %s cars; requeuing request for heat %s", 
                           car_type, request["heat"].id)
                new_queue.append((priority, timestamp, request))
                continue

            # Find closest car
            closest_car = self._find_closest_car(available_cars, request["from_bay"])
            
            if not closest_car:
                logger.warning(f"Failed to find closest car for request to {request['from_bay']}")
                new_queue.append((priority, timestamp, request))
                continue
                
            # Assign the request
            request["status"] = "assigned"
            request["assigned_car"] = closest_car
            destination = {"bay": request["to_bay"], "unit": request["to_unit"]}
            
            # Try to assign heat
            success = closest_car.assign_heat(request["heat"], destination)

            if success:
                logger.info("Assigned %s car %d to heat %s from %s to %s", 
                           car_type, closest_car.car_id, request["heat"].id, 
                           request["from_bay"], request["to_bay"])
            else:
                logger.warning("Failed to assign %s car %d to heat %s; requeuing", 
                              car_type, closest_car.car_id, request["heat"].id)
                request["status"] = "pending"
                request["assigned_car"] = None
                new_queue.append((priority, timestamp, request))
                
            processed_count += 1
        
        # Write back the new queue safely
        with self.request_lock:
            for item in new_queue:
                heappush(self.pending_requests, item)

    def _find_closest_car(self, available_cars, target_bay):
        """
        Find the closest car to a target bay based on distance.
        
        Args:
            available_cars: List of available cars
            target_bay: Target bay ID
            
        Returns:
            BaseLadleCar: Closest car or None
        """
        if not available_cars:
            return None
            
        try:
            # Use cached distances where possible
            closest_car = min(
                available_cars, 
                key=lambda car: self._get_bay_distance(car.current_bay, target_bay)
            )
            return closest_car
        except Exception as e:
            logger.error(f"Error finding closest car: {e}", exc_info=True)
            return available_cars[0] if available_cars else None

    def _get_bay_distance(self, from_bay, to_bay):
        """
        Get the distance between two bays, using cache when possible.
        
        Args:
            from_bay: Source bay ID
            to_bay: Destination bay ID
            
        Returns:
            float: Distance between bays
        """
        # Check cache first
        cache_key = f"{from_bay}_to_{to_bay}"
        if cache_key in self.distance_cache:
            return self.distance_cache[cache_key]
            
        # Same bay - zero distance
        if from_bay == to_bay:
            self.distance_cache[cache_key] = 0
            return 0
            
        # Try to get from spatial manager
        try:
            path = self.spatial_manager.get_path_between_bays(from_bay, to_bay)
            if path and isinstance(path, list) and len(path) > 0:
                total_distance = sum(segment.get("distance", 0) for segment in path)
                self.distance_cache[cache_key] = total_distance
                return total_distance
        except Exception as e:
            logger.warning(f"Error getting path between bays {from_bay} and {to_bay}: {e}")
            
        # Fallback to direct distance calculation
        try:
            from_pos = self.spatial_manager.get_bay_position(from_bay)
            to_pos = self.spatial_manager.get_bay_position(to_bay)
            
            if from_pos and to_pos:
                dx = to_pos["x"] - from_pos["x"]
                dy = to_pos["y"] - from_pos["y"]
                distance = (dx**2 + dy**2)**0.5
                self.distance_cache[cache_key] = distance
                return distance
        except Exception as e:
            logger.error(f"Error calculating distance between bays: {e}", exc_info=True)
            
        # Final fallback - use default
        logger.warning("No path or positions for bays %s to %s; using default distance 100", 
                      from_bay, to_bay)
        self.distance_cache[cache_key] = 100
        return 100

    def check_transport_status(self, heat):
        """
        Check status of transport for a specific heat.
        
        Args:
            heat: Heat object to check
            
        Returns:
            dict: Status information
        """
        if not heat:
            logger.error("Cannot check status for null heat")
            return {"status": "unknown"}
            
        try:
            heat_id = heat.id
        except AttributeError:
            logger.error("Heat object missing id attribute")
            return {"status": "unknown"}
            
        # Check pending requests
        with self.request_lock:
            for _, _, request in self.pending_requests:
                try:
                    if request["heat"].id == heat_id:
                        return {
                            "status": request["status"],
                            "time_requested": request["time_requested"],
                            "waiting_time": self.env.now() - request["time_requested"],
                            "assigned_car": request["assigned_car"].car_id if request["assigned_car"] else None
                        }
                except AttributeError:
                    continue  # Skip invalid requests
        
        # Check active transports
        for car in self._ladle_cars:
            if car.current_heat and car.current_heat.id == heat_id:
                try:
                    # Check car status with error handling
                    car_status = car.get_status_string()
                    
                    return {
                        "status": car_status,
                        "car_id": car.car_id,
                        "current_bay": car.current_bay,
                        "destination_bay": car.destination.get("bay") if car.destination else None,
                        "progress": f"{car.current_path_segment}/{len(car.path)}" if car.path else "N/A"
                    }
                except (AttributeError, TypeError) as e:
                    logger.error(f"Error getting car status for heat {heat_id}: {e}", exc_info=True)
                    return {"status": "error_checking", "heat_id": heat_id}
                
        return {"status": "not_in_transport"}

    def get_status(self):
        """
        Get overall status of transport system.
        
        Returns:
            dict: System status information
        """
        return {
            "ladle_cars": [
                {
                    "car_id": car.car_id,
                    "car_type": car.car_type,
                    "status": car.get_status_string(),
                    "current_bay": car.current_bay,
                    "destination": car.destination,
                    "current_heat": car.current_heat.id if car.current_heat else None,
                    "metrics": car.get_metrics() if hasattr(car, "get_metrics") else {}
                }
                for car in self._ladle_cars
            ],
            "cranes": {
                bay: [
                    {
                        "crane_id": crane.unit_id, 
                        "status": crane.crane_state.value,
                        "utilization": crane.get_utilization(),
                        "metrics": crane.get_metrics() if hasattr(crane, "get_metrics") else {}
                    } 
                    for crane in cranes
                ]
                for bay, cranes in self.cranes.items()
            },
            "pending_requests": len(self.pending_requests),
            "distance_cache_size": len(self.distance_cache)
        }

    def request_crane(self, bay, task):
        """
        Request a crane for a specific task in a bay.
        Uses Salabim Resource for thread-safe allocation.
        
        Args:
            bay: Bay where crane is needed
            task: Task description
            
        Returns:
            Crane: Available crane or None
        """
        if bay not in self.cranes:
            logger.error("No cranes registered in bay %s", bay)
            return None
            
        # First check if any crane is directly available
        available_cranes = [crane for crane in self.cranes[bay] if crane.is_available()]
        if available_cranes:
            crane = available_cranes[0]
            logger.debug("Crane %d in bay %s allocated for task", crane.unit_id, bay)
            return crane
            
        # If no crane is directly available, we'll use resource allocation
        # This is for future implementation - direct check is simpler for now
        logger.info("No available cranes in bay %s", bay)
        return None
        
    def clear_cache(self):
        """Clear the distance cache."""
        self.distance_cache.clear()
        logger.info("TransportManager distance cache cleared")