import salabim as sim
import logging
import random
from collections import defaultdict

from spatial.spatial_manager import SpatialManager
from process_control.route_manager import ProcessRouteManager as OriginalRouteManager
from route_manager_adapter import ProcessRouteManagerAdapter
from process_control.steel_grade import SteelGrade
from equipment.transport_manager import TransportManager
from equipment.ladle_manager import LadleManager
from production_units.eaf import EnhancedEAFUnit
from production_units.lmf import EnhancedLMFStation
from production_units.degasser import DegasserUnit
from production_units.caster import EnhancedCaster
from production_units.heat import Heat

logger = logging.getLogger(__name__)

class ProductionManager(sim.Component):
    """
    Manages the steel production process, including heat generation, routing, and equipment coordination.
    """

    def __init__(self, n_lmf=2, n_degassers=1, n_casters=1, config=None, 
                 scenario_manager=None, layer_manager=None, env=None, **kwargs):
        """
        Initialize the ProductionManager.

        Args:
            n_lmf (int): Number of LMF stations per bay (default: 2).
            n_degassers (int): Number of degassers per bay (default: 1).
            n_casters (int): Number of casters per bay (default: 1).
            config (dict): Configuration dictionary (optional).
            scenario_manager: ScenarioManager instance (optional).
            layer_manager: LayerManager instance for visualization (optional).
            env: Salabim simulation environment (optional, creates new if None).
        """
        # Store configuration and managers
        self.config = config or {}
        self.scenario_manager = scenario_manager
        self.layer_manager = layer_manager
        self.env = env or sim.Environment()

        # Store unit counts as instance variables
        self.n_lmf = n_lmf
        self.n_degassers = n_degassers
        self.n_casters = n_casters

        # Initialize managers
        self.spatial_manager = SpatialManager(self.config)
        self.steel_grades = SteelGrade.create_from_config(self.config)
        self.route_manager = ProcessRouteManagerAdapter(self.config, self.spatial_manager, self.steel_grades)
        self.transport_manager = TransportManager(self.env, self.config, self.spatial_manager)
        self.ladle_manager = LadleManager(self.env, self.config)

        # Make managers available to environment
        self.env.spatial_manager = self.spatial_manager
        self.env.route_manager = self.route_manager
        self.env.transport_manager = self.transport_manager
        self.env.ladle_manager = self.ladle_manager

        # Units and equipment storage
        self.units = defaultdict(dict)
        self.bay_equipment = defaultdict(lambda: defaultdict(list))

        # Counters and tracking
        self.heat_counter = 0
        self.generated_heats = []
        self.active_heats = []
        self.completed_heats = []
        self._heats_processed = 0
        self.total_cycle_time = 0

        # Processes
        self.heat_generator = None
        self.route_processor = None

        # Initialize the component
        super().__init__(env=self.env, name="ProductionManager", **kwargs)
        logger.info("ProductionManager initialized")

    def get_ladle_cars(self):
        """
        Get a copy of the ladle cars list.
        
        Returns:
            list: Copy of ladle cars from transport manager
        """
        return self.transport_manager.ladle_cars

    # Backward compatibility property for existing code that accesses ladle_cars directly
    @property
    def ladle_cars(self):
        """
        Property that provides backward compatibility for code that accesses ladle_cars directly.
        Returns a copy of the ladle cars from the transport manager.
        """
        return self.get_ladle_cars()

    @property
    def heats_processed(self):
        """Get the number of processed heats."""
        return self._heats_processed

    @heats_processed.setter
    def heats_processed(self, value):
        """Set the number of processed heats."""
        self._heats_processed = value

    def complete_heat(self, heat):
        """
        Mark a heat as completed and update statistics.

        Args:
            heat: Heat object that completed processing.
        """
        if heat not in self.completed_heats:
            if heat in self.active_heats:
                self.active_heats.remove(heat)
            self.completed_heats.append(heat)
            self.heats_processed += 1  # Use setter

            process_time = getattr(heat, 'total_process_time', 0)
            if process_time == 0 and hasattr(heat, 'total_process_time'):
                logger.warning(f"Heat {heat.id} has total_process_time of 0")
            elif not hasattr(heat, 'total_process_time'):
                logger.warning(f"Heat {heat.id} missing 'total_process_time' attribute")
            self.total_cycle_time += process_time

            logger.info(f"Heat {heat.id} completed. Total heats processed: {self.heats_processed}")

    ### Helper Methods for Config Access
    def get_unit_config(self, unit_type):
        """Get configuration for a specific unit type."""
        return self.config.get("units", {}).get(unit_type, {})

    def get_bay_config(self, bay_id):
        """Get configuration for a specific bay."""
        return self.config.get("bays", {}).get(bay_id, {})

    def get_grade_properties(self, grade):
        """Get properties for a specific steel grade."""
        return self.config.get("grade_distribution", {}).get(grade, {})

    ### Setup and Process Management
    def setup(self):
        """Set up production units and connections."""
        n_bays = self.config.get("n_bays", 2)

        for bay_id in range(1, n_bays + 1):
            bay_name = f"bay{bay_id}"
            bay_config = self.get_bay_config(bay_name)
            if not bay_config:
                logger.warning(f"No configuration found for bay {bay_name}; using defaults")

            # Create EAF units
            n_eaf = self.config.get("n_eaf_per_bay", 1)
            self.units[bay_name]["EAF"] = []
            for i in range(n_eaf):
                eaf_config = self.get_unit_config("EAF")
                eaf = EnhancedEAFUnit(
                    env=self.env,
                    bay=bay_name,
                    unit_id=i + 1,
                    name=f"EAF_{i+1}",
                    **eaf_config
                )
                self.units[bay_name]["EAF"].append(eaf)
                self.bay_equipment[bay_name]["EAF"].append(eaf)
                self.route_manager.register_unit(eaf, bay_name, "EAF")

            # Create LMF units
            n_lmf = self.config.get("n_lmf_per_bay", self.n_lmf)  # Use instance variable as default
            self.units[bay_name]["LMF"] = []
            for i in range(n_lmf):
                lmf_config = self.get_unit_config("LMF")
                lmf = EnhancedLMFStation(
                    env=self.env,
                    bay=bay_name,
                    unit_id=i + 1,
                    name=f"LMF_{i+1}",
                    **lmf_config
                )
                self.units[bay_name]["LMF"].append(lmf)
                self.bay_equipment[bay_name]["LMF"].append(lmf)
                self.route_manager.register_unit(lmf, bay_name, "LMF")

            # Create Degasser units
            n_degassers = self.config.get("n_degassers_per_bay", self.n_degassers)  # Use instance variable
            self.units[bay_name]["Degasser"] = []
            for i in range(n_degassers):
                degasser_config = self.get_unit_config("Degasser")
                degasser = DegasserUnit(
                    env=self.env,
                    bay=bay_name,
                    unit_id=i + 1,
                    name=f"Degasser_{i+1}",
                    **degasser_config
                )
                self.units[bay_name]["Degasser"].append(degasser)
                self.bay_equipment[bay_name]["Degasser"].append(degasser)
                self.route_manager.register_unit(degasser, bay_name, "Degasser")

            # Create Caster units
            caster_config = self.get_unit_config("Caster")
            n_casters = caster_config.get("capacity", self.n_casters)  # Use 'capacity' from config or default
            self.units[bay_name]["Caster"] = []
            for i in range(n_casters):
                caster = EnhancedCaster(
                    env=self.env,
                    bay=bay_name,
                    unit_id=i + 1,
                    name=f"Caster_{i+1}",
                    min_casting_time=caster_config.get("min_casting_time", 30),  # Default value if not specified
                    critical_temp=caster_config.get("critical_temp", 1400)       # Default value if not specified
                )
                self.units[bay_name]["Caster"].append(caster)
                self.bay_equipment[bay_name]["Caster"].append(caster)
                self.route_manager.register_unit(caster, bay_name, "Caster")

        self._place_equipment_in_bays()
        logger.info("ProductionManager setup complete")

    def process(self):
        """Main process method for ProductionManager."""
        self.setup()
        self.heat_generator = self.env.process(self.generate_heats())
        self.route_processor = self.env.process(self.process_routes())
        
        while True:
            metrics = self.get_metrics()
            if int(self.env.now()) % 60 == 0:  # Log every hour
                logger.info(f"Production status at {self.env.now()}:")
                logger.info(f"  Active heats: {len(self.active_heats)}")
                logger.info(f"  Completed heats: {len(self.completed_heats)}")
                logger.info(f"  Utilization: {metrics['utilization']}")
            yield self.env.timeout(self.config.get("production_manager_interval", 5))

    def _place_equipment_in_bays(self):
        """Place production units in their bays based on configuration."""
        for bay_id, equipment in self.bay_equipment.items():
            bay_config = self.get_bay_config(bay_id)
            
            # Get the bay boundaries from the spatial manager to ensure consistency
            bay = self.spatial_manager.bays.get(bay_id)
            if not bay:
                logger.warning(f"Bay {bay_id} not found in spatial manager")
                continue
                
            # Use actual bay boundaries from the bay object
            top_left = bay.top_left
            bottom_right = bay.bottom_right
            bay_width = bay.width
            bay_height = bay.height
            
            # Add buffer to ensure equipment stays inside bay
            buffer = 10  # Buffer from edges
            
            for unit_type, units in equipment.items():
                for i, unit in enumerate(units):
                    # Calculate position within bay boundaries with buffer
                    # Spread equipment evenly along width
                    x_position = top_left["x"] + buffer + (bay_width - 2*buffer) * (i / (len(units) + 1))
                    # Place in middle of height
                    y_position = top_left["y"] + bay_height / 2
                    
                    position = {
                        "x": x_position,
                        "y": y_position
                    }
                    
                    logger.info(f"Placing {unit_type} {i+1} at position {position} in bay {bay_id}")
                    self.spatial_manager.place_equipment(f"{bay_id}_{unit_type}_{i+1}", unit_type, bay_id, position)
                    unit.position = position

    ### Heat Generation and Routing
    def generate_heats(self):
        """Generate heats according to the configured schedule."""
        heat_interval = self.config.get("heat_interval", 10)  # Adjusted from 'heat_generation_interval'
        max_heats = self.config.get("max_heats", 50)

        while self.heat_counter < max_heats:
            heat = self._create_heat()
            self.heat_counter += 1
            self.generated_heats.append(heat)
            self.active_heats.append(heat)
            initial_route = self.route_manager.get_route_for_heat(heat)
            logger.info(f"Generated heat {heat.id} with grade {heat.grade}, initial route: {[step[1] for step in initial_route]}")
            yield self.env.timeout(heat_interval)

        logger.info(f"Heat generation complete - generated {self.heat_counter} heats")

    def _create_heat(self):
        """Create a new heat with appropriate properties."""
        heat_id = f"H{self.heat_counter + 1:04d}"
        grade_dist = self.config.get("grade_distribution", {"standard": 1})
        selected_grade = random.choices(list(grade_dist.keys()), list(grade_dist.values()), k=1)[0]
        bay_id = f"bay{random.randint(1, self.config.get('n_bays', 2))}"
        grade_props = self.get_grade_properties(selected_grade)
        width = random.randint(grade_props.get("width_min", 900), grade_props.get("width_max", 1900))
        thickness = 250

        heat = Heat(
            id=heat_id,
            grade=selected_grade,
            bay=bay_id,
            start_time=self.env.now(),
            width=width,
            thickness=thickness,
            grade_specific_props=grade_props,
            env=self.env
        )
        return heat

    def process_routes(self):
        """Process routes for active heats."""
        while True:
            for heat in list(self.active_heats):
                if heat.completion_time is not None:
                    self.active_heats.remove(heat)
                    self.completed_heats.append(heat)
                    self.heats_processed += 1
                    continue
                
                if not heat.current_unit:
                    next_step = self.route_manager.get_next_step(heat)
                    if next_step:
                        bay_id, unit_type, unit = next_step
                        if hasattr(unit, "add_heat"):
                            success = unit.add_heat(heat)
                            if success:
                                heat.current_unit = unit
                                logger.info(f"Heat {heat.id} assigned to {unit_type} {unit.unit_id} in bay {bay_id}")
                            else:
                                logger.info(f"Could not assign heat {heat.id} to {unit_type} {unit.unit_id} - unit busy")
                    else:
                        if heat in self.active_heats:
                            self.active_heats.remove(heat)
                            heat.completion_time = self.env.now()
                            cycle_time = heat.completion_time - heat.start_time
                            self.total_cycle_time += cycle_time
                            self.completed_heats.append(heat)
                            self.heats_processed += 1
                            logger.info(f"Heat {heat.id} completed its route, cycle time: {cycle_time:.2f}")
            
            yield self.env.timeout(1)

    ### Metrics
    def get_metrics(self):
        """Calculate current simulation metrics."""
        metrics = {
            "heats_generated": self.heat_counter,
            "heats_active": len(self.active_heats),
            "heats_completed": len(self.completed_heats),
            "current_time": self.env.now()
        }

        equipment_utilization = defaultdict(lambda: {"busy": 0, "total": 0})
        for bay_id, equipment in self.bay_equipment.items():
            for unit_type, units in equipment.items():
                for unit in units:
                    equipment_utilization[unit_type]["total"] += 1
                    if getattr(unit, "status", "idle") == "processing":
                        equipment_utilization[unit_type]["busy"] += 1

        utilization = {}
        for unit_type, counts in equipment_utilization.items():
            utilization[unit_type] = (counts["busy"] / counts["total"] * 100) if counts["total"] > 0 else 0
        metrics["utilization"] = utilization

        metrics["throughput"] = len(self.completed_heats) / (self.env.now() / 60) if self.env.now() > 0 else 0
        return metrics