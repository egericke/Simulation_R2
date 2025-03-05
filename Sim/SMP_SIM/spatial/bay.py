import logging

logger = logging.getLogger(__name__)

class Bay:
    """
    Represents a physical bay in the steel plant with defined boundaries and equipment.
    
    A bay is a rectangular area defined by top-left and bottom-right coordinates.
    It contains equipment and crane paths for logistical operations.
    """
    
    def __init__(self, bay_id, top_left, bottom_right, crane_paths=None):
        """
        Initialize a bay with its boundaries and paths.
        
        Args:
            bay_id: Unique identifier for the bay
            top_left: Dict with x,y coordinates of top-left corner
            bottom_right: Dict with x,y coordinates of bottom-right corner
            crane_paths: List of crane paths within the bay
        """
        self.bay_id = bay_id
        self.top_left = top_left
        self.bottom_right = bottom_right
        self.width = bottom_right["x"] - top_left["x"]
        self.height = bottom_right["y"] - top_left["y"]
        self.crane_paths = crane_paths or []
        self.equipment = {}
        
        # Validate bay dimensions and coordinates
        if not all(isinstance(coord, dict) and "x" in coord and "y" in coord 
                   for coord in (top_left, bottom_right)):
            logger.error(f"Invalid coordinate format for bay {bay_id}")
            raise ValueError(f"Bay {bay_id} has invalid coordinate format")
        if self.width <= 0 or self.height <= 0:
            logger.error(f"Invalid bay dimensions for {bay_id}: width={self.width}, height={self.height}")
            raise ValueError(f"Bay {bay_id} has invalid dimensions")
            
        logger.info(f"Bay {bay_id} created with dimensions: {self.width}x{self.height}")
    
    def get_center(self):
        """
        Calculate and return the center coordinates of the bay.
        
        Returns:
            dict: Center position with {'x': x, 'y': y}
        """
        center_x = (self.top_left["x"] + self.bottom_right["x"]) / 2
        center_y = (self.top_left["y"] + self.bottom_right["y"]) / 2
        return {"x": center_x, "y": center_y}
    
    def contains_point(self, x, y):
        """Check if the bay contains the given point."""
        return (self.top_left["x"] <= x <= self.bottom_right["x"] and
                self.top_left["y"] <= y <= self.bottom_right["y"])
    
    def add_equipment(self, equipment_id, equipment_type, position):
        """
        Add equipment to the bay at the specified position.
        
        Args:
            equipment_id: Unique identifier for the equipment
            equipment_type: Type of equipment (EAF, LMF, etc.)
            position: Dict with x,y coordinates
        
        Returns:
            bool: True if equipment was added successfully
        """
        if not self.contains_point(position["x"], position["y"]):
            logger.warning(f"Equipment {equipment_id} position {position} is outside bay {self.bay_id}")
            return False
            
        self.equipment[equipment_id] = {
            "type": equipment_type,
            "position": position
        }
        logger.info(f"Added {equipment_type} {equipment_id} to bay {self.bay_id} at {position}")
        return True
    
    def get_crane_position_at_time(self, crane_id, time):
        """
        Calculate the position of a crane at a given simulation time.
        
        Args:
            crane_id: ID of the crane to track
            time: Current simulation time
            
        Returns:
            dict: Position {x, y} of the crane, or None if invalid
        """
        crane_index = int(crane_id.split('_')[1]) - 1
        if crane_index < 0 or crane_index >= len(self.crane_paths):
            logger.warning(f"Crane {crane_id} index out of range for bay {self.bay_id}")
            return None
        path = self.crane_paths[crane_index]
        path_length = path["end_x"] - path["start_x"]
        position_ratio = (time % 60) / 60  # Oscillate every minute
        if position_ratio > 0.5:
            position_ratio = 1 - position_ratio
        position_ratio *= 2  # Scale to 0-1 range
        x = path["start_x"] + path_length * position_ratio
        return {"x": x, "y": path["y"]}
    
    def check_crane_collision(self, crane_positions):
        """
        Check if any cranes in the provided positions would collide.
        
        Args:
            crane_positions: Dict of crane_id to position {x, y}
            
        Returns:
            bool: True if a collision would occur
        """
        cranes_by_x = sorted(
            [(crane_id, pos["x"]) for crane_id, pos in crane_positions.items()],
            key=lambda item: item[1]
        )
        MIN_SPACING = 10  # Minimum distance between cranes in units
        for i in range(len(cranes_by_x) - 1):
            crane1, x1 = cranes_by_x[i]
            crane2, x2 = cranes_by_x[i + 1]
            if x2 - x1 < MIN_SPACING:
                logger.warning(f"Potential collision between {crane1} and {crane2} in bay {self.bay_id}")
                return True
        return False