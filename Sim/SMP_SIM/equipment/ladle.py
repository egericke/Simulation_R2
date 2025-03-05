import salabim as sim
import logging

logger = logging.getLogger(__name__)

class Ladle(sim.Component):
    def __init__(self, id, env, warming_time=10, bay=None, capacity=150, **kwargs):
        """
        Initialize a ladle.

        Args:
            id: Unique identifier for the ladle.
            env: Simulation environment.
            warming_time: Time required to warm the ladle (default: 10).
            bay: Initial bay location (optional).
            capacity: Maximum heat capacity in tons (default: 150).
        """
        super().__init__(env=env, name=f"Ladle_{id}", **kwargs)
        self.id = id
        self.env = env
        self.warming_time = warming_time
        self.location = bay
        self.capacity = capacity
        self.status = "available"  # available, in_use, warming, maintenance
        self.current_heat = None
        self.current_grade = None
        self.temperature = 20  # Ambient temperature in °C
        self.wear_level = 0.0
        self.total_heats_processed = 0
        self.total_warming_time = 0
        self.maintenance_count = 0
        self.last_update_time = env.now()
        logger.info(f"Ladle {self.id} initialized at {bay}")

    def update_temperature(self, current_time):
        """
        Update the ladle's temperature based on time elapsed.

        Args:
            current_time: Current simulation time.
        """
        if self.status == "in_use" and self.temperature > 20:
            time_elapsed = current_time - self.last_update_time
            self.temperature -= 0.1 * time_elapsed  # Cooling rate: 0.1°C per minute
            self.temperature = max(self.temperature, 20)  # Minimum ambient temperature
            self.last_update_time = current_time
            logger.debug(f"Ladle {self.id} temperature updated to {self.temperature:.1f}°C")

    def assign(self, heat):
        """
        Assign a heat to the ladle.

        Args:
            heat: Heat object to assign.
        """
        if self.status == "available":
            self.current_heat = heat
            self.current_grade = heat.grade if hasattr(heat, "grade") else None
            self.status = "in_use"
            self.temperature = 1600  # Assume heat brings ladle to high temp
            self.last_update_time = self.env.now()
            self.total_heats_processed += 1
            logger.info(f"Ladle {self.id} assigned heat {heat.id}")

    def release(self):
        """Release the heat and start warming cycle."""
        if self.status == "in_use":
            self.current_heat = None
            self.current_grade = None
            self.status = "warming"
            self.activate(process=self.warm_up)
            logger.info(f"Ladle {self.id} released heat, starting warming")

    def warm_up(self):
        """Process to warm the ladle."""
        yield self.env.timeout(self.warming_time)
        self.status = "available"
        self.total_warming_time += self.warming_time
        self.temperature = 20  # Reset to ambient after warming
        logger.info(f"Ladle {self.id} warmed up, now available")

    def check_availability(self, required_grade=None):
        """
        Check if the ladle is available and suitable.

        Args:
            required_grade: Required steel grade (optional).

        Returns:
            bool: True if available and suitable.
        """
        return self.status == "available" and (required_grade is None or self.current_grade == required_grade)

    def needs_maintenance(self):
        """Check if maintenance is needed based on wear."""
        return self.wear_level >= 0.9  # Arbitrary threshold

    def perform_maintenance(self):
        """Perform maintenance and return duration."""
        self.status = "maintenance"
        self.wear_level = 0.0
        self.maintenance_count += 1
        maintenance_time = 30  # Fixed maintenance time
        logger.info(f"Ladle {self.id} undergoing maintenance")
        return maintenance_time