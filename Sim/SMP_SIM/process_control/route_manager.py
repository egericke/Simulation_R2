import logging
from collections import deque
from typing import Dict, List, Tuple, Optional

# Configure logger
logger = logging.getLogger(__name__)

class ProcessRouteManager:
    """
    Manages the routing of heats through a steel plant based on grade requirements.

    Determines the sequence of equipment (e.g., EAF, LMF, Degasser, Caster) a heat must visit,
    ensures metallurgical constraints are met, and optimizes unit selection for efficiency.
    """

    def __init__(self, config: Dict, units: Dict[str, List], steel_grades: Optional[Dict] = None, env=None):
        """
        Initialize the RouteManager.

        Args:
            config (dict): Configuration with grade-specific routes and constraints.
                           Example: {"grade_routes": {"standard": ["EAF", "LMF", "Caster"]},
                                     "min_process_times": {"LMF": 30}}
            units (dict): Available units by type. Example: {"EAF": [eaf1, eaf2], "LMF": [lmf1]}
            steel_grades (dict, optional): Grade-specific properties (e.g., chemistry constraints).
            env (object, optional): Simulation environment for time tracking.
        """
        self.config = config
        self.units = units  # {unit_type: [unit_objects]}
        self.steel_grades = steel_grades or {}
        self.env = env
        self.heat_routes: Dict[str, Dict] = {}  # {heat_id: {"route": [(unit_type, unit)], "current_step": int, "complete": bool}}

        # Validate configuration
        if "grade_routes" not in config:
            raise ValueError("Config must include 'grade_routes' mapping grades to equipment sequences")
        if not all(isinstance(route, list) for route in config["grade_routes"].values()):
            raise ValueError("All grade routes must be lists of unit types")

        logger.info("RouteManager initialized with %d grade routes", len(config["grade_routes"]))

    def get_route_for_heat(self, heat) -> List[Tuple[str, object]]:
        """
        Determine the processing route for a heat based on its grade.

        Args:
            heat (Heat): Heat object with grade and id attributes.

        Returns:
            list: Ordered list of (unit_type, unit) tuples representing the route.
        """
        if heat.id in self.heat_routes:
            return self.heat_routes[heat.id]["route"]

        grade = heat.grade
        route_steps = self.config["grade_routes"].get(grade, [])

        # Fallback to default route if grade-specific route is missing
        if not route_steps:
            logger.warning(f"No route defined for grade {grade}, using default route")
            route_steps = ["EAF", "LMF", "Caster"]

        route = []
        for step in route_steps:
            unit = self.select_unit(step, heat)
            if unit:
                route.append((step, unit))
            else:
                logger.error(f"No available unit for {step} in route for heat {heat.id}")
                return []

        self.heat_routes[heat.id] = {
            "route": route,
            "current_step": 0,
            "complete": False
        }
        route_summary = [(step, unit.unit_id) for step, unit in route]
        logger.info(f"Route for heat {heat.id} (grade {grade}): {route_summary}")
        return route

    def select_unit(self, unit_type: str, heat) -> Optional[object]:
        """
        Select the most suitable unit of the specified type for the heat.

        Args:
            unit_type (str): Type of unit (e.g., "EAF", "Degasser").
            heat (Heat): Heat object for context-specific selection.

        Returns:
            Unit: Selected unit object, or None if unavailable.
        """
        available_units = self.units.get(unit_type, [])
        if not available_units:
            logger.warning(f"No units available for {unit_type}")
            return None

        # Advanced selection: prioritize units based on queue length and grade compatibility
        for unit in sorted(available_units, key=lambda u: len(u.heat_queue) if hasattr(u, "heat_queue") else 0):
            if self.is_unit_compatible(unit, heat):
                return unit

        logger.warning(f"No compatible unit found for {unit_type} and heat {heat.id}")
        return None

    def is_unit_compatible(self, unit, heat) -> bool:
        """
        Check if a unit is compatible with a heat's grade requirements.

        Args:
            unit: Unit object with properties like capabilities.
            heat (Heat): Heat object with grade.

        Returns:
            bool: True if compatible, False otherwise.
        """
        grade = heat.grade
        grade_specs = self.steel_grades.get(grade, {})
        required_capabilities = grade_specs.get("required_capabilities", [])
        unit_capabilities = getattr(unit, "capabilities", [])  # Assume units have capability list

        return all(cap in unit_capabilities for cap in required_capabilities)

    def get_next_step(self, heat) -> Optional[Tuple[str, object]]:
        """
        Get the next processing step for a heat.

        Args:
            heat (Heat): Heat object.

        Returns:
            tuple: (unit_type, unit) for the next step, or None if complete.
        """
        if heat.id not in self.heat_routes:
            self.get_route_for_heat(heat)

        route_info = self.heat_routes[heat.id]
        if route_info["complete"]:
            return None

        current_step = route_info["current_step"]
        if current_step >= len(route_info["route"]):
            route_info["complete"] = True
            logger.info(f"Heat {heat.id} completed its route")
            return None

        return route_info["route"][current_step]

    def advance_heat(self, heat) -> Optional[Tuple[str, object]]:
        """
        Advance a heat to its next processing step.

        Args:
            heat (Heat): Heat object.

        Returns:
            tuple: (unit_type, unit) for the next step, or None if complete.
        """
        if heat.id not in self.heat_routes:
            self.get_route_for_heat(heat)

        route_info = self.heat_routes[heat.id]
        route_info["current_step"] += 1
        next_step = self.get_next_step(heat)
        if next_step:
            logger.debug(f"Heat {heat.id} advanced to {next_step[0]} (unit {next_step[1].unit_id})")
        return next_step

    def is_ready_for_caster(self, heat) -> bool:
        """
        Check if a heat meets minimum processing requirements for casting.

        Args:
            heat (Heat): Heat object with processing history.

        Returns:
            bool: True if ready for casting, False otherwise.
        """
        grade = heat.grade
        required_steps = self.config["grade_routes"].get(grade, [])
        min_times = self.config.get("min_process_times", {})

        for step in required_steps:
            if step == "Caster":
                continue
            min_time = min_times.get(step, 0)
            total_time = heat.get_total_time_at_unit(step)  # Assumes Heat has this method
            if total_time < min_time:
                logger.warning(f"Heat {heat.id} not ready: {step} time {total_time} < {min_time}")
                return False

        logger.info(f"Heat {heat.id} is ready for casting")
        return True

    def plan_path(self, heat, from_unit, to_unit) -> Dict:
        """
        Plan a path for a heat between units.

        Args:
            heat (Heat): Heat being moved.
            from_unit (Unit): Starting unit.
            to_unit (Unit): Destination unit.

        Returns:
            dict: {"waypoints": list of positions, "travel_time": float}
        """
        # Simplified path planning; in reality, this would use a spatial manager
        waypoints = [from_unit.position, to_unit.position]  # Assumes units have position
        base_time = 10  # minutes
        # Adjust travel time based on heat properties (e.g., weight)
        travel_time = base_time * (1 + getattr(heat, "weight", 1.0) / 100)
        logger.debug(f"Planned path for heat {heat.id}: {len(waypoints)} waypoints, {travel_time:.1f} min")
        return {"waypoints": waypoints, "travel_time": travel_time}

    def reset_heat(self, heat_id: str) -> None:
        """
        Reset a heat's route status (e.g., for rerouting or restart).

        Args:
            heat_id (str): ID of the heat to reset.
        """
        if heat_id in self.heat_routes:
            self.heat_routes[heat_id] = {"route": [], "current_step": 0, "complete": False}
            logger.info(f"Reset route for heat {heat_id}")