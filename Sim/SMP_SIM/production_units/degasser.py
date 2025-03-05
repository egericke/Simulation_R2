import salabim as sim
import logging
from collections import deque
from production_units.base_unit import BaseProductionUnit

logger = logging.getLogger(__name__)

class DegasserUnit(BaseProductionUnit):
    """
    Enhanced Vacuum Degasser (RH Degasser) for removing unwanted gases from molten steel.
    
    The degasser creates a vacuum to remove hydrogen, nitrogen, and carbon,
    and can also be used for deep desulfurization of certain steel grades.
    """
    
    def __init__(self, env, bay, unit_id=0, name="Degasser", 
                process_time=40, min_process_time=35, capacity=1, **kwargs):
        """
        Initialize a Degasser unit.
        
        Args:
            env: Simulation environment
            bay: Bay identifier
            unit_id: Unit identifier
            name: Name of the degasser
            process_time: Process time in minutes
            min_process_time: Minimum process time in minutes
            capacity: Number of heats that can process simultaneously
        """
        # Error handling for required parameters
        if env is None:
            raise ValueError("Degasser initialization error: Simulation environment (env) is required")
        if not isinstance(bay, str):
            raise ValueError(f"Degasser initialization error: Bay must be a string, got {type(bay)}")
            
        # Calculate position based on unit_id
        x_position = kwargs.get('x', 400)  # Default x position for Degasser
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
            color=kwargs.get('color', 'purple'),  # Degassers are typically purple
            **kwargs
        )
        
        self.unit_id = unit_id
        self.min_process_time = min_process_time
        self.active = True  # Unit is active by default
        
        # Queue for heats waiting to be processed
        self.heat_queue = deque()
        
        # Track the current vacuum level
        self.vacuum_level = 0.0  # 0.0 = no vacuum, 1.0 = full vacuum
        
        # Track degasser cycle status
        self.cycle_stage = "idle"  # idle, evacuating, processing, repressurizing
        self.target_carbon = None
        self.target_hydrogen = None
        self.start_time = None
        
        # Special configurations for different grades
        self.grade_settings = {
            "high_clean": {
                "min_process_time": 40,
                "target_hydrogen": 1.5,  # ppm
                "vacuum_time": 15
            },
            "decarb": {
                "min_process_time": 45,
                "target_carbon": 0.03,  # percentage
                "vacuum_time": 20
            }
        }
        
        # Activate the component instead of creating a process object
        self.activate()
        
        logger.info(f"EnhancedDegasserUnit {unit_id} initialized in bay {bay}")
    
    def process(self):
        """Main processing loop for the degasser."""
        while True:
            try:
                if not self.active:
                    yield self.env.timeout(1)
                    continue
                    
                # Check if we have a heat being processed
                if self.status == "processing":
                    # Already processing a heat
                    current_time = self.env.now()
                    
                    # Check if we should adjust process time based on grade
                    if self.current_heat:
                        try:
                            grade = self.current_heat.grade
                            if grade in self.grade_settings:
                                # Get grade-specific settings
                                settings = self.grade_settings[grade]
                                
                                # Ensure minimum process time for special grades
                                min_time = settings.get("min_process_time", self.min_process_time)
                                if current_time - self.start_time < min_time:
                                    yield self.env.timeout(1)
                                    continue
                        except AttributeError:
                            logger.warning(f"Heat {getattr(self.current_heat, 'id', 'unknown')} missing grade attribute")
                    
                    # Check if processing is complete
                    if current_time - self.start_time >= self.process_time:
                        # Complete the heat processing
                        heat = self.current_heat
                        
                        # Apply grade-specific effects
                        if heat:
                            try:
                                if heat.grade == "high_clean":
                                    # Record hydrogen reduction
                                    if hasattr(heat, "hydrogen_content"):
                                        heat.hydrogen_content = self.grade_settings["high_clean"]["target_hydrogen"]
                                    logger.info(f"Heat {heat.id}: Hydrogen reduced to {self.grade_settings['high_clean']['target_hydrogen']} ppm")
                                
                                elif heat.grade == "decarb":
                                    # Record carbon reduction
                                    if hasattr(heat, "carbon_content"):
                                        heat.carbon_content = self.grade_settings["decarb"]["target_carbon"]
                                    logger.info(f"Heat {heat.id}: Carbon reduced to {self.grade_settings['decarb']['target_carbon']}%")
                            except Exception as e:
                                logger.error(f"Error applying grade-specific effects: {e}")
                        
                        # Repressurize before completing
                        if self.cycle_stage == "processing":
                            logger.info(f"Degasser {self.unit_id} repressurizing")
                            self.cycle_stage = "repressurizing"
                            # Repressurization typically takes a few minutes
                            yield self.env.timeout(3)
                            self.vacuum_level = 0.0
                        
                        # Complete the heat
                        self.complete_heat(heat)
                        
                        # Reset status
                        self.status = "idle"
                        self.current_heat = None
                        self.cycle_stage = "idle"
                        logger.info(f"Degasser {self.unit_id} completed processing heat")
                    
                    # Still processing - update vacuum level based on cycle stage
                    elif self.cycle_stage == "evacuating":
                        # Gradually increase vacuum
                        self.vacuum_level = min(1.0, self.vacuum_level + 0.2)
                        if self.vacuum_level >= 0.95:
                            logger.info(f"Degasser {self.unit_id} reached full vacuum")
                            self.cycle_stage = "processing"
                        yield self.env.timeout(1)
                    
                    elif self.cycle_stage == "processing":
                        # Main processing under vacuum
                        yield self.env.timeout(1)
                    
                    else:
                        # Default processing
                        yield self.env.timeout(1)
                
                # Check if we need to start a new heat from the queue
                elif self.heat_queue and self.status == "idle":
                    try:
                        # Get the next heat to process
                        next_heat = self.heat_queue.popleft()
                        
                        # Start processing
                        self.current_heat = next_heat
                        self.status = "processing"
                        self.start_time = self.env.now()
                        
                        # Start evacuation cycle
                        self.cycle_stage = "evacuating"
                        self.vacuum_level = 0.0
                        logger.info(f"Degasser {self.unit_id} starting evacuation for heat {next_heat.id}")
                        
                        # Set targets based on grade
                        grade = getattr(next_heat, 'grade', 'standard')
                        if grade in self.grade_settings:
                            settings = self.grade_settings[grade]
                            self.target_carbon = settings.get("target_carbon")
                            self.target_hydrogen = settings.get("target_hydrogen")
                            logger.info(f"Degasser {self.unit_id} processing {grade} grade with special settings")
                        
                        # Apply heat-specific processing parameters
                        if grade == "high_clean":
                            # High-clean steel needs more degassing time for hydrogen removal
                            self.process_time = max(self.process_time, 45)
                        elif grade == "decarb":
                            # Decarburization requires longer processing
                            self.process_time = max(self.process_time, 50)
                        else:
                            # Standard processing time for other grades
                            self.process_time = 40
                            
                        # Record processing in heat history
                        if hasattr(next_heat, 'record_process'):
                            next_heat.record_process("Degasser", self.start_time, self.start_time + self.process_time, self.bay)
                    except Exception as e:
                        logger.error(f"Error starting new heat in Degasser {self.unit_id}: {e}")
                        self.status = "idle"
                        yield self.env.timeout(1)
                else:
                    # No heat being processed and none in queue
                    self.status = "idle"
                    yield self.env.timeout(1)
            except Exception as e:
                logger.error(f"Error in Degasser {self.unit_id} process: {e}")
                # Continue operation despite error
                yield self.env.timeout(1)
    

    
    def add_heat(self, heat):
        """
        Add a heat to the degasser queue.
        
        Args:
            heat: Heat object to be processed
            
        Returns:
            bool: True if successfully added to queue
        """
        try:
            # Ensure heat is valid
            if heat is None:
                logger.error("Attempted to add None heat to Degasser queue")
                return False
                
            # Check if we can accept this heat
            if len(self.heat_queue) >= self.capacity * 2:  # Allow queue up to 2x capacity
                logger.warning(f"Degasser {self.unit_id} queue full, cannot add heat {heat.id}")
                return False
            
            self.heat_queue.append(heat)
            logger.info(f"Heat {heat.id} added to Degasser {self.unit_id} queue in bay {self.bay}")
            return True
        except Exception as e:
            logger.error(f"Error adding heat to Degasser {self.unit_id}: {e}")
            return False
    
    def complete_heat(self, heat):
        """
        Complete processing of a heat.
        
        Args:
            heat: Heat object that completed processing
        """
        try:
            if heat is None:
                logger.warning("Attempted to complete None heat in Degasser")
                return
                
            # Handle any post-processing steps
            logger.info(f"Heat {heat.id} completed degasser processing in bay {self.bay}")
            
            # Update metrics
            self.heats_processed += 1
            
            # In actual implementation, this would notify the route manager
            route_manager = getattr(self.env, "route_manager", None)
            if route_manager and hasattr(route_manager, "mark_step_complete"):
                route_manager.mark_step_complete(heat)
        except Exception as e:
            logger.error(f"Error completing heat in Degasser {self.unit_id}: {e}")
    
    def is_available(self):
        return self.ispassive() or (self.state.value() == "idle" and len(self.heat_queue) < self.capacity * 2)
    
    def can_process_grade(self, grade):
        """
        Check if this degasser can process the given grade.
        
        Args:
            grade: Steel grade to check
            
        Returns:
            bool: True if this degasser can process the grade
        """
        # By default, the degasser can process all grades that require it
        # In a more complex implementation, we might check for special equipment requirements
        return True
    
    def get_estimated_wait_time(self):
        """
        Get estimated wait time for a new heat.
        
        Returns:
            float: Estimated wait time in minutes
        """
        try:
            if self.status == "idle" and not self.heat_queue:
                return 0
                
            # If processing, calculate remaining time
            remaining_time = 0
            if self.status == "processing" and self.start_time:
                elapsed = self.env.now() - self.start_time
                remaining_time = max(0, self.process_time - elapsed)
                
            # Add time for queued heats
            queue_time = len(self.heat_queue) * self.process_time
            
            return remaining_time + queue_time
        except Exception as e:
            logger.error(f"Error calculating wait time in Degasser {self.unit_id}: {e}")
            return 0  # Default to no wait if calculation fails