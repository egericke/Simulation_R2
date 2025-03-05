import logging
import salabim as sim
from equipment.ladle import Ladle

logger = logging.getLogger(__name__)

class LadleManager(sim.Component):
    """
    Manages the fleet of ladles, handling assignment, availability and warming.
    """
    def __init__(self, env, config, **kwargs):
        """
        Initialize the ladle manager.
        
        Args:
            env: Salabim environment
            config: Configuration dictionary with ladle settings
        """
        super().__init__(env=env, **kwargs)
        self.env = env
        self.config = config
        
        # Create ladle fleet
        self.ladles = []
        n_ladles = config.get("n_ladles", 10)  # Default to 10 ladles if not specified
        warming_time = config.get("ladle_warming_time", 10)
        
        # Bay tracking for ladles
        self.bay_ladles = {}
        n_bays = config.get("n_bays", 2)
        for i in range(1, n_bays + 1):
            self.bay_ladles[f"bay{i}"] = []
        
        for i in range(n_ladles):
            # Determine initial bay placement
            bay_id = f"bay{(i % n_bays) + 1}"
            
            # Create ladle with enhanced properties
            ladle = Ladle(
                id=i, 
                env=env, 
                warming_time=warming_time,
                bay=bay_id,
                capacity=config.get("ladle_capacity", 150)
            )
            self.ladles.append(ladle)
            
            # Track ladle by bay
            self.bay_ladles[bay_id].append(ladle)
        
        # Start the process - activate without parameters
        self.activate()
        
        logger.info(f"LadleManager initialized with {n_ladles} ladles")
    
    def process(self):
        """Main process required by Salabim - calls maintenance cycle."""
        return self.maintenance_cycle()
    
    def get_available_ladle(self, required_grade=None, bay=None):
        """
        Get an available ladle suitable for the given grade.
        
        Args:
            required_grade: Steel grade needed
            bay: Preferred bay location (optional)
            
        Returns:
            Ladle: An available ladle, or None if none available
        """
        # First priority: Available ladles in the requested bay
        if bay:
            bay_ladles = [l for l in self.ladles 
                         if l.check_availability(required_grade) and l.location == bay]
            if bay_ladles:
                return bay_ladles[0]
        
        # Second priority: Any available ladle
        available_ladles = [l for l in self.ladles if l.check_availability(required_grade)]
        if available_ladles:
            return available_ladles[0]
        
        logger.warning(f"{self.env.now():.2f} LadleManager: No ladles available for grade {required_grade}")
        return None
    
    def release_ladle(self, ladle):
        """
        Release a ladle and start warming cycle.
        
        Args:
            ladle: Ladle to release
        """
        if ladle in self.ladles:
            ladle.release()
    
    def maintenance_cycle(self):
        """Process to periodically check ladles for maintenance."""
        while True:
            for ladle in self.ladles:
                if ladle.needs_maintenance():
                    logger.info(f"Ladle {ladle.id} needs maintenance")
                    maintenance_time = ladle.perform_maintenance()
                    yield self.env.timeout(maintenance_time)  # Simulate maintenance duration
                    logger.info(f"Ladle {ladle.id} maintenance completed")
            yield self.env.timeout(60)
    
    def transfer_ladle(self, ladle, to_bay):
        """
        Transfer a ladle to another bay.
        
        Args:
            ladle: Ladle to transfer
            to_bay: Destination bay
            
        Returns:
            bool: True if transfer successful
        """
        if ladle not in self.ladles or ladle.status != "available":
            return False
            
        # Remove from current bay tracking
        from_bay = ladle.location
        if from_bay in self.bay_ladles and ladle in self.bay_ladles[from_bay]:
            self.bay_ladles[from_bay].remove(ladle)
            
        # Add to new bay tracking
        ladle.location = to_bay
        if to_bay in self.bay_ladles:
            self.bay_ladles[to_bay].append(ladle)
            logger.info(f"Ladle {ladle.id} transferred from {from_bay} to {to_bay}")
            return True
            
        return False
    
    def get_stats(self):
        """
        Get statistics on ladle usage.
        
        Returns:
            dict: Dictionary of ladle statistics
        """
        stats = {
            "total_ladles": len(self.ladles),
            "available": sum(1 for l in self.ladles if l.status == "available"),
            "in_use": sum(1 for l in self.ladles if l.status == "in_use"),
            "warming": sum(1 for l in self.ladles if l.status == "warming"),
            "maintenance": sum(1 for l in self.ladles if l.status == "maintenance"),
            "total_heats_processed": sum(l.total_heats_processed for l in self.ladles),
            "total_warming_time": sum(l.total_warming_time for l in self.ladles),
            "by_bay": {
                bay: len(ladles) for bay, ladles in self.bay_ladles.items()
            },
            "average_wear": sum(l.wear_level for l in self.ladles) / len(self.ladles) if self.ladles else 0
        }
        return stats