import logging

logger = logging.getLogger(__name__)

class SteelGrade:
    """
    Represents a steel grade with specific processing requirements.
    
    Different steel grades require different equipment, process times,
    and have different physical properties.
    """
    
    def __init__(self, grade_id, name, properties=None):
        """
        Initialize a steel grade.
        
        Args:
            grade_id: Unique identifier for the grade (e.g., "standard")
            name: Human-readable name (e.g., "Standard Carbon Steel")
            properties: Dict of grade-specific properties
        """
        self.grade_id = grade_id
        self.name = name
        self.properties = properties or {}
        
        # Set default properties if not provided
        self._set_default_properties()
    
    def _set_default_properties(self):
        """Set default properties based on grade if not explicitly provided."""
        default_props = {
            # Processing requirements
            "requires_eaf": True,  # All grades need EAF processing
            "requires_lmf": True,  # All grades need LMF processing
            "requires_degasser": self.grade_id in ["high_clean", "decarb"],  # Some grades need degassing
            "requires_caster": True,  # All grades are cast
            
            # Process times (in minutes)
            "eaf_time": 50,  # Default EAF processing time
            "lmf_time": 30,  # Default LMF processing time
            "degasser_time": 40,  # Default degasser time
            "caster_time": 20,  # Default caster time
            
            # Minimum process times (cannot go below these)
            "min_eaf_time": 50,
            "min_lmf_time": 30,
            "min_degasser_time": 40,
            
            # Physical properties
            "min_temperature": 1500,  # Minimum temperature (°C)
            "max_temperature": 1650,  # Maximum temperature (°C)
            "temperature_loss_rate": 1.5,  # Temperature loss per minute (°C)
            
            # Caster-specific properties
            "min_sequence_length": 1,  # Minimum sequence length
            "max_sequence_length": 7,  # Maximum sequence length
            "width_min": 900,   # Minimum width (mm)
            "width_max": 1900,  # Maximum width (mm)
        }
        
        # Grade-specific overrides
        grade_overrides = {
            "standard": {
                "requires_degasser": False,
                "eaf_time": 50,
                "lmf_time": 30,
                "caster_time": 20,
            },
            "high_clean": {
                "requires_degasser": True,
                "eaf_time": 68,  # Longer EAF time for high clean grades
                "lmf_time": 45,
                "degasser_time": 45,
                "caster_time": 25,
                "temperature_loss_rate": 1.2,  # Slower temperature loss
            },
            "decarb": {
                "requires_degasser": True,
                "eaf_time": 62,
                "lmf_time": 40,
                "degasser_time": 50,  # Longer degassing for decarb grades
                "caster_time": 22,
            },
            "temp_sensitive": {
                "requires_degasser": False,  # Doesn't require degassing
                "eaf_time": 55,
                "lmf_time": 35,
                "caster_time": 30,  # Slower casting for temp sensitive
                "min_temperature": 1520,  # Higher minimum temperature
                "max_temperature": 1580,  # Lower maximum temperature (tighter range)
                "temperature_loss_rate": 2.0,  # Faster temperature loss
            }
        }
        
        # Apply default properties
        for key, value in default_props.items():
            if key not in self.properties:
                self.properties[key] = value
                
        # Apply grade-specific overrides
        if self.grade_id in grade_overrides:
            for key, value in grade_overrides[self.grade_id].items():
                self.properties[key] = value
    
    def requires_equipment(self, equipment_type):
        """
        Check if this grade requires processing in the specified equipment.
        
        Args:
            equipment_type: Type of equipment (EAF, LMF, etc.)
            
        Returns:
            bool: True if the grade requires this equipment
        """
        requirement_property = f"requires_{equipment_type.lower()}"
        return self.properties.get(requirement_property, False)
    
    def get_process_time(self, equipment_type):
        """
        Get the process time for this grade on the specified equipment.
        
        Args:
            equipment_type: Type of equipment (EAF, LMF, etc.)
            
        Returns:
            float: Process time in minutes
        """
        time_property = f"{equipment_type.lower()}_time"
        return self.properties.get(time_property, 0)
    
    def get_min_process_time(self, equipment_type):
        """
        Get the minimum process time for this grade on the specified equipment.
        
        Args:
            equipment_type: Type of equipment (EAF, LMF, etc.)
            
        Returns:
            float: Minimum process time in minutes
        """
        min_time_property = f"min_{equipment_type.lower()}_time"
        return self.properties.get(min_time_property, 0)
    
    @staticmethod
    def create_from_config(config):
        """
        Create steel grade objects from configuration.
        
        Args:
            config: Configuration dict with grade definitions
            
        Returns:
            dict: Map of grade_id to SteelGrade object
        """
        grades = {}
        
        # Get grade distribution from config
        grade_dist = config.get("grade_distribution", {})
        
        # Create a grade object for each grade in the distribution
        for grade_id, ratio in grade_dist.items():
            # Create a descriptive name
            name = grade_id.replace('_', ' ').title()
            
            # Get grade-specific properties from config if available
            properties = config.get("grade_properties", {}).get(grade_id, {})
            
            # Create the grade object
            grades[grade_id] = SteelGrade(grade_id, name, properties)
            
        return grades