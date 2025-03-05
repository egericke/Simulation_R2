# process_control/heat_tracker.py
import logging

logger = logging.getLogger(__name__)

class HeatTracker:
    def __init__(self):
        # Dictionary to store heat data: heat_id -> {heat, current_unit, current_bay, route, status}
        self.heats = {}
        logger.info("HeatTracker initialized")

    def add_heat(self, heat, route):
        """Add a new heat with its route."""
        self.heats[heat.id] = {
            "heat": heat,
            "current_unit": None,  # No unit assigned yet
            "current_bay": heat.bay,  # Initial bay from heat object
            "route": route,  # List of (bay, process, unit) tuples
            "status": "pending"  # Initial status
        }
        logger.info(f"Added heat {heat.id} to HeatTracker with route: {[step[1] for step in route]}")

    def update_heat(self, heat_id, unit=None, bay=None, status=None):
        """Update heat state if it exists."""
        if heat_id in self.heats:
            if unit is not None:
                self.heats[heat_id]["current_unit"] = unit
            if bay is not None:
                self.heats[heat_id]["current_bay"] = bay
            if status is not None:
                self.heats[heat_id]["status"] = status
            logger.debug(f"Updated heat {heat.id}: unit={unit}, bay={bay}, status={status}")
            return True
        logger.warning(f"Heat {heat_id} not found in HeatTracker")
        return False

    def get_next_step(self, heat_id):
        """Get the next route step for a heat."""
        heat_data = self.heats.get(heat_id)
        if not heat_data or heat_data["status"] == "completed":
            return None
        route = heat_data["route"]
        current_idx = next((i for i, (bay, _, unit) in enumerate(route) 
                            if unit == heat_data["current_unit"]), -1)
        next_step = route[current_idx + 1] if current_idx + 1 < len(route) else None
        logger.debug(f"Next step for heat {heat_id}: {next_step}")
        return next_step