import json
import logging
import os
import copy

logger = logging.getLogger(__name__)

class SimulationConfig:
    """
    Manages configuration for the steel plant simulation.
    
    This class handles loading, saving, and accessing configuration parameters
    for the simulation, including bay layouts, equipment settings, and
    processing requirements.
    """
    
    def __init__(self, config_path=None):
        """
        Initialize the configuration.
        
        Args:
            config_path: Path to configuration file
        """
        self.config_path = config_path
        self.config = self._get_default_config()
        self.last_config_path = "last_config.json"
        
        # Try to load configuration from different sources with fallbacks
        if config_path and os.path.exists(config_path):
            self.load_config(config_path)
        elif os.path.exists(self.last_config_path):
            logger.info(f"Loading last used configuration from {self.last_config_path}")
            self.load_config(self.last_config_path)
            # Update the config_path to point to the last config
            self.config_path = self.last_config_path
    
    def _get_default_config(self):
        """Get the default simulation configuration."""
        return {
            # Simulation parameters
            "simulation_time": 1440,  # 24 hours in minutes
            "heat_generation_interval": 60,  # Generate a heat every 60 minutes
            "max_heats": 50,  # Maximum number of heats to generate
            
            # Plant configuration
            "n_bays": 2,
            "n_eaf_per_bay": 1,
            "n_lmf_per_bay": 2,
            "n_degassers_per_bay": 1,
            "n_casters_per_bay": 1,
            "n_ladles": 12,
            "n_ladle_cars": 3,
            
            # Equipment parameters
            "bays": {
                "bay1": {
                    "top_left": {"x": 100, "y": 100},
                    "bottom_right": {"x": 300, "y": 300},
                    "crane_paths": [
                        {"start_x": 120, "end_x": 280, "y": 150},
                        {"start_x": 120, "end_x": 280, "y": 250}
                    ]
                },
                "bay2": {
                    "top_left": {"x": 300, "y": 100},
                    "bottom_right": {"x": 500, "y": 300},
                    "crane_paths": [
                        {"start_x": 320, "end_x": 480, "y": 150},
                        {"start_x": 320, "end_x": 480, "y": 250}
                    ]
                }
            },
            "units": {
                "EAF": {
                    "process_time": 50,
                    "min_process_time": 50,
                    "capacity": 1
                },
                "LMF": {
                    "process_time": 30,
                    "min_process_time": 30,
                    "capacity": 1
                },
                "Degasser": {
                    "process_time": 40,
                    "capacity": 1
                },
                "Caster": {
                    "process_time": 20,
                    "capacity": 1,
                    "turnaround_time": 20,
                    "max_sequence": 7,
                    "flow_interruption_threshold": 15  # Minutes between heats that triggers turnaround
                }
            },
            
            # Steel grade properties
            "grade_distribution": {
                "standard": 0.60,      # 60% Standard Steel
                "high_clean": 0.20,    # 20% High Clean
                "decarb": 0.15,        # 15% Decarburized
                "temp_sensitive": 0.05  # 5% Temperature Sensitive
            },
            "grade_properties": {
                "standard": {
                    "requires_degasser": False,
                    "eaf_time": 50,
                    "lmf_time": 30,
                    "caster_time": 20,
                    "min_eaf_time": 50,
                    "min_lmf_time": 30,
                    "min_temperature": 1500,
                    "width_min": 900,
                    "width_max": 1900
                },
                "high_clean": {
                    "requires_degasser": True,
                    "eaf_time": 68,
                    "lmf_time": 45,
                    "degasser_time": 40,
                    "caster_time": 25,
                    "min_eaf_time": 60,
                    "min_lmf_time": 40,
                    "min_degasser_time": 35,
                    "min_temperature": 1520,
                    "width_min": 1000,
                    "width_max": 1800
                },
                "decarb": {
                    "requires_degasser": True,
                    "eaf_time": 62,
                    "lmf_time": 40,
                    "degasser_time": 45,
                    "caster_time": 22,
                    "min_eaf_time": 55,
                    "min_lmf_time": 35,
                    "min_degasser_time": 40,
                    "min_temperature": 1510,
                    "width_min": 900,
                    "width_max": 1700
                },
                "temp_sensitive": {
                    "requires_degasser": False,
                    "eaf_time": 55,
                    "lmf_time": 35,
                    "caster_time": 30,
                    "min_eaf_time": 50,
                    "min_lmf_time": 30,
                    "min_temperature": 1540,
                    "temperature_loss_rate": 2.0,
                    "width_min": 1100,
                    "width_max": 1600
                }
            },
            "grade_routes": {
                "standard": ["EAF", "LMF", "Caster"],
                "high_clean": ["EAF", "LMF", "Degasser", "Caster"],
                "decarb": ["EAF", "LMF", "Degasser", "Caster"],
                "temp_sensitive": ["EAF", "LMF", "Caster"]
            },
            
            # Ladle parameters
            "ladle_warming_time": 15,  # Minutes to warm a ladle
            "ladle_max_heats": 5,      # Max heats before ladle needs maintenance
            
            # Transport parameters
            "ladle_car_speed": 150,    # Units per minute
            "crane_speed": 100,        # Units per minute
            "loading_time": 5,         # Minutes to load a ladle
            "unloading_time": 5,       # Minutes to unload a ladle
            
            # Bay connections (for ladle car routing)
            "bay_connections": [
                {"from": "bay1", "to": "bay2", "distance": 200, "travel_time": 10}
            ],
            
            # Reporting parameters
            "metrics_reporting_interval": 60,  # Report metrics every 60 minutes
            
            # Visualization parameters
            "visualization": {
                "bay_color": "#e6f7ff",        # Light blue for bays
                "eaf_color": "#ff7f0e",        # Orange for EAF
                "lmf_color": "#1f77b4",        # Blue for LMF
                "degasser_color": "#2ca02c",   # Green for Degasser
                "caster_color": "#d62728",     # Red for Caster
                "ladle_car_color": "#9467bd",  # Purple for ladle cars
                "crane_color": "#8c564b",      # Brown for cranes
                "scale_factor": 0.5            # Scaling factor for visualization
            },
            
            # Background settings
            "background_type": "image",  # Default to 'image' instead of 'grid' or 'pdf'
            "background_image": None,    # Path to background image file
            "cad_file_path": None,      # CAD file path (PDF, DXF, etc.)
        }
    
    def load_config(self, config_path):
        """
        Load configuration from a file.
        
        Args:
            config_path: Path to configuration file
            
        Returns:
            dict: Loaded configuration
        """
        try:
            with open(config_path, 'r') as f:
                loaded_config = json.load(f)
                
            # Update configuration
            self.config.update(loaded_config)
            logger.info(f"Configuration loaded from {config_path}")
            
            # Save this as the last used configuration
            self.save_config(self.last_config_path)
            
            return self.config
        except Exception as e:
            logger.error(f"Error loading configuration: {str(e)}")
            return self.config
    
    def save_config(self, config_path=None):
        """
        Save configuration to a file.
        
        Args:
            config_path: Path to save configuration file (defaults to self.config_path)
            
        Returns:
            bool: True if save was successful
        """
        save_path = config_path or self.config_path
        if not save_path:
            logger.error("No config path specified for saving")
            return False
            
        try:
            # Create parent directory if it doesn't exist
            dir_path = os.path.dirname(save_path)
            if dir_path and not os.path.exists(dir_path):
                os.makedirs(dir_path)
                
            with open(save_path, 'w') as f:
                json.dump(self.config, f, indent=4)
                
            logger.info(f"Configuration saved to {save_path}")
            
            # If this isn't the last_config_path, also save to last_config
            if save_path != self.last_config_path:
                with open(self.last_config_path, 'w') as f:
                    json.dump(self.config, f, indent=4)
                logger.info(f"Configuration backed up to {self.last_config_path}")
                
            return True
        except Exception as e:
            logger.error(f"Error saving configuration: {str(e)}")
            return False
    
    def get(self, key, default=None):
        """
        Get a configuration value.
        
        Args:
            key: Configuration key
            default: Default value if key not found
            
        Returns:
            Value for the key or default
        """
        return self.config.get(key, default)
    
    def set(self, key, value):
        """
        Set a configuration value.
        
        Args:
            key: Configuration key
            value: Value to set
            
        Returns:
            bool: True if value was set
        """
        try:
            self.config[key] = value
            # Auto-save when settings change
            self.save_config(self.last_config_path)
            return True
        except Exception as e:
            logger.error(f"Error setting configuration: {str(e)}")
            return False
    
    def get_bay_config(self, bay_id):
        """
        Get configuration for a specific bay.
        
        Args:
            bay_id: Bay identifier
            
        Returns:
            dict: Bay configuration or None
        """
        return self.config.get("bays", {}).get(bay_id)
    
    def get_unit_config(self, unit_type):
        """
        Get configuration for a specific unit type.
        
        Args:
            unit_type: Unit type (EAF, LMF, etc.)
            
        Returns:
            dict: Unit configuration or None
        """
        return self.config.get("units", {}).get(unit_type)
    
    def get_grade_properties(self, grade):
        """
        Get properties for a specific steel grade.
        
        Args:
            grade: Steel grade identifier
            
        Returns:
            dict: Grade properties or None
        """
        return self.config.get("grade_properties", {}).get(grade)
    
    def get_grade_route(self, grade):
        """
        Get the processing route for a specific steel grade.
        
        Args:
            grade: Steel grade identifier
            
        Returns:
            list: Ordered list of equipment types or None
        """
        return self.config.get("grade_routes", {}).get(grade)