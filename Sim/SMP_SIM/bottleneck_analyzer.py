import logging
import numpy as np
from collections import defaultdict, deque

logger = logging.getLogger(__name__)

class BottleneckAnalyzer:
    """
    Analyzes production flow to identify bottlenecks in the steel plant.
    Uses metrics like utilization, queue length, and waiting time to identify constraints.
    """
    def __init__(self, production_manager, config=None):
        self.production_manager = production_manager
        self.config = config or {}
        
        # Tracking window size (how many data points to keep for trending)
        self.window_size = self.config.get("analytics", {}).get("window_size", 20)
        
        # Initialize metrics storage
        self.metrics = {
            "utilization": defaultdict(lambda: deque(maxlen=self.window_size)),
            "queue_length": defaultdict(lambda: deque(maxlen=self.window_size)),
            "wait_time": defaultdict(lambda: deque(maxlen=self.window_size)),
            "cycle_time": defaultdict(lambda: deque(maxlen=self.window_size)),
            "blocked_time": defaultdict(lambda: deque(maxlen=self.window_size))
        }
        
        # Bottleneck thresholds
        self.thresholds = {
            "high_utilization": self.config.get("analytics", {}).get("high_utilization", 0.85),
            "queue_alert": self.config.get("analytics", {}).get("queue_alert", 2),
            "wait_time_alert": self.config.get("analytics", {}).get("wait_time_alert", 20)
        }
        
        logger.info("Bottleneck analyzer initialized with window size: %d", self.window_size)

    def collect_current_metrics(self):
        """Collect current metrics from all production units."""
        
        if not self.production_manager:
            logger.warning("Cannot collect metrics: Production manager is None")
            return
        
        current_time = self.production_manager.env.now()
        
        # Process processing units
        if hasattr(self.production_manager, "units"):
            for bay_name, bay_units in self.production_manager.units.items():
                for unit_type, units in bay_units.items():
                    if isinstance(units, list):
                        for unit in units:
                            self._collect_unit_metrics(unit, current_time)
                    else:
                        self._collect_unit_metrics(units, current_time)
        
        # Process ladle cars with safe access
        ladle_cars = self._get_ladle_cars_safely()
        
        for ladle_car in ladle_cars:
            unit_name = self._get_unit_name(ladle_car)
            
            # Use the safe status access method if available
            if hasattr(ladle_car, "get_status_string") and callable(getattr(ladle_car, "get_status_string")):
                status_value = ladle_car.get_status_string()
                logger.debug(f"Ladle car {unit_name} status (via get_status_string): {status_value}")
                is_active = ladle_car.current_heat is not None or status_value in ["moving", "loading", "unloading"]
            else:
                # Fall back to trying car_status.value with careful handling
                try:
                    status_value = self._safe_get_state_value(ladle_car, "car_status")
                    logger.debug(f"Ladle car {unit_name} car_status.value type: {type(status_value)}")
                    
                    # Handle string values
                    if isinstance(status_value, str):
                        is_active = ladle_car.current_heat is not None or status_value in ["moving", "loading", "unloading"]
                    # Handle salabim Monitor objects or other unexpected types
                    else:
                        logger.warning(f"Unexpected type for car_status.value in {unit_name}: {type(status_value)}. Expected str.")
                        is_active = ladle_car.current_heat is not None  # Fallback to heat check
                except Exception as e:
                    logger.error(f"Error accessing car_status for {unit_name}: {e}")
                    is_active = ladle_car.current_heat is not None  # Fallback to heat check
            
            utilization = 1.0 if is_active else 0.0
            self.metrics["utilization"][unit_name].append(utilization)
            
            # Get queue length with safe access
            queue_length = 0
            if hasattr(ladle_car, "move_queue"):
                queue_length = len(ladle_car.move_queue)
            elif hasattr(ladle_car, "path"):
                queue_length = len(ladle_car.path)
            
            self.metrics["queue_length"][unit_name].append(queue_length)
        
        logger.debug(f"Collected metrics at time {current_time:.2f}")

    def _get_ladle_cars_safely(self):
        """Get ladle cars with robust error handling for different access patterns."""
        try:
            # Try using the get_ladle_cars method first
            if hasattr(self.production_manager, "get_ladle_cars") and callable(getattr(self.production_manager, "get_ladle_cars")):
                return self.production_manager.get_ladle_cars()
            
            # Fall back to direct attribute access
            elif hasattr(self.production_manager, "ladle_cars"):
                if callable(self.production_manager.ladle_cars):
                    return self.production_manager.ladle_cars()
                else:
                    return self.production_manager.ladle_cars
            
            # Try accessing through transport manager
            elif hasattr(self.production_manager, "transport_manager") and hasattr(self.production_manager.transport_manager, "ladle_cars"):
                if callable(self.production_manager.transport_manager.ladle_cars):
                    return self.production_manager.transport_manager.ladle_cars()
                else:
                    return self.production_manager.transport_manager.ladle_cars
        except Exception as e:
            logger.error(f"Error getting ladle cars: {e}")
        
        # Return an empty list if all methods fail
        logger.warning("Unable to access ladle cars through any method; using empty list")
        return []

    def _safe_get_state_value(self, obj, state_attr_name):
        """
        Safely get the value of a salabim State object, handling various cases.
        
        Args:
            obj: Object containing the state
            state_attr_name: Name of the state attribute
            
        Returns:
            Current state value as a string when possible
        """
        if not hasattr(obj, state_attr_name):
            return "unknown"
            
        state_obj = getattr(obj, state_attr_name)
        
        # Handle case where the attribute might be a string directly
        if isinstance(state_obj, str):
            return state_obj
            
        # Handle case where it's a salabim State object
        try:
            if hasattr(state_obj, "value"):
                value_or_monitor = state_obj.value
                
                # If it's a string, return directly
                if isinstance(value_or_monitor, str):
                    return value_or_monitor
                    
                # If it's a Monitor, try to get the current state
                if hasattr(value_or_monitor, "tx") and hasattr(value_or_monitor, "tx") and len(value_or_monitor.tx) > 0:
                    return value_or_monitor.tx[-1]
                    
                # Special case for salabim StateMonitor
                if hasattr(value_or_monitor, "_state"):
                    state_obj = value_or_monitor._state
                    if hasattr(state_obj, "_value"):
                        return state_obj._value
            
            # Try accessing _value directly as a fallback
            if hasattr(state_obj, "_value"):
                return state_obj._value
                
        except Exception as e:
            logger.error(f"Error getting state value: {e}")
            
        # Last resort: try to convert to string
        try:
            return str(state_obj)
        except:
            return "unknown"

    def _get_unit_name(self, unit):
        """Safely get the name of a unit."""
        if unit is None:
            return "Unknown"
        if hasattr(unit, 'name') and callable(getattr(unit, 'name')):
            return unit.name()
        if hasattr(unit, 'name') and not callable(getattr(unit, 'name')):
            return unit.name
        if hasattr(unit, 'id'):
            return f"{unit.__class__.__name__}_{unit.id}"
        if hasattr(unit, 'unit_id'):
            return f"{unit.__class__.__name__}_{unit.unit_id}"
        if hasattr(unit, 'car_id'):
            return f"{unit.__class__.__name__}_{unit.car_id}"
        return str(unit)

    def _collect_unit_metrics(self, unit, current_time):
        """Collect metrics for a single production unit."""
        import salabim as sim
        unit_name = self._get_unit_name(unit)
        
        # Check for valid production unit structure
        if not hasattr(unit, "heat_queue"):
            logger.warning(f"Unit {unit_name} is missing heat_queue attribute, skipping")
            return
            
        is_active = len(unit.heat_queue) > 0 or (hasattr(unit, "current_heat") and unit.current_heat is not None)
        utilization = 1.0 if is_active else 0.0
        self.metrics["utilization"][unit_name].append(utilization)
        queue_length = len(unit.heat_queue)
        self.metrics["queue_length"][unit_name].append(queue_length)
        
        # Safely collect additional metrics if available
        self._safe_collect_monitor(unit, "waiting_time", "wait_time", unit_name)
        self._safe_collect_monitor(unit, "blocked_time", "blocked_time", unit_name)
        self._safe_collect_monitor(unit, "cycle_time", "cycle_time", unit_name)

    def _safe_collect_monitor(self, unit, attr_name, metric_key, unit_name):
        """Safely collect a metric from a salabim Monitor if available."""
        import salabim as sim
        if hasattr(unit, attr_name):
            try:
                value = getattr(unit, attr_name)
                # Handle salabim Monitor objects
                if isinstance(value, sim.Monitor):
                    if value.tally_count() > 0:
                        value = value.mean()
                    else:
                        value = 0
                # Handle other metric types
                elif hasattr(value, "__float__"):
                    value = float(value)
                else:
                    logger.debug(f"Unit {unit_name} {attr_name} is not a number: {type(value)}")
                    value = 0
                    
                self.metrics[metric_key][unit_name].append(value)
            except Exception as e:
                logger.error(f"Error processing {attr_name} for {unit_name}: {e}")
                self.metrics[metric_key][unit_name].append(0)

    def identify_bottlenecks(self):
        """Identify bottlenecks in the system based on collected metrics."""
        # Calculate average metrics for each unit
        avg_metrics = {
            metric_type: {
                unit: np.mean(values) if values else 0 
                for unit, values in unit_metrics.items()
            }
            for metric_type, unit_metrics in self.metrics.items()
        }
        
        logger.debug(f"Thresholds: {self.thresholds}")
        for metric_type, metrics in avg_metrics.items():
            for unit, value in metrics.items():
                logger.debug(f"{metric_type} for {unit}: {value} (type: {type(value)})")
    
        # Method 1: High utilization
        high_util_units = [
            (unit, value) for unit, value in avg_metrics["utilization"].items()
            if value >= self.thresholds["high_utilization"]
        ]
    
        # Method 2: Long queues
        long_queue_units = [
            (unit, value) for unit, value in avg_metrics["queue_length"].items()
            if value >= self.thresholds["queue_alert"]
        ]
    
        # Method 3: Longest waiting times
        long_wait_units = [
            (unit, value) for unit, value in avg_metrics["wait_time"].items()
            if value >= self.thresholds["wait_time_alert"]
        ]
    
        # Combine methods (give points for each bottleneck indicator)
        bottleneck_scores = defaultdict(int)
        for unit, _ in high_util_units:
            bottleneck_scores[unit] += 2  # High utilization is a strong indicator
    
        for unit, _ in long_queue_units:
            bottleneck_scores[unit] += 1
    
        for unit, _ in long_wait_units:
            bottleneck_scores[unit] += 1
    
        # Create bottleneck report
        bottlenecks = []
        for unit, score in bottleneck_scores.items():
            if score >= 2:  # At least 2 points to be considered a bottleneck
                severity = "High" if score >= 3 else "Medium"
            
                # Determine causes
                causes = []
                if any(u == unit for u, _ in high_util_units):
                    causes.append("High utilization")
                if any(u == unit for u, _ in long_queue_units):
                    causes.append("Long queue")
                if any(u == unit for u, _ in long_wait_units):
                    causes.append("Long wait times")
            
                bottlenecks.append({
                    "unit": unit,
                    "severity": severity,
                    "score": score,
                    "causes": causes,
                    "metrics": {
                        "utilization": avg_metrics["utilization"].get(unit, 0),
                        "queue_length": avg_metrics["queue_length"].get(unit, 0),
                        "wait_time": avg_metrics["wait_time"].get(unit, 0)
                    }
                })
    
        # Sort by score (highest first)
        bottlenecks.sort(key=lambda x: x["score"], reverse=True)
    
        if bottlenecks:
            logger.info(f"Identified {len(bottlenecks)} bottlenecks. Primary: {bottlenecks[0]['unit']}")
        else:
            logger.info("No bottlenecks identified in the current system state")
    
        return bottlenecks

    def get_throughput_analysis(self):
        """Analyze system throughput and identify limiting factors."""
        pm = self.production_manager
        
        if not hasattr(pm, "completed_heats") or not pm.completed_heats:
            return {"status": "insufficient_data"}
        
        total_time = pm.env.now()
        if total_time <= 0:
            return {"status": "insufficient_data"}
        
        throughput = len(pm.completed_heats) / total_time
        avg_cycle_time = pm.total_cycle_time / len(pm.completed_heats) if len(pm.completed_heats) > 0 else 0
        takt_time = self.config.get("takt_time", 60)
        
        bottlenecks = self.identify_bottlenecks()
        primary_bottleneck = bottlenecks[0]["unit"] if bottlenecks else "None"
        
        theoretical_max = 0
        if bottlenecks:
            bottleneck_unit_name = bottlenecks[0]["unit"]
            bottleneck_unit = None
            
            # Find the bottleneck unit in the production units
            for bay_units in pm.units.values():
                for unit_type, units in bay_units.items():
                    if isinstance(units, list):
                        for unit in units:
                            if self._get_unit_name(unit) == bottleneck_unit_name:
                                bottleneck_unit = unit
                                break
                    elif self._get_unit_name(units) == bottleneck_unit_name:
                        bottleneck_unit = units
                        break
                if bottleneck_unit:
                    break
                    
            if bottleneck_unit and hasattr(bottleneck_unit, "process_time"):
                theoretical_max = 1 / bottleneck_unit.process_time
        
        efficiency = throughput / theoretical_max if theoretical_max > 0 else 0
        
        return {
            "status": "ok",
            "throughput": throughput,
            "avg_cycle_time": avg_cycle_time,
            "takt_time": takt_time,
            "takt_achievement": takt_time / avg_cycle_time if avg_cycle_time > 0 else 0,
            "primary_bottleneck": primary_bottleneck,
            "theoretical_max_throughput": theoretical_max,
            "system_efficiency": efficiency,
            "bottlenecks": bottlenecks
        }

    def get_unit_analytics(self, unit_name):
        """Get detailed analytics for a specific unit by name."""
        # Search in production units
        for bay_name, bay_units in self.production_manager.units.items():
            for unit_type, units in bay_units.items():
                if isinstance(units, list):
                    for unit in units:
                        if self._get_unit_name(unit) == unit_name:
                            return self._get_unit_metrics(unit, bay_name, unit_type)
                elif self._get_unit_name(units) == unit_name:
                    return self._get_unit_metrics(units, bay_name, unit_type)
        
        # Search in transport equipment
        ladle_cars = self._get_ladle_cars_safely()
        for ladle_car in ladle_cars:
            if self._get_unit_name(ladle_car) == unit_name:
                return self._get_unit_metrics(ladle_car, "Transport", "LadleCar")
        
        return {
            "status": "error",
            "message": f"Unit not found: {unit_name}"
        }

    def _get_unit_metrics(self, unit, bay_name, unit_type):
        """Extract metrics for a specific unit and return formatted data."""
        unit_name = self._get_unit_name(unit)
        
        metrics = {}
        # Process each metric type
        for metric_type, all_unit_data in self.metrics.items():
            if unit_name in all_unit_data and all_unit_data[unit_name]:
                data_points = list(all_unit_data[unit_name])
                metrics[metric_type] = {
                    "current": data_points[-1] if data_points else 0,
                    "average": sum(data_points) / len(data_points) if data_points else 0,
                    "min": min(data_points) if data_points else 0,
                    "max": max(data_points) if data_points else 0,
                    "history": data_points
                }
            else:
                # No data for this metric
                metrics[metric_type] = {
                    "current": 0,
                    "average": 0,
                    "min": 0,
                    "max": 0,
                    "history": []
                }
        
        # Add unit-specific details with safe attribute access
        unit_info = {
            "name": unit_name,
            "bay": bay_name,
            "type": unit_type,
            "process_time": getattr(unit, "process_time", 0),
            "capacity": getattr(unit, "capacity", 1) if hasattr(unit, "capacity") else 1,
            "current_queue_length": len(getattr(unit, "heat_queue", [])) if hasattr(unit, "heat_queue") else 0
        }
        
        return {
            "status": "ok",
            "unit_info": unit_info,
            "metrics": metrics
        }

    def recommend_improvements(self):
        """
        Recommend improvements based on bottleneck analysis.
        Returns a list of recommended actions.
        """
        bottlenecks = self.identify_bottlenecks()
        if not bottlenecks:
            return [{"type": "info", "message": "No bottlenecks detected. System is running efficiently."}]
        
        recommendations = []
        
        for bottleneck in bottlenecks:
            unit = bottleneck["unit"]
            severity = bottleneck["severity"]
            causes = bottleneck["causes"]
            
            # Get unit details to make specific recommendations
            unit_analysis = self.get_unit_analytics(unit)
            if unit_analysis["status"] != "ok":
                continue
                
            unit_info = unit_analysis["unit_info"]
            unit_type = unit_info["type"]
            
            # Make recommendations based on bottleneck causes and unit type
            if "High utilization" in causes:
                if unit_type in ["EAFUnit", "LMFStation", "DegassingUnit", "Caster"]:
                    recommendations.append({
                        "type": "capacity",
                        "unit": unit,
                        "severity": severity,
                        "message": f"Consider adding capacity to {unit} or reducing process time.",
                        "actions": [
                            f"Increase {unit_type} capacity",
                            f"Optimize {unit_type} process time"
                        ]
                    })
            
            if "Long queue" in causes:
                if unit_type == "LadleCar":
                    recommendations.append({
                        "type": "transport",
                        "unit": unit,
                        "severity": severity,
                        "message": f"Add more ladle cars to reduce waiting times.",
                        "actions": [
                            "Add more ladle cars",
                            "Optimize ladle car routing"
                        ]
                    })
                else:
                    recommendations.append({
                        "type": "flow",
                        "unit": unit,
                        "severity": severity,
                        "message": f"Optimize flow into {unit} to reduce queue buildup.",
                        "actions": [
                            "Review upstream processes",
                            "Modify heat scheduling"
                        ]
                    })
            
            if "Long wait times" in causes:
                recommendations.append({
                    "type": "scheduling",
                    "unit": unit,
                    "severity": severity,
                    "message": f"Improve scheduling to reduce wait times at {unit}.",
                    "actions": [
                        "Implement better scheduling algorithm",
                        "Review routing decisions"
                    ]
                })
        
        # Add general recommendations if we have multiple bottlenecks
        if len(bottlenecks) > 1:
            recommendations.append({
                "type": "layout",
                "severity": "Medium",
                "message": "Consider revising plant layout to optimize material flow.",
                "actions": [
                    "Review distances between units",
                    "Optimize unit placement"
                ]
            })
        
        return recommendations

    def generate_analytics_report(self):
        """Generate a comprehensive analytics report."""
        throughput = self.get_throughput_analysis()
        bottlenecks = self.identify_bottlenecks()
        recommendations = self.recommend_improvements()
        
        unit_metrics = {}
        for bay_name, bay_units in self.production_manager.units.items():
            for unit_type, units in bay_units.items():
                if isinstance(units, list):
                    for unit in units:
                        unit_name = self._get_unit_name(unit)
                        unit_metrics[unit_name] = self.get_unit_analytics(unit_name)
                else:
                    unit_name = self._get_unit_name(units)
                    unit_metrics[unit_name] = self.get_unit_analytics(unit_name)
        
        pm = self.production_manager
        system_metrics = {
            "heats_processed": pm.heats_processed,
            "heats_completed": len(pm.completed_heats),
            "completion_rate": len(pm.completed_heats) / pm.heats_processed if pm.heats_processed > 0 else 0,
            "total_simulation_time": pm.env.now(),
            "avg_cycle_time": pm.total_cycle_time / len(pm.completed_heats) if len(pm.completed_heats) > 0 else 0
        }
        
        # Safely get total distance traveled
        total_distance = 0
        ladle_cars = self._get_ladle_cars_safely()
        for lc in ladle_cars:
            total_distance += getattr(lc, "total_distance_traveled", 0)
            
        system_metrics["total_distance"] = total_distance
        
        return {
            "timestamp": pm.env.now(),
            "system_metrics": system_metrics,
            "throughput_analysis": throughput,
            "bottlenecks": bottlenecks,
            "recommendations": recommendations,
            "unit_metrics": unit_metrics
        }