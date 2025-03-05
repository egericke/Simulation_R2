# Steel Plant Simulation Project

## Introduction

This software provides a powerful simulation framework for modeling steelmaking plant layouts and optimizing ladle logistics. Tailored for engineers and planners, it offers advanced visualization of steel flow through processing units, real-time bottleneck analysis, and plant configuration optimization. The simulation models a steelmaking plant featuring key production units—Electric Arc Furnace (EAF), Ladle Metallurgical Furnace (LMF), Degasser, and Caster—interconnected by sophisticated ladle transport systems. Each heat (batch) of steel follows a defined route based on its grade and operational conditions, with enhanced support for integrating real-world plant layouts via CAD files.

## Key Features

- **Interactive Simulation Environment**: Real-time visualization of plant operations with animated flows.
- **Advanced CAD Integration**: Import and utilize DXF, SVG, and CAD/DWG layouts with automatic scaling, layer management, and caching.
- **Visual Equipment Placement**: Drag-and-drop interface for positioning units on imported layouts.
- **Transportation Route Editor**: Define and optimize paths between production units.
- **Production Planning**: Configure schedules, shifts, maintenance, and steel grade distributions.
- **Real-time Bottleneck Analysis**: Identify and analyze production constraints dynamically.
- **Interactive Dashboard**: Monitor live performance metrics with customizable views.
- **Analytics Reports**: Generate detailed analyses of production flow and bottlenecks.
- **What-If Scenarios**: Test various configurations and operational settings.
- **Enhanced User Interface**: Features a setup wizard, configuration tools, and detailed feedback for CAD operations.

## Installation

### Prerequisites

- Python 3.7 or higher
- pip (Python package manager)

### Recommended Dependencies

For full functionality, install these optional packages alongside the core dependencies:
- `ezdxf` (>=0.17): Enhanced DXF file parsing
- `librecad`, `freecad`, or ODA File Converter: For CAD/DWG conversion
- `python-dwg` (optional): Fallback DWG parsing


### Installation Steps

1. **Clone or Download the Repository**:
   ```bash
   git clone https://github.com/your-username/steel-plant-simulation.git
   cd steel-plant-simulation
   ```

2. **Create and Activate a Virtual Environment (Recommended)**:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install Required Packages**:
   ```bash
   pip install -r requirements.txt
   ```
   Core dependencies include:
   - `PyQt5`: GUI framework
   - `salabim`: Discrete event simulation
   - `numpy`: Numerical computations

   For optimal CAD support:
   ```bash
   pip install ezdxf
   ```

4. **Run the Simulation**:
   ```bash
   python main.py
   ```

## Getting Started

### First Launch Setup

Upon initial launch, the `SetupWizard` guides you through configuration:

1. **Introduction**: Overview of the setup process.
2. **CAD Layout**: Load a DXF, SVG, or CAD/DWG file with automatic scaling and layer selection.
3. **Equipment Configuration**: Define production units and parameters.
4. **Production Parameters**: Set targets, steel grade distributions, and scenarios.
5. **Equipment Placement**: Position units on the layout.
6. **Transportation Configuration**: Configure ladle cars and routes.

### Working with CAD Files

The simulation now supports a wide range of CAD file formats with advanced features:

- **Supported Formats**:
  - **DXF**: Native support with robust parsing (lines, circles, arcs, text, polylines) and layer management, enhanced by `ezdxf` if installed.
  - **SVG**: Full parsing of lines, circles, paths, and text, with automatic scaling.
  - **CAD/DWG**: Automatic conversion to DXF using ODA File Converter, LibreCAD, FreeCAD, or `python-dwg` (if available).

- **Import Process**:
  - Use **Tools > Import CAD** to load files. The enhanced `ConversionDialog` attempts multiple conversion methods and provides detailed feedback.
  - Manually convert unsupported formats to DXF or SVG using tools like AutoCAD, FreeCAD, or Inkscape if automatic conversion fails.
  - Adjust scale, offset, and visible layers via the UI or `config.json`.

- **Features**:
  - **Auto-Scaling**: Automatically fits layouts to the simulation grid (80% of grid size with margins).
  - **Layer Management**: Filter and toggle visibility of CAD layers for focused visualization.
  - **Caching**: Stores parsed layouts to improve load times for repeated use.

- **Note**: For best results, use AutoCAD 2018 DXF format or SVG files. Pre-convert complex CAD files if automatic conversion encounters issues.

### Configuring Equipment

Set up production units via the Equipment Configuration tab:

- **EAF**: Melts raw materials.
- **LMF**: Refines steel chemistry and temperature.
- **Degasser**: Removes gases from molten steel.
- **Caster**: Solidifies steel into semi-finished products.

Configurable parameters include:
- Process time
- Minimum process time
- Capacity
- Position coordinates

### Setting Up Production

Configure via the Production Settings dialog:
- **Steel Grade Distribution**: Standard, high-clean, decarb, temp-sensitive.
- **Production Scenarios**: Define operational conditions.
- **Heat Generation Intervals**: Set timing for new heats.
- **Operating Parameters**: Adjust unit-specific settings.

### Running the Simulation

Control the simulation through the main dashboard:
1. Click **Run** to start or pause.
2. Use **Step** for single-step advancement.
3. Adjust speed with the slider.
4. Navigate tabs:
   - **Simulation**: Animated view.
   - **Dashboard**: Real-time metrics.
   - **Analytics**: Bottleneck analysis and recommendations.
5. Reset to apply major changes.

## Configuration Options

### `config.json`

This JSON file centralizes simulation settings, editable directly or via the UI. Key sections include:

```json
{
  "sim_speed": 1.0,              // Simulation speed multiplier
  "takt_time": 60,               // Target takt time in minutes
  "bays": {                      // Define physical bays with their positions
    "bay1": {"x_offset": 100, "y_offset": 100},
    "bay2": {"x_offset": 100, "y_offset": 400}
  },
  "units": {
    "EAF": {"process_time": 50, "min_process_time": 50, "capacity": 1},
    "LMF": {"process_time": 30, "min_process_time": 30, "capacity": 1},
    "Degasser": {"process_time": 40, "capacity": 1},
    "Caster": {
      "process_time": 20, "capacity": 1, "turnaround_time": 20,
      "max_sequence": 7, "flow_interruption_threshold": 15
    }
  },
  "grade_distribution": {
    "standard": 0.60, "high_clean": 0.20, "decarb": 0.15, "temp_sensitive": 0.05
  },
  "grade_routes": {
    "standard": ["EAF", "LMF", "Caster"],
    "high_clean": ["EAF", "LMF", "Degasser", "Caster"],
    "decarb": ["EAF", "LMF", "Degasser", "Caster"],
    "temp_sensitive": ["EAF", "LMF", "Caster"]
  },
  "ladle_car_speed": 150,
  "crane_speed": 100,
  "n_ladle_cars": 2,
  "n_cranes_per_bay": 1,
  "analytics": {"high_utilization": 0.85, "queue_alert": 2}
}
```

- **New CAD Options**:
  - `cad_file_path`: Path to the CAD file.
  - `cad_scale`, `cad_x_offset`, `cad_y_offset`: Manual scaling and positioning (overridden by auto-scaling if enabled).
  - `auto_scale_cad`: Enable/disable automatic scaling (default: `true`).
  - `cad_visible_layers`: List of visible CAD layers (empty means all layers visible).
  - `cad_cache_enabled`: Enable/disable caching (default: `true`).

**Note**: Ensure `bays` includes `x_offset` and `y_offset` keys for accurate positioning.

### Command-Line Options

```bash
python main.py [options]
```
- `--config FILEPATH`: Specify configuration file (default: `config.json`).
- `--headless`: Run without GUI.
- `--scenario NAME`: Select scenario for headless mode.
- `--export-results PATH`: Save results in headless mode.
- `--simulation-time SEC`: Set duration (default: 1000).

## File Structure

The project is organized as follows, with detailed descriptions to aid in understanding and troubleshooting:

```
steel-plant-simulation_c1/
├── main.py                    # Main entry point with GUI or headless mode
├── analytics_dashboard.py     # Analytics visualization
├── bottleneck_analyzer.py     # Bottleneck detection
├── cad_integration.py         # Advanced CAD layout integration (DXF, SVG, CAD/DWG)
├── config.json                # Configuration file with CAD options
├── dashboard.py               # Main UI dashboard
├── equipment_layout_editor.py # Equipment placement editor
├── layer_manager.py           # Visualization layers with CAD layer support
├── oda_file_converter.py      # Enhanced CAD conversion utilities
├── production_manager.py      # Production oversight
├── production_settings.py     # Production configuration
├── requirements.txt           # Dependencies
├── route_manager_adapter.py   # Routing adapter
├── setup_wizard.py            # Setup wizard with CAD import
├── simulation_service.py      # Core simulation logic
├── equipment/                 # Equipment modules
│   ├── crane.py
│   ├── ladle.py
│   ├── ladle_car.py
│   ├── ladle_manager.py
│   ├── transport_manager.py
│   └── __init__.py
├── process_control/           # Process control modules
│   ├── plant_metrics.py
│   ├── route_manager.py
│   ├── scenario_manager.py
│   ├── steel_grade.py
│   └── __init__.py
├── production_units/          # Production unit definitions
│   ├── base_unit.py
│   ├── eaf.py
│   ├── lmf.py
│   ├── degasser.py
│   ├── caster.py
│   ├── heat.py
│   └── __init__.py
├── simulation/                # Simulation utilities
│   ├── config.py
│   └── __init__.py
└── spatial/                   # Spatial management
    ├── bay.py
    ├── spatial_manager.py     # Aligns equipment with CAD layouts
    └── __init__.py
```

### Detailed File Descriptions

#### **Simulation Core**

- **`main.py`**
  - **Purpose**: Main entry point, initializing and running the simulation with GUI or headless options.
  - **Key Classes**:
    - `LoadingThread`: Background loading of components.
    - `SimulationApp`: GUI management with tabs and controls.
  - **Important Variables**:
    - `config`: Simulation parameters.
    - `env`: Salabim environment.
    - `sim_service`: Core simulation instance.
  - **Functionality**: Parses arguments, sets up GUI with tabs (Simulation, Dashboard, Analytics), and controls simulation flow.
  - **Interactions**: Launches `SetupWizard`, integrates with `SimulationService`, `Dashboard`, and `AnalyticsDashboard`.

- **`simulation_service.py`**
  - **Purpose**: Manages core simulation logic (start, pause, reset).
  - **Key Classes**: `SimulationService`
  - **Important Variables**: `env`, `config`, `production_manager`
  - **Functionality**: Initializes and synchronizes simulation components.
  - **Interactions**: Controlled by `main.py` and `dashboard.py`, coordinates with `ProductionManager`.

#### **User Interface**

- **`dashboard.py`**
  - **Purpose**: Main UI for simulation control and monitoring.
  - **Key Classes**: `Dashboard` (QMainWindow)
  - **Important Variables**: `config`, `sim_service`, `layer_manager`
  - **Functionality**: Offers tabs for simulation control, visualization, and configuration; updates real-time stats.
  - **Interactions**: Controls `SimulationService`, updates `config.json`, manages `LayerManager`.

- **`analytics_dashboard.py`**
  - **Purpose**: Visualizes bottleneck analysis and metrics.
  - **Key Classes**: `AnalyticsDashboard` (QWidget)
  - **Important Variables**: `analyzer`, `timer`
  - **Functionality**: Displays tabs for system overview, bottlenecks, unit details, and recommendations; updates via `QTimer`.
  - **Interactions**: Uses `BottleneckAnalyzer`, integrates with `Dashboard`.

- **`setup_wizard.py`**
  - **Purpose**: Guides initial configuration.
  - **Key Classes**: `SetupWizard` (QWizard), various page classes
  - **Important Variables**: `config`, `env`, `sim_service`
  - **Functionality**: Steps through CAD loading, equipment setup, and production settings.
  - **Interactions**: Updates `config`, interacts with `CADBackground` and `LayerManager`.

#### **Configuration and Setup**

- **`config.json`**
  - **Purpose**: Centralizes simulation settings.
  - **Key Sections**: `sim_speed`, `bays`, `units`, `grade_distribution`, etc.
  - **Functionality**: Loaded and modified by multiple modules; supports extended options like `n_bays`.
  - **Interactions**: Used by `main.py`, `ProductionManager`, `Dashboard`, etc.

- **`config.py`**
  - **Purpose**: Manages configuration loading and access.
  - **Key Classes**: `SimulationConfig`
  - **Important Variables**: `config`, `config_path`
  - **Functionality**: Loads defaults, overrides with file settings, saves changes.
  - **Interactions**: Ensures consistency across modules.

- **`spatial_manager.py`**
  - **Purpose**: Handles spatial layout and path planning.
  - **Key Classes**: `SpatialManager`
  - **Important Variables**: `bays`, `equipment_locations`, `ladle_car_paths`
  - **Functionality**: Manages bay layouts, equipment placement, and transport paths; checks crane collisions.
  - **Interactions**: Supports `TransportManager`, `ProductionManager`; uses `Bay`.

- **`bay.py`**
  - **Purpose**: Defines physical bays.
  - **Key Classes**: `Bay`
  - **Important Variables**: `bay_id`, `top_left`, `equipment`
  - **Functionality**: Validates boundaries, manages equipment placement, calculates crane positions.
  - **Interactions**: Used by `SpatialManager`.

#### **Production Management**

- **`production_manager.py`**
  - **Purpose**: Oversees production processes.
  - **Key Classes**: `ProductionManager` (Salabim Component)
  - **Important Variables**: `units`, `heat_counter`, `route_manager`
  - **Functionality**: Generates heats, routes them, calculates metrics.
  - **Interactions**: Uses `RouteManagerAdapter`, coordinates with production units and `TransportManager`.

- **`route_manager.py`**
  - **Purpose**: Directs heat routing based on grade.
  - **Key Classes**: `ProcessRouteManager`
  - **Important Variables**: `heat_routes`, `steel_grades`
  - **Functionality**: Defines equipment sequences, assigns units, plans paths.
  - **Interactions**: Uses `SteelGrade`, `SpatialManager`; integrates with units.

- **`route_manager_adapter.py`**
  - **Purpose**: Adapts `RouteManager` for `ProductionManager`.
  - **Key Classes**: `ProcessRouteManagerAdapter`
  - **Important Variables**: `route_queue`, `heat_routes`
  - **Functionality**: Registers units, determines and advances routes.
  - **Interactions**: Bridges `ProductionManager` and units.

- **`scenario_manager.py`**
  - **Purpose**: Manages operational scenarios.
  - **Key Classes**: `ScenarioManager`
  - **Important Variables**: `current_scenario`, `scenarios`
  - **Functionality**: Switches scenarios, adjusts routing logic.
  - **Interactions**: Influences `RouteManager` via config.

- **`steel_grade.py`**
  - **Purpose**: Defines steel grade properties.
  - **Key Classes**: `SteelGrade`
  - **Important Variables**: `grade_id`, `properties`
  - **Functionality**: Sets equipment needs and process times.
  - **Interactions**: Used by `RouteManager`, influences units.

- **`production_settings.py`**
  - **Purpose**: Configures production parameters via UI.
  - **Key Classes**: `ProductionSettingsDialog` (QDialog)
  - **Important Variables**: `config`
  - **Functionality**: Manages targets, schedules, and advanced settings.
  - **Interactions**: Updates `config`, invoked by `main.py`.

#### **Equipment and Transportation**

- **`equipment_layout_editor.py`**
  - **Purpose**: Interactive equipment placement editor.
  - **Key Classes**: `EquipmentItem`, `LayoutScene`, `EquipmentLayoutEditor`
  - **Important Variables**: `EQUIPMENT_TYPES`, `config`
  - **Functionality**: Allows dragging equipment and drawing routes, saves to `config`.
  - **Interactions**: Uses `config.json`, integrates with `oda_file_converter.py`.

- **`transport_manager.py`**
  - **Purpose**: Coordinates ladle transport.
  - **Key Classes**: `TransportManager`
  - **Important Variables**: `ladle_cars`, `cranes`, `pending_requests`
  - **Functionality**: Assigns transport tasks, manages queue.
  - **Interactions**: Controls `LadleCar`, `Crane`; uses `SpatialManager`.

- **`crane.py`**
  - **Purpose**: Simulates cranes for lifting ladles.
  - **Key Classes**: `Crane` (Salabim Component)
  - **Important Variables**: `status`, `position`
  - **Functionality**: Moves and lifts ladles within bays.
  - **Interactions**: Used by `TransportManager`, relies on `SpatialManager`.

- **`ladle_car.py`**
  - **Purpose**: Simulates ladle car transport.
  - **Key Classes**: `LadleCar` (Salabim Component)
  - **Important Variables**: `car_status`, `path`, `current_heat`
  - **Functionality**: Transports ladles between bays, updates heat temperature.
  - **Interactions**: Controlled by `TransportManager`, uses `Crane`.

- **`ladle_manager.py`**
  - **Purpose**: Manages ladle fleet.
  - **Key Classes**: `LadleManager` (Salabim Component)
  - **Important Variables**: `ladles`, `bay_ladles`
  - **Functionality**: Assigns and maintains ladles.
  - **Interactions**: Manages `Ladle`, integrates with simulation timing.

- **`ladle.py`**
  - **Purpose**: Represents individual ladles.
  - **Key Classes**: `Ladle` (Salabim Component)
  - **Important Variables**: `status`, `temperature`, `wear_level`
  - **Functionality**: Tracks ladle state, temperature, and wear.
  - **Interactions**: Controlled by `LadleManager`, holds `Heat`.

#### **Production Units**

- **`base_unit.py`**
  - **Purpose**: Base class for production units.
  - **Key Classes**: `BaseProductionUnit` (Salabim Component)
  - **Important Variables**: `heat_queue`, `metrics`, `state`
  - **Functionality**: Manages queues, metrics, and visualization.
  - **Interactions**: Parent for `EAF`, `LMF`, etc.; uses Salabim.

- **`eaf.py`**
  - **Purpose**: Simulates Electric Arc Furnace.
  - **Key Classes**: `EnhancedEAFUnit`
  - **Important Variables**: `process_time`, `can_slow_down`
  - **Functionality**: Processes heats, adjusts timing based on grade and downstream.
  - **Interactions**: Extends `BaseProductionUnit`, interacts with `RouteManager`.

- **`lmf.py`**
  - **Purpose**: Simulates Ladle Metallurgical Furnace.
  - **Key Classes**: `EnhancedLMFStation`
  - **Important Variables**: `warming_queue`, `max_warming_time`
  - **Functionality**: Refines steel, manages warming when downstream is busy.
  - **Interactions**: Extends `BaseProductionUnit`, uses `RouteManager`.

- **`degasser.py`**
  - **Purpose**: Simulates Vacuum Degasser.
  - **Key Classes**: `DegasserUnit`
  - **Important Variables**: `vacuum_level`, `grade_settings`
  - **Functionality**: Removes gases with grade-specific cycles.
  - **Interactions**: Extends `BaseProductionUnit`, updates `Heat`.

- **`caster.py`**
  - **Purpose**: Simulates Continuous Caster.
  - **Key Classes**: `EnhancedCaster`
  - **Important Variables**: `max_sequence`, `flow_interruption_threshold`
  - **Functionality**: Casts steel, manages sequences and turnarounds.
  - **Interactions**: Extends `BaseProductionUnit`, notifies `RouteManager`.

- **`heat.py`**
  - **Purpose**: Represents steel batches.
  - **Key Classes**: `Heat`
  - **Important Variables**: `temperature`, `process_history`
  - **Functionality**: Tracks heat properties and temperature loss.
  - **Interactions**: Used by units, updated by `LadleCar`.

#### **Analytics and Metrics**

- **`bottleneck_analyzer.py`**
  - **Purpose**: Analyzes production bottlenecks.
  - **Key Classes**: `BottleneckAnalyzer`
  - **Important Variables**: `metrics`, `thresholds`
  - **Functionality**: Identifies bottlenecks, provides recommendations.
  - **Interactions**: Uses `ProductionManager`, feeds `AnalyticsDashboard`.

- **`plant_metrics.py`**
  - **Purpose**: Tracks plant performance metrics.
  - **Key Classes**: `PlantMetricsTracker` (Salabim Component)
  - **Important Variables**: `metrics_history`, `unit_metrics`
  - **Functionality**: Collects and logs throughput, yield, etc.
  - **Interactions**: Depends on `ProductionManager`, supports UI display.

#### **Utilities and Support**

- **`cad_integration.py`**
  - **Purpose**: Integrates CAD layouts (DXF, SVG, CAD/DWG) as simulation backgrounds.
  - **Key Classes**: `CADBackground`
  - **Important Variables**: `cad_file_path`, `scale`, `visible_layers`, `cache_dir`
  - **Functionality**: Loads and parses DXF (with or without `ezdxf`), SVG, and converts CAD/DWG files, featuring auto-scaling, layer filtering, and caching.
  - **Interactions**: Uses `ezdxf` (optional), `oda_file_converter.py`, and integrates with `LayerManager` and `SpatialManager`.

- **`oda_file_converter.py`**
  - **Purpose**: Converts CAD files to DXF or SVG with multiple methods.
  - **Key Functions**: `convert_cad_to_dxf`
  - **Key Classes**: `EnhancedConversionDialog`
  - **Functionality**: Attempts conversion using ODA, LibreCAD, FreeCAD, or `python-dwg`, with detailed progress feedback and manual conversion guidance.
  - **Interactions**: Supports `cad_integration.py`, invoked via UI.

- **`layer_manager.py`**
  - **Purpose**: Manages visualization layers.
  - **Key Classes**: `LayerManager`, `Layer`
  - **Important Variables**: `layers`
  - **Functionality**: Toggles visibility of animation objects.
  - **Interactions**: Used by `dashboard.py`, integrates with Salabim.

## Known Issues and Limitations

- **CAD Conversion**: Requires external tools (e.g., ODA, LibreCAD) for non-DXF/SVG files; manual conversion may be needed if all methods fail.
- **Threading**: UI updates from non-main threads may cause errors.
- **Table Updates**: Issues with `QTableWidgetItem` in the analytics dashboard persist.
- **Reset**: Full reset requires application restart.
- **Memory**: Large CAD files may strain memory without `ezdxf` optimization; enable caching to mitigate.

## Troubleshooting

- **Logs**: Check `simulation_*.log` for detailed CAD parsing and conversion errors.
- **CAD Issues**: Ensure files are in DXF (AutoCAD 2018) or SVG format; pre-convert if import fails.
- **UI Freezes**: Restart the application or reduce simulation complexity.
- **Memory**: Use caching (`cad_cache_enabled`) and filter layers (`cad_visible_layers`) for large files.
- **File Reference**: Refer to updated "Detailed File Descriptions" for module-specific troubleshooting.

## Extending the Simulation

- **New Formats**: Extend `cad_integration.py` to support additional formats by adding parsing methods.
- **Custom Layers**: Modify `LayerManager` and `cad_integration.py` to handle new layer types.
- **Conversion Tools**: Add support for other converters in `oda_file_converter.py`.
- **Performance**: Adjust caching parameters or add entity culling in `cad_integration.py`.
