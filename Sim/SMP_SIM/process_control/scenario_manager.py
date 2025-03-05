import logging

logger = logging.getLogger(__name__)

class ScenarioManager:
    """
    Manages different operating scenarios for the steel plant.
    Each scenario can have different routing rules, equipment availability, etc.
    """
    def __init__(self, config):
        self.config = config
        self.current_scenario = config.get("scenarios", {}).get("default", {}).get("routing", "standard")
        
        # Track all defined scenarios for reference
        self.scenarios = config.get("scenarios", {
            "default": { "routing": "standard" },
            "maintenance": { "routing": "maintenance_mode" }
        })
        
        logger.info(f"ScenarioManager initialized with scenario: {self.current_scenario}")
    
    def set_current_scenario(self, scenario_name):
        """
        Set the current operating scenario.
        
        Args:
            scenario_name: Name of the scenario to activate
        """
        scenarios = self.config.get("scenarios", {})
        if scenario_name in scenarios:
            self.current_scenario = scenarios[scenario_name].get("routing", "standard")
            logger.info(f"Scenario set to {scenario_name} with routing '{self.current_scenario}'")
        else:
            logger.warning(f"Scenario {scenario_name} not found. Using default.")
    
    def get_routing(self):
        """Get the current routing mode."""
        return self.current_scenario
    
    def get_available_scenarios(self):
        """Get list of all available scenarios."""
        return list(self.scenarios.keys())
    
    def get_scenario_description(self, scenario_name):
        """Get description of a particular scenario."""
        if scenario_name not in self.scenarios:
            return "Unknown scenario"
            
        descriptions = {
            "default": "Standard production routing",
            "maintenance": "Maintenance mode with simplified routing"
        }
        
        return descriptions.get(scenario_name, "Custom scenario")