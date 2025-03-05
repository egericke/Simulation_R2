import sys
import os
import unittest
import pytest
from unittest.mock import MagicMock, patch

# Add the project root to the path so we can import modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Import the module to test
from route_manager_adapter import RouteManagerAdapter

class TestRouteManagerAdapter(unittest.TestCase):
    """Test case for the RouteManagerAdapter class."""
    
    def setUp(self):
        """Set up the test environment."""
        # Create mocks for dependencies
        self.mock_env = MagicMock()
        self.mock_env.now.return_value = 0
        
        self.mock_route_manager = MagicMock()
        
        # Configure steel grades
        self.steel_grades = {
            "1020": {"name": "Carbon Steel", "route": ["EAF", "LMF", "CASTER"]},
            "304": {"name": "Stainless Steel", "route": ["EAF", "LMF", "RH", "CASTER"]},
            "4140": {"name": "Alloy Steel", "route": ["EAF", "LMF", "VAC", "CASTER"]}
        }
        
        # Configure bay assignments
        self.bay_assignments = {
            "EAF": "bay1",
            "LMF": "bay2",
            "RH": "bay3",
            "VAC": "bay3",
            "CASTER": "bay4"
        }
        
        # Create test instance with mocks
        self.adapter = RouteManagerAdapter(
            environment=self.mock_env,
            route_manager=self.mock_route_manager,
            steel_grades=self.steel_grades,
            bay_assignments=self.bay_assignments
        )
    
    def test_initialization(self):
        """Test proper initialization."""
        # Check basic attributes
        self.assertEqual(self.adapter.env, self.mock_env)
        self.assertEqual(self.adapter.route_manager, self.mock_route_manager)
        self.assertEqual(self.adapter.steel_grades, self.steel_grades)
        self.assertEqual(self.adapter.bay_assignments, self.bay_assignments)
    
    def test_get_route_for_grade(self):
        """Test retrieving routes for different steel grades."""
        # Test existing grade
        route = self.adapter.get_route_for_grade("1020")
        self.assertEqual(route, ["EAF", "LMF", "CASTER"])
        
        # Test another existing grade with different route
        route = self.adapter.get_route_for_grade("304")
        self.assertEqual(route, ["EAF", "LMF", "RH", "CASTER"])
        
        # Test non-existent grade
        with patch('logging.Logger.warning') as mock_log:
            route = self.adapter.get_route_for_grade("unknown")
            self.assertIsNone(route)
            mock_log.assert_called()  # Should log a warning
    
    def test_get_bay_for_unit(self):
        """Test getting bay assignments for different unit types."""
        # Test existing unit
        bay = self.adapter.get_bay_for_unit("EAF")
        self.assertEqual(bay, "bay1")
        
        # Test another existing unit
        bay = self.adapter.get_bay_for_unit("RH")
        self.assertEqual(bay, "bay3")
        
        # Test case insensitivity
        bay = self.adapter.get_bay_for_unit("eaf")
        self.assertEqual(bay, "bay1")
        
        # Test non-existent unit
        with patch('logging.Logger.warning') as mock_log:
            bay = self.adapter.get_bay_for_unit("NONEXISTENT")
            self.assertIsNone(bay)
            mock_log.assert_called()  # Should log a warning
    
    def test_route_heat(self):
        """Test routing a heat through its processing steps."""
        # Create a mock heat
        mock_heat = MagicMock()
        mock_heat.steel_grade = "1020"
        mock_heat.id = "heat1"
        
        # Mock the route manager's get_next_unit method
        self.mock_route_manager.get_next_unit.return_value = "LMF"
        
        # Route the heat
        next_unit = self.adapter.route_heat(mock_heat)
        
        # Verify results
        self.assertEqual(next_unit, "LMF")
        self.mock_route_manager.get_next_unit.assert_called_once_with(mock_heat)
    
    def test_route_heat_unknown_grade(self):
        """Test routing a heat with an unknown steel grade."""
        # Create a mock heat with unknown grade
        mock_heat = MagicMock()
        mock_heat.steel_grade = "unknown"
        mock_heat.id = "heat1"
        
        # Mock the route manager's get_next_unit method to return None
        self.mock_route_manager.get_next_unit.return_value = None
        
        # Route the heat
        with patch('logging.Logger.error') as mock_log:
            next_unit = self.adapter.route_heat(mock_heat)
            
            # Verify results
            self.assertIsNone(next_unit)
            mock_log.assert_called()  # Should log an error
    
    def test_get_current_step(self):
        """Test getting the current processing step for a heat."""
        # Create a mock heat
        mock_heat = MagicMock()
        mock_heat.id = "heat1"
        mock_heat.route_history = ["EAF"]
        
        # Test with a heat that has a route history
        current_step = self.adapter.get_current_step(mock_heat)
        self.assertEqual(current_step, "EAF")
        
        # Test with a heat that has no route history
        mock_heat.route_history = []
        current_step = self.adapter.get_current_step(mock_heat)
        self.assertIsNone(current_step)
    
    def test_get_next_step(self):
        """Test getting the next processing step for a heat."""
        # Create a mock heat
        mock_heat = MagicMock()
        mock_heat.id = "heat1"
        mock_heat.steel_grade = "1020"
        mock_heat.route_history = ["EAF"]
        
        # Test with a heat that has a route and history
        next_step = self.adapter.get_next_step(mock_heat)
        self.assertEqual(next_step, "LMF")
        
        # Test with a heat at the last step
        mock_heat.route_history = ["EAF", "LMF"]
        next_step = self.adapter.get_next_step(mock_heat)
        self.assertEqual(next_step, "CASTER")
        
        # Test with a heat that has completed its route
        mock_heat.route_history = ["EAF", "LMF", "CASTER"]
        next_step = self.adapter.get_next_step(mock_heat)
        self.assertIsNone(next_step)
        
        # Test with unknown grade
        mock_heat.steel_grade = "unknown"
        with patch('logging.Logger.warning') as mock_log:
            next_step = self.adapter.get_next_step(mock_heat)
            self.assertIsNone(next_step)
            mock_log.assert_called()  # Should log a warning
    
    def test_update_route_history(self):
        """Test updating a heat's route history."""
        # Create a mock heat
        mock_heat = MagicMock()
        mock_heat.id = "heat1"
        mock_heat.route_history = ["EAF"]
        
        # Update with a new unit
        self.adapter.update_route_history(mock_heat, "LMF")
        
        # Verify history was updated
        self.assertEqual(mock_heat.route_history, ["EAF", "LMF"])
        
        # Update with a duplicate unit (should not add again)
        self.adapter.update_route_history(mock_heat, "LMF")
        
        # Verify history was not changed
        self.assertEqual(mock_heat.route_history, ["EAF", "LMF"])
    
    def test_get_remaining_route(self):
        """Test getting the remaining route for a heat."""
        # Create a mock heat
        mock_heat = MagicMock()
        mock_heat.id = "heat1"
        mock_heat.steel_grade = "1020"
        mock_heat.route_history = ["EAF"]
        
        # Test with a heat that has a partial route history
        remaining = self.adapter.get_remaining_route(mock_heat)
        self.assertEqual(remaining, ["LMF", "CASTER"])
        
        # Test with a heat that has completed more steps
        mock_heat.route_history = ["EAF", "LMF"]
        remaining = self.adapter.get_remaining_route(mock_heat)
        self.assertEqual(remaining, ["CASTER"])
        
        # Test with a heat that has completed its route
        mock_heat.route_history = ["EAF", "LMF", "CASTER"]
        remaining = self.adapter.get_remaining_route(mock_heat)
        self.assertEqual(remaining, [])
        
        # Test with unknown grade
        mock_heat.steel_grade = "unknown"
        with patch('logging.Logger.warning') as mock_log:
            remaining = self.adapter.get_remaining_route(mock_heat)
            self.assertEqual(remaining, [])
            mock_log.assert_called()  # Should log a warning
    
    def test_is_route_complete(self):
        """Test checking if a heat's route is complete."""
        # Create a mock heat
        mock_heat = MagicMock()
        mock_heat.id = "heat1"
        mock_heat.steel_grade = "1020"
        
        # Test with incomplete route
        mock_heat.route_history = ["EAF"]
        self.assertFalse(self.adapter.is_route_complete(mock_heat))
        
        mock_heat.route_history = ["EAF", "LMF"]
        self.assertFalse(self.adapter.is_route_complete(mock_heat))
        
        # Test with complete route
        mock_heat.route_history = ["EAF", "LMF", "CASTER"]
        self.assertTrue(self.adapter.is_route_complete(mock_heat))
        
        # Test with route longer than expected (edge case)
        mock_heat.route_history = ["EAF", "LMF", "CASTER", "EXTRA"]
        self.assertTrue(self.adapter.is_route_complete(mock_heat))
        
        # Test with unknown grade
        mock_heat.steel_grade = "unknown"
        with patch('logging.Logger.warning') as mock_log:
            self.assertFalse(self.adapter.is_route_complete(mock_heat))
            mock_log.assert_called()  # Should log a warning

if __name__ == '__main__':
    pytest.main(['-xvs', __file__])