import sys
import os
import unittest
import pytest
from unittest.mock import MagicMock, patch

# Add the project root to the path so we can import modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from equipment.crane import Crane, CraneState

class TestCrane(unittest.TestCase):
    """Test case for the Crane class."""
    
    def setUp(self):
        """Set up the test environment."""
        # Create mocks for dependencies
        self.mock_env = MagicMock()
        self.mock_env.now.return_value = 0
        
        self.mock_spatial_manager = MagicMock()
        self.mock_spatial_manager.get_crane_home_position.return_value = {"x": 10, "y": 20}
        self.mock_spatial_manager.get_unit_position.return_value = {"x": 30, "y": 40}
        self.mock_spatial_manager.is_unit_in_bay.return_value = True
        
        # Create a test crane
        self.crane = Crane(
            env=self.mock_env,
            crane_id=1,
            bay="testbay",
            speed=100,
            spatial_manager=self.mock_spatial_manager
        )
    
    def test_initialization(self):
        """Test proper crane initialization."""
        # Check basic attributes
        self.assertEqual(self.crane.unit_id, 1)
        self.assertEqual(self.crane.bay, "testbay")
        self.assertEqual(self.crane.speed, 100)
        self.assertEqual(self.crane.crane_state.value, CraneState.IDLE.value)
        self.assertIsNone(self.crane.current_heat)
        self.assertIsNone(self.crane.current_ladle)
        self.assertIsNone(self.crane.source)
        self.assertIsNone(self.crane.destination)
        
        # Check initial position
        self.assertEqual(self.crane.position, {"x": 10, "y": 20})
        
        # Check spatial manager was called with the right arguments
        self.mock_spatial_manager.get_crane_home_position.assert_called_once_with("testbay")
    
    def test_invalid_initialization(self):
        """Test handling of invalid initialization parameters."""
        # Test invalid crane_id
        with self.assertRaises(TypeError):
            Crane(
                env=self.mock_env,
                crane_id=None,  # Invalid: should be int or str
                bay="testbay",
                speed=100
            )
        
        # Test invalid bay
        with self.assertRaises(TypeError):
            Crane(
                env=self.mock_env,
                crane_id=1,
                bay=123,  # Invalid: should be str
                speed=100
            )
        
        # Test invalid speed
        with self.assertRaises(ValueError):
            Crane(
                env=self.mock_env,
                crane_id=1,
                bay="testbay",
                speed=-10  # Invalid: should be positive
            )
    
    def test_task_queuing(self):
        """Test adding tasks to the queue."""
        # First task should be accepted directly (not queued)
        result = self.crane.assign_task("source1", "dest1", priority=1)
        self.assertGreater(result, 0)  # Should return a positive time estimate
        self.assertEqual(len(self.crane.task_queue), 0)  # Task shouldn't be queued
        self.assertEqual(self.crane.crane_state.value, CraneState.MOVING.value)
        self.assertEqual(self.crane.source, "source1")
        self.assertEqual(self.crane.destination, "dest1")
        
        # Second task should be queued
        result = self.crane.assign_task("source2", "dest2", priority=2)
        self.assertEqual(result, 0)  # Should return 0 for queued tasks
        self.assertEqual(len(self.crane.task_queue), 1)  # Task should be queued
        
        # Lower priority task
        result = self.crane.assign_task("source3", "dest3", priority=0)
        self.assertEqual(result, 0)
        self.assertEqual(len(self.crane.task_queue), 2)
        
        # Verify task queue order (highest priority first)
        # Note: Priority is negated in the queue for the heap implementation
        self.assertEqual(self.crane.task_queue[0][0], -2)  # Highest priority
    
    def test_invalid_task_assignment(self):
        """Test handling of invalid task assignments."""
        # Source not in bay
        self.mock_spatial_manager.is_unit_in_bay.return_value = False
        result = self.crane.assign_task("source1", "dest1")
        self.assertEqual(result, 0)  # Should reject the task
        self.assertEqual(self.crane.crane_state.value, CraneState.IDLE.value)
        
        # Reset for subsequent tests
        self.mock_spatial_manager.is_unit_in_bay.return_value = True
    
    def test_calculate_movement_time(self):
        """Test movement time calculations."""
        # Test with short distance (under 2*d_accel)
        start = {"x": 0, "y": 0}
        end = {"x": 10, "y": 0}
        time = self.crane._calculate_movement_time(start, end)
        self.assertGreater(time, 0)
        
        # Test with longer distance
        end = {"x": 1000, "y": 0}
        time_long = self.crane._calculate_movement_time(start, end)
        self.assertGreater(time_long, time)  # Longer distance should take more time
        
        # Test with invalid input
        with patch('logging.Logger.error') as mock_log:
            time_invalid = self.crane._calculate_movement_time("invalid", end)
            self.assertGreater(time_invalid, 0)  # Should return fallback value
            mock_log.assert_called()  # Should log an error
    
    def test_is_available(self):
        """Test availability check."""
        # Initially available
        self.assertTrue(self.crane.is_available())
        
        # Not available when busy
        self.crane.assign_task("source", "dest")
        self.assertFalse(self.crane.is_available())
        
        # Not available when idle but has queued tasks
        self.crane.crane_state.set(CraneState.IDLE.value)
        self.crane.task_queue.append((-1, "source", "dest"))
        self.assertFalse(self.crane.is_available())
        
        # Available when idle and no queue
        self.crane.task_queue.clear()
        self.assertTrue(self.crane.is_available())
    
    def test_process_state_machine(self):
        """Test the crane's state machine in the process method."""
        # Create mock units for testing
        mock_source_unit = MagicMock()
        mock_source_unit.current_ladle = MagicMock()
        mock_source_unit.current_ladle.current_heat = MagicMock()
        mock_source_unit.current_ladle.current_heat.id = "heat1"
        mock_source_unit.current_ladle.id = "ladle1"
        
        mock_dest_unit = MagicMock()
        mock_dest_unit.add_ladle.return_value = True
        
        # Mock finding units
        self.crane.find_unit = MagicMock()
        self.crane.find_unit.side_effect = lambda loc: mock_source_unit if loc == "source" else mock_dest_unit
        
        # Assign a task to start the state machine
        self.crane.assign_task("source", "dest")
        self.assertEqual(self.crane.crane_state.value, CraneState.MOVING.value)
        
        # Test MOVING state
        self.crane.process()  # Will hold and transition to LIFTING
        self.mock_env.now.return_value = 10  # Simulate time passing
        self.crane.crane_state.set(CraneState.LIFTING.value)
        
        # Test LIFTING state
        self.crane.process()  # Will hold and transition to MOVING
        self.mock_env.now.return_value = 20
        self.crane.crane_state.set(CraneState.MOVING.value)
        
        # Verify ladle was picked up
        self.assertEqual(self.crane.current_ladle, mock_source_unit.current_ladle)
        self.assertEqual(self.crane.current_heat, mock_source_unit.current_ladle.current_heat)
        self.assertIsNone(mock_source_unit.current_ladle)
        
        # Test MOVING state again
        self.crane.process()
        self.mock_env.now.return_value = 30
        self.crane.crane_state.set(CraneState.LOWERING.value)
        
        # Test LOWERING state
        self.crane.process()
        self.mock_env.now.return_value = 40
        
        # Verify ladle was placed
        mock_dest_unit.add_ladle.assert_called_once_with(self.crane.current_ladle)
        
        # Should be back to IDLE state
        self.assertEqual(self.crane.crane_state.value, CraneState.IDLE.value)
        self.assertIsNone(self.crane.current_ladle)
        self.assertIsNone(self.crane.current_heat)
        self.assertIsNone(self.crane.source)
        self.assertIsNone(self.crane.destination)
    
    def test_error_state_recovery(self):
        """Test recovery from error state."""
        # Force an error state
        self.crane.crane_state.set(CraneState.ERROR.value)
        self.crane.current_ladle = MagicMock()
        self.crane.current_heat = MagicMock()
        self.crane.source = "source"
        self.crane.destination = "dest"
        
        # Process should attempt recovery
        self.crane.process()
        self.mock_env.now.return_value = 50
        
        # After recovery hold time, should transition back to IDLE
        self.crane.crane_state.set(CraneState.IDLE.value)
        
        # Verify everything was reset
        self.assertIsNone(self.crane.current_ladle)
        self.assertIsNone(self.crane.current_heat)
        self.assertIsNone(self.crane.source)
        self.assertIsNone(self.crane.destination)
    
    def test_get_metrics(self):
        """Test the metrics collection."""
        # Add some mock operation times
        self.crane.operation_times["moving"] = [10, 20]
        self.crane.operation_times["lifting"] = [5, 15]
        self.crane.operation_times["lowering"] = [8, 12]
        self.crane.task_count = 3
        self.crane.error_count = 1
        
        # Get metrics
        metrics = self.crane.get_metrics()
        
        # Verify metrics structure
        self.assertEqual(metrics["task_count"], 3)
        self.assertEqual(metrics["error_count"], 1)
        self.assertEqual(metrics["average_times"]["moving"], 15)
        self.assertEqual(metrics["average_times"]["lifting"], 10)
        self.assertEqual(metrics["average_times"]["lowering"], 10)
        self.assertEqual(metrics["queue_length"], 0)
        self.assertEqual(metrics["current_state"], CraneState.IDLE.value)

if __name__ == '__main__':
    pytest.main(['-xvs', __file__])