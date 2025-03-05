---
claude_md_version: 1.1
last_updated: 2023-11-15
---

# Project Overview
This is a steel plant simulation application built with Python (using salabim for simulation, PyQt/PySide for GUI), designed to model and optimize steelmaking processes. It includes equipment layout editing, simulation services, and transportation management.

# Directory Structure
- `/steel-plant-simulation_c3/`: Contains source code.
  - `/equipment/`: Modules for cranes, ladle cars, and ladle managers.
  - `/spatial/`: Spatial management for layout positioning.
  - `/setup_wizard.py`: GUI for configuring the simulation layout.
  - `/simulation_service.py`: Core simulation service logic.
  - `/test.py`: Basic simulation tests.
- `/tests/`: Test suites.

# Key Components
- `setup_wizard.py`: Implements `SetupWizard` and pages like `PlacementPage` and `EquipmentConfigPage`.
- `simulation_service.py`: Manages simulation state and configuration.
- `equipment_layout_editor.py`: Equipment layout editing interface.

# Coding Conventions
- Use PEP 8 for Python style.
- Use Qt styles for GUI elements.
- Comprehensive logging for debugging.

# Frequently Used Commands
- `python setup_wizard.py`: Launches the setup wizard GUI.
- `python main.py`: Runs the main simulation.
- `python test.py`: Runs basic simulation tests.

# Important Files
- `config_backup.json`: Stores configuration backups.
- `setup_wizard.log`: Logs GUI actions and errors.

# Project-Specific Terms
- **Bay**: A physical area in the layout for equipment.
- **Equipment**: Entities like EAF, LMF, Degasser, Caster.
- **Heat**: A batch of molten steel being processed through the plant.

# Integration Points
- **salabim**: For discrete-event simulation.
- **PyQt/PySide**: For the GUI (Equipment Layout Editor).
- **JSON**: For configuration storage.

# Testing Strategy
- Unit tests for simulation components using `salabim`.
- Integration tests for GUI and configuration persistence.

# Known Issues and Fixes
- **Equipment Configuration Persistence**: Configurations weren't persisting after saving and closing.
  - **Solution**: Updated `SimulationService.load_config` to ensure `equipment_positions` and `bays` sections exist, and modified `SummaryPage.save_config_file` to guarantee these sections are saved.
  
- **Toggle Button Visibility**: Buttons in the Equipment Layout Editor were hard to read without hovering.
  - **Solution**: Enhanced button styling in `PlacementPage` with high-contrast colors, larger fonts, and tooltips.
  
- **Equipment Sizing**: Equipment appeared too large for the bays.
  - **Solution**: Added size customization to `EquipmentConfigPage` (width/height fields) and updated rendering to use these dimensions.

---

**Note**: When making changes to the simulation configuration, use the "Save and Close" button or the "Save Configuration to File" button on the Summary page to ensure your changes persist.