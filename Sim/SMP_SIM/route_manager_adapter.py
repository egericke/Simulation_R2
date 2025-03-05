import logging

class ProcessRouteManagerAdapter:
    """
    Adapter for ProcessRouteManager to provide compatibility with
    the methods expected by ProductionManager.
    """
    def __init__(self, config, spatial_manager, steel_grades):
        """
        Initialize the adapter.
        
        Args:
            config: Configuration object
            spatial_manager: Spatial manager
            steel_grades: Steel grade information
        """
        self.config = config
        self.spatial_manager = spatial_manager
        self.steel_grades = steel_grades
        
        # Track registered units
        self.units = {}
        for bay_id in range(1, config.get("n_bays", 2) + 1):
            bay_name = f"bay{bay_id}"
            self.units[bay_name] = {
                "EAF": [],
                "LMF": [],
                "Degasser": [],
                "Caster": []
            }
        
        # Initialize route manager
        self.route_queue = {}  # Heat ID -> route information
        
        # Will store heat -> current route step mapping
        self.heat_routes = {}  # Heat ID -> (current_step, total_steps, route)
        
        self.logger = logging.getLogger(__name__)
        self.logger.info("ProcessRouteManager initialized")
    
    def register_unit(self, unit, bay_name, unit_type):
        """
        Register a unit with the route manager.
        
        Args:
            unit: Unit to register
            bay_name: Bay where the unit is located
            unit_type: Type of unit (EAF, LMF, etc.)
        """
        if bay_name not in self.units:
            self.units[bay_name] = {}
        
        if unit_type not in self.units[bay_name]:
            self.units[bay_name][unit_type] = []
        
        self.units[bay_name][unit_type].append(unit)
        self.logger.info(f"Registered {unit_type} in {bay_name}")
    
    def get_route_for_heat(self, heat):
        """
        Get the processing route for a heat.
        
        Args:
            heat: Heat to route
            
        Returns:
            list: List of (bay, unit_type, unit) tuples
        """
        # Determine route based on grade
        grade_routes = self.config.get("grade_routes", {})
        route_types = grade_routes.get(heat.grade, ["EAF", "LMF", "Caster"])
        
        # Create actual route with specific units
        route = []
        
        # Assign to units in the heat's bay when possible
        for unit_type in route_types:
            # First try to find unit in the heat's bay
            if heat.bay in self.units and unit_type in self.units[heat.bay] and self.units[heat.bay][unit_type]:
                # Find least busy unit of this type
                unit = min(self.units[heat.bay][unit_type], key=lambda u: getattr(u, 'utilization', 0) if hasattr(u, 'utilization') else 0)
                route.append((heat.bay, unit_type, unit))
            else:
                # If no unit in the heat's bay, find one in any bay
                for bay, bay_units in self.units.items():
                    if unit_type in bay_units and bay_units[unit_type]:
                        unit = min(bay_units[unit_type], key=lambda u: getattr(u, 'utilization', 0) if hasattr(u, 'utilization') else 0)
                        route.append((bay, unit_type, unit))
                        break
        
        # Store this heat's route
        self.heat_routes[heat.id] = (0, len(route), route)
        
        return route
    
    def get_next_step(self, heat):
        """
        Get the next processing step for a heat.
        
        Args:
            heat: Heat to route
            
        Returns:
            tuple: (bay, unit_type, unit) or None if route complete
        """
        if heat.id not in self.heat_routes:
            # First time seeing this heat, get its route
            route = self.get_route_for_heat(heat)
            return route[0] if route else None
        
        # Get current position in route
        current_step, total_steps, route = self.heat_routes[heat.id]
        
        # If we've processed all steps, return None
        if current_step >= total_steps - 1:
            # Route complete
            del self.heat_routes[heat.id]
            return None
        
        # Move to next step
        next_step = current_step + 1
        self.heat_routes[heat.id] = (next_step, total_steps, route)
        
        # Return the next location in the route
        return route[next_step]