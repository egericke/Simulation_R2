import sys
import os
import unittest
import pytest
from unittest.mock import MagicMock, patch

# Add the project root to the path so we can import modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from equipment.ladle_car import BaseLadleCar

class TestLadleCar(unittest.TestCase):
    """Test case for the BaseLadleCar class."""
    
    def setUp(self):
        """Set up the test environment."""
        # Create mocks for dependencies
        self.mock_env = MagicMock()
        self.mock_env.now.return_value = 0
        
        self.mock_spatial_manager = MagicMock()
        self.mock_spatial_manager.get_bay_position.return_value = {"x": 10, "y": 20}
        self.mock_spatial_manager.get_path.return_value = [
            {"from": {"x": 10, "y": 20}, "to": {"x": 50, "y": 20}, "travel_time": 5, "distance": 40},
            {"from": {"x": 50, "y": 20}, "to": {"x": 50, "y": 60}, "travel_time": 5, "distance": 40}
        ]
        
        # Mock for the idle callback function
        self.mock_callback = MagicMock()
        
        # Create a test ladle car
        self.ladle_car = BaseLadleCar(
            env=self.mock_env,
            car_id=1,
            car_type="tapping",
            home_bay="bay1",
            speed=150,
            spatial_manager=self.mock_spatial_manager,
            on_idle_callback=self.mock_callback
        )
    
    def test_initialization(self):
        """Test proper ladle car initialization."""
        # Check basic attributes
        self.assertEqual(self.ladle_car.car_id, 1)
        self.assertEqual(self.ladle_car.car_type, "tapping")
        self.assertEqual(self.ladle_car.home_bay, "bay1")
        self.assertEqual(self.ladle_car.speed, 150)
        self.assertEqual(self.ladle_car.get_status_string(), "idle")
        self.assertEqual(self.ladle_car.current_bay, "bay1")
        self.assertIsNone(self.ladle_car.current_heat)
        self.assertIsNone(self.ladle_car.destination)
        self.assertEqual(self.ladle_car.position, {"x": 10, "y": 20})
        
        # Check spatial manager was called correctly
        self.mock_spatial_manager.get_bay_position.assert_called_once_with("bay1")
    
    def test_invalid_initialization(self):
        """Test handling of invalid initialization parameters."""
        # Test invalid car_type
        with self.assertRaises(ValueError):
            BaseLadleCar(
                env=self.mock_env,
                car_id=1,
                car_type="invalid_type",  # Invalid: not in ["tapping", "treatment", "rh"]
                home_bay="bay1",
                speed=150
            )
        
        # Test invalid car_id
        with self.assertRaises(TypeError):
            BaseLadleCar(
                env=self.mock_env,
                car_id=None,  # Invalid: not int or str
                car_type="tapping",
                home_bay="bay1",
                speed=150
            )
        
        # Test invalid home_bay
        with self.assertRaises(TypeError):
            BaseLadleCar(
                env=self.mock_env,
                car_id=1,
                car_type="tapping",
                home_bay=123,  # Invalid: not str
                speed=150
            )
        
        # Test invalid speed
        with self.assertRaises(ValueError):
            BaseLadleCar(
                env=self.mock_env,
                car_id=1,
                car_type="tapping",
                home_bay="bay1",
                speed=-10  # Invalid: not positive
            )
    
    def test_status_property(self):
        """Test the car_status property and status methods."""
        # Test initial status
        self.assertEqual(self.ladle_car.get_status_string(), "idle")
        
        # Test setting status
        self.assertTrue(self.ladle_car.set_status("moving"))
        self.assertEqual(self.ladle_car.get_status_string(), "moving")
        
        # Test invalid status
        self.assertFalse(self.ladle_car.set_status("invalid_status"))
        self.assertEqual(self.ladle_car.get_status_string(), "moving")  # Should not change
        
        # Test invalid status type
        self.assertFalse(self.ladle_car.set_status(123))  # Not a string
        
        # Test setting back to idle triggers callback
        self.ladle_car.set_status("idle")
        self.mock_callback.assert_called_once()
        
        # Test direct assignment is prevented
        with self.assertRaises(AttributeError):
            self.ladle_car.car_status = "moving"
    
    def test_assign_heat(self):
        """Test assigning a heat to the ladle car."""
        # Create mock objects
        mock_heat = MagicMock()
        mock_heat.id = "heat1"
        mock_unit = MagicMock()
        mock_unit.name.return_value = "test_unit"
        destination = {"bay": "bay2", "unit": mock_unit}
        
        # Assign heat
        result = self.ladle_car.assign_heat(mock_heat, destination)
        
        # Verify assignment
        self.assertTrue(result)
        self.assertEqual(self.ladle_car.current_heat, mock_heat)
        self.assertEqual(self.ladle_car.destination, destination)
        self.assertEqual(self.ladle_car.get_status_string(), "loading")
        self.assertEqual(len(self.ladle_car.path), 2)  # Should have 2 path segments
        
        # Verify spatial manager was used to get path
        self.mock_spatial_manager.get_path.assert_called_once_with("bay1", "bay2", car_type="tapping")
    
    def test_assign_heat_invalid_inputs(self):
        """Test heat assignment with invalid inputs."""
        # Test null heat
        result = self.ladle_car.assign_heat(None, {"bay": "bay2", "unit": MagicMock()})
        self.assertFalse(result)
        
        # Test invalid destination format
        mock_heat = MagicMock()
        mock_heat.id = "heat1"
        
        result = self.ladle_car.assign_heat(mock_heat, "not_a_dict")
        self.assertFalse(result)
        
        # Test missing keys in destination
        result = self.ladle_car.assign_heat(mock_heat, {"missing": "keys"})
        self.assertFalse(result)
        
        # Test unavailable car (not idle)
        self.ladle_car.set_status("moving")
        result = self.ladle_car.assign_heat(mock_heat, {"bay": "bay2", "unit": MagicMock()})
        self.assertFalse(result)
    
    def test_assign_heat_path_error(self):
        """Test heat assignment with path retrieval error."""
        # Create mock objects
        mock_heat = MagicMock()
        mock_heat.id = "heat1"
        mock_unit = MagicMock()
        destination = {"bay": "bay2", "unit": mock_unit}
        
        # Force a path retrieval error
        self.mock_spatial_manager.get_path.return_value = None
        
        # Reset the car to idle
        self.ladle_car.set_status("idle")
        
        # Assign heat should fail due to path error
        result = self.ladle_car.assign_heat(mock_heat, destination)
        self.assertFalse(result)
        self.assertIsNone(self.ladle_car.current_heat)
    
    def test_is_available(self):
        """Test the availability check."""
        # Initially available
        self.assertTrue(self.ladle_car.is_available())
        
        # Not available when busy
        self.ladle_car.set_status("moving")
        self.assertFalse(self.ladle_car.is_available())
        
        # Available when idle again
        self.ladle_car.set_status("idle")
        self.assertTrue(self.ladle_car.is_available())
    
    def test_process_movement(self):
        """Test the car's movement processing."""
        # Setup for movement
        mock_heat = MagicMock()
        mock_heat.id = "heat1"
        mock_unit = MagicMock()
        destination = {"bay": "bay2", "unit": mock_unit}
        
        # Assign heat to start movement
        self.ladle_car.assign_heat(mock_heat, destination)
        self.ladle_car.set_status("moving")
        
        # Process first movement segment
        self.ladle_car.process()
        
        # Simulate time passing
        self.mock_env.now.return_value = 5
        
        # Update position after first segment
        self.ladle_car.position = {"x": 50, "y": 20}
        self.ladle_car.current_path_segment = 1
        
        # Process second movement segment
        self.ladle_car.process()
        
        # Simulate time passing
        self.mock_env.now.return_value = 10
        
        # Update position after second segment and update bay
        self.ladle_car.position = {"x": 50, "y": 60}
        self.ladle_car.current_path_segment = 2
        self.ladle_car.current_bay = "bay2"
        
        # Process should now transition to unloading since we've reached destination
        self.ladle_car.set_status("unloading")
        
        # Verify total distance traveled
        self.assertEqual(self.ladle_car.total_distance_traveled, 80)  # 40 + 40
    
    def test_request_crane(self):
        """Test requesting a crane."""
        # Mock the transport manager and crane
        mock_transport_manager = MagicMock()
        self.mock_env.transport_manager = mock_transport_manager
        
        mock_crane = MagicMock()
        mock_crane.is_available.return_value = True
        mock_crane.name.return_value = "test_crane"
        
        # Set up transport manager to return our mock crane
        mock_transport_manager.cranes = {"bay1": [mock_crane]}
        
        # Request crane
        crane = self.ladle_car._request_crane("bay1", "loading")
        
        # Verify result
        self.assertEqual(crane, mock_crane)
    
    def test_request_crane_none_available(self):
        """Test requesting a crane when none are available."""
        # Mock the transport manager
        mock_transport_manager = MagicMock()
        self.mock_env.transport_manager = mock_transport_manager
        
        # Set up transport manager to return no available cranes
        mock_crane = MagicMock()
        mock_crane.is_available.return_value = False
        mock_transport_manager.cranes = {"bay1": [mock_crane]}
        
        # Request crane
        crane = self.ladle_car._request_crane("bay1", "loading")
        
        # Verify result
        self.assertIsNone(crane)
    
    def test_get_metrics(self):
        """Test the metrics collection."""
        # Add some mock metrics data
        self.ladle_car.task_count = 5
        self.ladle_car.total_distance_traveled = 200.0
        self.ladle_car.error_count = 2
        self.ladle_car.movement_times = [10, 20, 15]
        self.ladle_car.waiting_times = [5, 8]
        
        # Get metrics
        metrics = self.ladle_car.get_metrics()
        
        # Verify metrics structure
        self.assertEqual(metrics["car_id"], 1)
        self.assertEqual(metrics["car_type"], "tapping")
        self.assertEqual(metrics["current_bay"], "bay1")
        self.assertEqual(metrics["status"], "idle")
        self.assertEqual(metrics["task_count"], 5)
        self.assertEqual(metrics["total_distance"], 200.0)
        self.assertEqual(metrics["error_count"], 2)
        self.assertEqual(metrics["avg_movement_time"], 15.0)
        self.assertEqual(metrics["avg_waiting_time"], 6.5)

if __name__ == '__main__':
    pytest.main(['-xvs', __file__])