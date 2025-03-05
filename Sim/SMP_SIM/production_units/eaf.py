from production_units.base_unit import BaseProductionUnit
import logging

logger = logging.getLogger(__name__)

class EnhancedEAFUnit(BaseProductionUnit):
    """
    Enhanced Electric Arc Furnace with grade-specific timing and flexibility.
    """
    def __init__(self, name, unit_id, process_time=50, min_process_time=50, 
                 capacity=1, env=None, x=200, y=100, bay="bay1", **kwargs):
        """
        Initialize an enhanced EAF unit.
        
        Args:
            name: Unit identifier
            unit_id: Numeric ID for this unit
            process_time: Default time to process a heat
            min_process_time: Minimum required processing time
            capacity: Number of heats that can be processed simultaneously
            env: Salabim environment
            x: X position for visualization
            y: Y position for visualization
            bay: Bay identifier
        """
        # Error handling for required parameters
        if env is None:
            raise ValueError("EAF initialization error: Simulation environment (env) is required")
        if not isinstance(bay, str):
            raise ValueError(f"EAF initialization error: Bay must be a string, got {type(bay)}")
        if not isinstance(name, str):
            raise ValueError(f"EAF initialization error: Name must be a string, got {type(name)}")
            
        # Calculate vertical position based on unit_id
        y_offset = y + unit_id * 80
        
        # Call parent constructor with keyword arguments
        super().__init__(
            name=name,
            process_time=process_time,
            capacity=capacity,
            env=env,
            x=x,
            y=y_offset,
            bay=bay,
            color="red",  # EAF is typically red hot
            **kwargs
        )
        
        self.unit_id = unit_id
        self.min_process_time = min_process_time
        self.can_slow_down = True  # Whether EAF can slow down if downstream is busy
        
        logger.info(f"EnhancedEAFUnit {unit_id} initialized in bay {bay}")
        
    def process(self):
        """Main process loop for the EAF with flexibility."""
        while True:
            try:
                if not self.heat_queue:
                    self._update_metrics("idle")
                    yield self.passivate()
                    
                # Get heat from queue
                try:
                    heat = self.heat_queue.pop()
                except Exception as e:
                    logger.error(f"Error getting heat from queue: {e}")
                    yield self.env.timeout(1)
                    continue
                    
                self.current_heat = heat
                self._update_metrics("processing")
                
                # Calculate grade-specific process time
                try:
                    actual_process_time = self.calculate_process_time(heat)
                except Exception as e:
                    logger.error(f"Error calculating process time: {e}, using default")
                    actual_process_time = self.process_time
                    
                logger.info(f"{self.env.now():.2f} {self.name}: Processing heat {heat.id}, grade {getattr(heat, 'grade', 'unknown')}, time: {actual_process_time}")
                
                # Check if we should slow down due to downstream bottlenecks
                try:
                    if self.can_slow_down and self.should_slow_down():
                        # Add extra time to avoid overwhelming downstream
                        actual_process_time += 10
                        logger.info(f"{self.env.now():.2f} {self.name}: Slowing down processing to avoid bottleneck")
                except Exception as e:
                    logger.warning(f"Error checking slowdown conditions: {e}")
                
                # Process the heat
                process_start = self.env.now()
                yield self.hold(actual_process_time)
                process_end = self.env.now()
                
                # Heat is processed - update metrics
                self.heats_processed += 1
                self.busy_time += actual_process_time
                self.total_processing_time += actual_process_time
                
                # Record in heat history if method exists
                if hasattr(heat, 'record_process'):
                    heat.record_process("EAF", process_start, process_end, self.bay)
                
                # Clear current unit reference
                heat.current_unit = None
                
                # If heat has a ladle, prepare for next step
                if hasattr(heat, 'ladle') and heat.ladle:
                    # We don't release the ladle here as it continues through the process
                    pass
                    
                # Notify route manager if available
                route_manager = getattr(self.env, "route_manager", None)
                if route_manager and hasattr(route_manager, "mark_step_complete"):
                    route_manager.mark_step_complete(heat)
                
                # Reset state
                self.current_heat = None
                self._update_metrics("idle")
                
            except Exception as e:
                logger.error(f"Error in EAF {self.unit_id} process: {e}")
                # Reset state and continue
                self.current_heat = None
                self._update_metrics("idle")
                yield self.env.timeout(1)
            
    def calculate_process_time(self, heat):
        """
        Calculate the appropriate process time for a heat based on grade.
        
        Args:
            heat: Heat object being processed
            
        Returns:
            float: Adjusted process time
        """
        # Start with default process time
        base_time = self.process_time
        
        try:
            # Apply grade-specific adjustments (tap-to-tap time variations)
            if hasattr(heat, 'grade'):
                if heat.grade == "high_clean":
                    # ULC grades often need longer processing
                    base_time += 18  # Longer tap-to-tap time
                elif heat.grade == "decarb":
                    # Decarburization may require additional processing
                    base_time += 12
                
            # Check for grade-specific properties
            if hasattr(heat, 'grade_specific_props'):
                if 'eaf_time' in heat.grade_specific_props:
                    base_time = heat.grade_specific_props['eaf_time']
        except Exception as e:
            logger.warning(f"Error applying grade-specific process time: {e}")
                    
        # Apply minimum process time constraint
        return max(base_time, self.min_process_time)
        
    def should_slow_down(self):
        """
        Determine if the EAF should slow down based on downstream conditions.
        """
        try:
            # Check if any LMF in the same bay has a long queue
            route_manager = getattr(self.env, "route_manager", None)
            if route_manager and hasattr(route_manager, "units"):
                bay_units = route_manager.units.get(self.bay, {})
                lmfs = bay_units.get("LMF", [])
                
                for lmf in lmfs:
                    if hasattr(lmf, 'heat_queue') and len(lmf.heat_queue) > 1:
                        return True
                        
            return False
        except Exception as e:
            logger.warning(f"Error checking downstream conditions: {e}")
            return False
            
    def add_heat(self, heat):
        """Add a heat to the processing queue with error handling."""
        try:
            # Ensure heat is valid
            if heat is None:
                logger.error("Attempted to add None heat to EAF queue")
                return False
                
            # Track waiting time if we already have heats in queue
            if self.heat_queue:
                self._update_metrics("waiting")
            
            # Add to queue
            self.heat_queue.add(heat)
            logger.info(f"Heat {heat.id} added to EAF {self.unit_id} queue in bay {self.bay}")
            
            # Activate if idle
            if self.ispassive():
                self.activate()
                
            return True
        except Exception as e:
            logger.error(f"Error adding heat to EAF {self.unit_id}: {e}")
            return False
            
def is_available(self):
    return self.ispassive() or (self.state.value() == "idle" and len(self.heat_queue) < self.capacity * 2)