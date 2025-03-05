import logging
import uuid

# Configure logger
logger = logging.getLogger(__name__)

class Heat:
    """
    Represents a batch of molten steel (a "heat") in the steel plant.

    A heat is produced by the Electric Arc Furnace (EAF), processed through various equipment
    (e.g., Ladle Metallurgy Furnace, Degasser), and eventually cast into slabs by the Caster.
    """

    def __init__(self, id=None, grade="standard", bay=None, start_time=0,
                 width=1500, thickness=250, grade_specific_props=None, env=None):
        """
        Initialize a Heat instance.

        Args:
            id (str, optional): Unique identifier for the heat. Defaults to a truncated UUID.
            grade (str, optional): Steel grade identifier (e.g., "standard"). Defaults to "standard".
            bay (str, optional): Initial bay location. Defaults to None.
            start_time (float, optional): Time when the heat was generated. Defaults to 0.
            width (int, optional): Width of slabs in millimeters. Defaults to 1500.
            thickness (int, optional): Thickness of slabs in millimeters. Defaults to 250.
            grade_specific_props (dict, optional): Grade-specific processing properties. Defaults to None.
            env (object, optional): Simulation environment object. Defaults to None.
        """
        self.id = id or str(uuid.uuid4())[:8]  # Generate a unique 8-character ID if not provided
        self.grade = grade
        self.bay = bay
        self.start_time = start_time
        self.width = width
        self.thickness = thickness
        self.grade_specific_props = grade_specific_props or {}  # Default to empty dict if None
        self.env = env
        self.process_history = []  # List to store processing steps
        self.current_location = None
        self.current_unit = None
        self.creation_time = start_time
        self.completion_time = None
        self.temperature = self.get_initial_temperature()
        self.last_temp_update = start_time

        logger.info(f"Heat {self.id} created with grade {self.grade}, width {self.width}mm")

    def get_initial_temperature(self):
        """
        Determine the initial temperature of the heat based on its grade.

        Returns:
            float: Initial temperature in degrees Celsius.
        """
        temp = 1650  # Default temperature from EAF tapping
        if self.grade == "high_clean":
            temp = 1630  # Lower temp for clean steel
        elif self.grade == "temp_sensitive":
            temp = 1600  # Lower for temperature-sensitive grades
        return temp

    def update_temperature(self, current_time):
        """
        Update the heat's temperature based on elapsed time since the last update.

        Args:
            current_time (float): Current simulation time in minutes.

        Returns:
            float: Updated temperature in degrees Celsius.
        """
        if current_time <= self.last_temp_update:
            return self.temperature

        # Define cooling rate based on grade (degrees Celsius per minute)
        loss_rate = 1.5  # Default cooling rate
        if self.grade == "high_clean":
            loss_rate = 1.2
        elif self.grade == "temp_sensitive":
            loss_rate = 2.0

        elapsed_minutes = current_time - self.last_temp_update
        temp_drop = elapsed_minutes * loss_rate
        self.temperature -= temp_drop
        self.last_temp_update = current_time

        if self.temperature < 1480:
            logger.warning(f"Heat {self.id} temperature critically low: {self.temperature:.1f}°C")

        return self.temperature

    def record_process(self, unit_type, start_time, end_time, bay=None):
        """
        Record a processing step in the heat's history.

        Args:
            unit_type (str): Type of unit (e.g., "EAF", "LMF", "Caster").
            start_time (float): Time when processing started.
            end_time (float): Time when processing ended.
            bay (str, optional): Bay where processing occurred. Defaults to None.
        """
        duration = end_time - start_time
        self.process_history.append({
            "unit_type": unit_type,
            "start_time": start_time,
            "end_time": end_time,
            "duration": duration,
            "bay": bay
        })
        self.current_location = bay
        if unit_type == "Caster":
            self.completion_time = end_time
            logger.info(f"Heat {self.id} completed at time {end_time}")

    def get_total_time_at_unit(self, unit_type):
        """
        Calculate the total time spent at a specific unit type.

        Args:
            unit_type (str): Type of unit to calculate total time for (e.g., "LMF").

        Returns:
            float: Total time spent at the specified unit type in minutes.
        """
        return sum(entry["duration"] for entry in self.process_history if entry["unit_type"] == unit_type)