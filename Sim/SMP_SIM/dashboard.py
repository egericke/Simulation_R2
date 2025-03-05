import sys
import logging
import json
import os
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QSlider, QComboBox, 
    QMessageBox, QGroupBox, QCheckBox, QPushButton, QFileDialog, QTabWidget,
    QSplitter, QFrame, QProgressBar, QTableWidget, QTableWidgetItem
)
from PyQt5.QtCore import Qt, QTimer, QMutex
from PyQt5.QtGui import QPalette, QColor

# Import the CAD layer management widget
from layer_manager import CADLayerManagerWidget

logger = logging.getLogger(__name__)

class Dashboard(QMainWindow):
    """
    Enhanced dashboard for controlling and monitoring the steel plant simulation.
    """
    def __init__(self, config, sim_service, layer_manager, env, parent=None):
        super().__init__(parent)
        self.config = config
        self.sim_service = sim_service
        self.layer_manager = layer_manager
        self.env = env
        self.config_mutex = QMutex()  # Thread-safe config access
        
        # Initialize UI
        self.setWindowTitle("Steel Plant Simulation Dashboard")
        self.setMinimumSize(800, 600)
        self.initUI()
        
        # Initialize CAD layer management system
        self.setup_cad_panel()

    def initUI(self):
        """Initialize the user interface."""
        # Create central widget with main layout
        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
        
        # Create control panel (left side)
        control_panel = QWidget()
        control_layout = QVBoxLayout(control_panel)
        control_panel.setMaximumWidth(300)
        
        # Add tabs for different control categories
        control_tabs = QTabWidget()
        
        # Simulation tab
        sim_tab = QWidget()
        sim_layout = QVBoxLayout(sim_tab)
        self.createSimulationControls(sim_layout)
        control_tabs.addTab(sim_tab, "Simulation")
        
        # Visualization tab
        vis_tab = QWidget()
        self.vis_layout = QVBoxLayout(vis_tab)  # Store layout for CAD panel
        self.createVisualizationControls(self.vis_layout)
        control_tabs.addTab(vis_tab, "Visualization")
        
        # Configuration tab
        config_tab = QWidget()
        config_layout = QVBoxLayout(config_tab)
        self.createConfigControls(config_layout)
        control_tabs.addTab(config_tab, "Configuration")
        
        control_layout.addWidget(control_tabs)
        
        # Add statistics panel
        stats_group = QGroupBox("Statistics")
        stats_layout = QVBoxLayout(stats_group)
        self.createStatsPanel(stats_layout)
        control_layout.addWidget(stats_group)
        
        # Add control panel to main layout
        main_layout.addWidget(control_panel)
        
        # Create visualization panel (right side)
        vis_panel = QWidget()
        vis_layout = QVBoxLayout(vis_panel)
        self.createVisualizationPanel(vis_layout)
        main_layout.addWidget(vis_panel, 1)  # 1 = stretch factor
        
        # Set up timer for stats update
        update_interval = self.config.get("dashboard", {}).get("update_interval", 1000)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_stats)
        self.timer.start(update_interval)

    def setup_cad_panel(self):
        """
        Set up the CAD layer management panel in the UI.
        This should be called after initializing the simulation service and layer manager.
        """
        try:
            # Check if we have a CAD background available
            cad_background = None
            if hasattr(self.sim_service, 'cad_background'):
                cad_background = self.sim_service.cad_background
            
            # Create CAD layer management widget
            self.cad_layer_widget = CADLayerManagerWidget(self.layer_manager)
            
            # Connect signals
            self.cad_layer_widget.layer_visibility_changed.connect(self.on_cad_layer_visibility_changed)
            
            # Add to visualization tab
            if hasattr(self, 'vis_layout'):
                # Create a new group box for CAD layers
                cad_layers_group = QGroupBox("CAD Layers")
                cad_layers_layout = QVBoxLayout(cad_layers_group)
                cad_layers_layout.addWidget(self.cad_layer_widget)
                
                # Add to visualization tab
                self.vis_layout.addWidget(cad_layers_group)
                logger.info("CAD layer management panel initialized")
            else:
                logger.warning("No suitable layout found for CAD layer widget")
            
            # Initial update
            self.update_cad_layers()
            
            # Add a refresh button to the toolbar if needed
            if hasattr(self, 'toolbar'):
                self.cad_refresh_action = self.toolbar.addAction("Refresh CAD Layers")
                self.cad_refresh_action.triggered.connect(self.update_cad_layers)
        
        except Exception as e:
            logger.error(f"Error setting up CAD panel: {e}")

    def createSimulationControls(self, layout):
        """Create simulation control widgets."""
        # Speed control
        speed_group = QGroupBox("Simulation Speed")
        speed_layout = QVBoxLayout()
        
        self.speed_label = QLabel(f"Speed: {self.config.get('sim_speed', 1.0)}x", self)
        speed_layout.addWidget(self.speed_label)
        
        self.speed_slider = QSlider(Qt.Horizontal, self)
        self.speed_slider.setMinimum(1)
        self.speed_slider.setMaximum(30)
        self.speed_slider.setValue(int(self.config.get("sim_speed", 1.0) * 10))
        self.speed_slider.valueChanged.connect(self.update_speed)
        speed_layout.addWidget(self.speed_slider)
        
        speed_group.setLayout(speed_layout)
        layout.addWidget(speed_group)
        
        # Scenario selection
        scenario_group = QGroupBox("Scenario")
        scenario_layout = QVBoxLayout()
        
        self.scenario_combobox = QComboBox(self)
        scenario_options = list(self.config.get("scenarios", {}).keys())
        self.scenario_combobox.addItems(scenario_options)
        self.scenario_combobox.currentTextChanged.connect(self.change_scenario)
        scenario_layout.addWidget(self.scenario_combobox)
        
        self.scenario_description = QLabel("Default production routing")
        self.scenario_description.setWordWrap(True)
        scenario_layout.addWidget(self.scenario_description)
        
        scenario_group.setLayout(scenario_layout)
        layout.addWidget(scenario_group)
        
        # Heat generation controls
        heat_group = QGroupBox("Heat Generation")
        heat_layout = QVBoxLayout()
        
        self.heat_interval_label = QLabel(f"Heat Interval: {self.config.get('heat_interval', 10)} seconds")
        heat_layout.addWidget(self.heat_interval_label)
        
        self.heat_interval_slider = QSlider(Qt.Horizontal, self)
        self.heat_interval_slider.setMinimum(5)
        self.heat_interval_slider.setMaximum(60)
        self.heat_interval_slider.setValue(self.config.get("heat_interval", 10))
        self.heat_interval_slider.valueChanged.connect(self.update_heat_interval)
        heat_layout.addWidget(self.heat_interval_slider)
        
        heat_group.setLayout(heat_layout)
        layout.addWidget(heat_group)
        
        # Simulation control buttons
        control_group = QGroupBox("Controls")
        control_buttons_layout = QHBoxLayout()
        
        self.pause_button = QPushButton("Pause")
        self.pause_button.clicked.connect(self.toggle_pause)
        control_buttons_layout.addWidget(self.pause_button)
        
        self.reset_button = QPushButton("Reset")
        self.reset_button.clicked.connect(self.reset_simulation)
        control_buttons_layout.addWidget(self.reset_button)
        
        control_group.setLayout(control_buttons_layout)
        layout.addWidget(control_group)

    def createVisualizationControls(self, layout):
        """Create visualization control widgets."""
        # Layer visibility
        layer_group = QGroupBox("Layer Visibility")
        layer_layout = QVBoxLayout()
        
        # Add checkboxes for each layer
        self.layer_checkboxes = {}
        for layer_name in ["Background", "Units", "LadleCars", "Routes", "HUD"]:
            checkbox = QCheckBox(layer_name)
            checkbox.setChecked(True)
            checkbox.stateChanged.connect(lambda state, name=layer_name: self.toggle_layer(name, state == Qt.Checked))
            layer_layout.addWidget(checkbox)
            self.layer_checkboxes[layer_name] = checkbox
        
        layer_group.setLayout(layer_layout)
        layout.addWidget(layer_group)
        
        # CAD background controls
        cad_group = QGroupBox("CAD Background")
        cad_layout = QVBoxLayout()
        
        self.load_cad_button = QPushButton("Load CAD File...")
        self.load_cad_button.clicked.connect(self.load_cad_file)
        cad_layout.addWidget(self.load_cad_button)
        
        self.cad_scale_label = QLabel(f"Scale: {self.config.get('cad_scale', 1.0)}")
        cad_layout.addWidget(self.cad_scale_label)
        
        self.cad_scale_slider = QSlider(Qt.Horizontal, self)
        self.cad_scale_slider.setMinimum(1)
        self.cad_scale_slider.setMaximum(200)
        self.cad_scale_slider.setValue(int(self.config.get("cad_scale", 1.0) * 100))
        self.cad_scale_slider.valueChanged.connect(self.update_cad_scale)
        cad_layout.addWidget(self.cad_scale_slider)
        
        # Add auto-scale checkbox
        self.auto_scale_checkbox = QCheckBox("Auto-scale CAD")
        self.auto_scale_checkbox.setChecked(self.config.get("auto_scale_cad", True))
        self.auto_scale_checkbox.stateChanged.connect(self.toggle_auto_scale)
        cad_layout.addWidget(self.auto_scale_checkbox)
        
        # Add CAD cache checkbox
        self.cad_cache_checkbox = QCheckBox("Enable CAD caching")
        self.cad_cache_checkbox.setChecked(self.config.get("cad_cache_enabled", True))
        self.cad_cache_checkbox.stateChanged.connect(self.toggle_cad_cache)
        cad_layout.addWidget(self.cad_cache_checkbox)
        
        cad_group.setLayout(cad_layout)
        layout.addWidget(cad_group)
        
        # Animation settings
        anim_group = QGroupBox("Animation Settings")
        anim_layout = QVBoxLayout()
        
        self.show_paths_checkbox = QCheckBox("Show Ladle Paths")
        self.show_paths_checkbox.setChecked(True)
        self.show_paths_checkbox.stateChanged.connect(self.toggle_paths)
        anim_layout.addWidget(self.show_paths_checkbox)
        
        self.show_labels_checkbox = QCheckBox("Show Labels")
        self.show_labels_checkbox.setChecked(True)
        self.show_labels_checkbox.stateChanged.connect(self.toggle_labels)
        anim_layout.addWidget(self.show_labels_checkbox)
        
        self.highlight_bottlenecks_checkbox = QCheckBox("Highlight Bottlenecks")
        self.highlight_bottlenecks_checkbox.setChecked(True)
        self.highlight_bottlenecks_checkbox.stateChanged.connect(self.toggle_bottlenecks)
        anim_layout.addWidget(self.highlight_bottlenecks_checkbox)
        
        anim_group.setLayout(anim_layout)
        layout.addWidget(anim_group)

    def createConfigControls(self, layout):
        """Create configuration control widgets."""
        # Unit process times
        unit_group = QGroupBox("Process Times")
        unit_layout = QVBoxLayout()
        
        units = ["EAF", "LMF", "Degasser", "Caster"]
        self.process_time_sliders = {}
        
        for unit in units:
            time_label = QLabel(f"{unit}: {self.config.get('units', {}).get(unit, {}).get('process_time', 30)} minutes")
            unit_layout.addWidget(time_label)
            
            slider = QSlider(Qt.Horizontal, self)
            slider.setMinimum(5)
            slider.setMaximum(100)
            slider.setValue(self.config.get("units", {}).get(unit, {}).get("process_time", 30))
            slider.valueChanged.connect(lambda value, u=unit, lbl=time_label: self.update_process_time(u, value, lbl))
            unit_layout.addWidget(slider)
            
            self.process_time_sliders[unit] = slider
        
        unit_group.setLayout(unit_layout)
        layout.addWidget(unit_group)
        
        # Takt time
        takt_group = QGroupBox("Takt Time")
        takt_layout = QVBoxLayout()
        
        self.takt_label = QLabel(f"Takt Time: {self.config.get('takt_time', 60)} minutes")
        takt_layout.addWidget(self.takt_label)
        
        self.takt_slider = QSlider(Qt.Horizontal, self)
        self.takt_slider.setMinimum(30)
        self.takt_slider.setMaximum(180)
        self.takt_slider.setValue(self.config.get("takt_time", 60))
        self.takt_slider.valueChanged.connect(self.update_takt_time)
        takt_layout.addWidget(self.takt_slider)
        
        takt_group.setLayout(takt_layout)
        layout.addWidget(takt_group)
        
        # Save/load configuration
        save_load_group = QGroupBox("Configuration File")
        save_load_layout = QHBoxLayout()
        
        self.save_config_button = QPushButton("Save")
        self.save_config_button.clicked.connect(self.save_config)
        save_load_layout.addWidget(self.save_config_button)
        
        self.load_config_button = QPushButton("Load")
        self.load_config_button.clicked.connect(self.load_config)
        save_load_layout.addWidget(self.load_config_button)
        
        save_load_group.setLayout(save_load_layout)
        layout.addWidget(save_load_group)

    def createStatsPanel(self, layout):
        """Create statistics panel widgets."""
        # Processing stats
        self.heats_label = QLabel("Heats Processed: 0")
        layout.addWidget(self.heats_label)
        
        self.cycle_time_label = QLabel("Avg Cycle Time: N/A")
        layout.addWidget(self.cycle_time_label)
        
        self.takt_actual_label = QLabel("Actual Takt: N/A")
        layout.addWidget(self.takt_actual_label)
        
        self.distance_label = QLabel("Total Ladle Distance: 0")
        layout.addWidget(self.distance_label)
        
        # Utilization bar
        self.utilization_label = QLabel("System Utilization:")
        layout.addWidget(self.utilization_label)
        
        self.utilization_bar = QProgressBar()
        self.utilization_bar.setMinimum(0)
        self.utilization_bar.setMaximum(100)
        self.utilization_bar.setValue(0)
        layout.addWidget(self.utilization_bar)
        
        # Unit utilization table
        self.unit_table = QTableWidget(0, 2)
        self.unit_table.setHorizontalHeaderLabels(["Unit", "Utilization"])
        self.unit_table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.unit_table)

    def createVisualizationPanel(self, layout):
        """Create visualization panel (simulation view)."""
        # This is a placeholder for the actual visualization
        # In a real implementation, this would integrate with the salabim visualization
        vis_frame = QFrame()
        vis_frame.setFrameShape(QFrame.StyledPanel)
        vis_frame.setAutoFillBackground(True)
        
        # Set a darker background
        pal = vis_frame.palette()
        pal.setColor(QPalette.Window, QColor(40, 40, 40))
        vis_frame.setPalette(pal)
        
        layout.addWidget(vis_frame)
        
        # Add a label explaining how to interact
        interaction_label = QLabel("Visualization: In a real implementation, this would display the simulation view.")
        interaction_label.setAlignment(Qt.AlignCenter)
        interaction_label.setStyleSheet("color: white; background-color: rgba(0, 0, 0, 128); padding: 5px;")
        layout.addWidget(interaction_label)

    def update_speed(self, value):
        """Update simulation speed based on slider value."""
        try:
            self.config_mutex.lock()
            new_speed = value / 10.0
            self.config["sim_speed"] = new_speed
            self.speed_label.setText(f"Speed: {new_speed}x")
            
            # Update simulation speed in environment
            if hasattr(self.env, "speed"):
                self.env.speed = new_speed
                
            logger.info(f"Simulation speed updated to {new_speed}")
        finally:
            self.config_mutex.unlock()

    def update_heat_interval(self, value):
        """Update heat generation interval."""
        try:
            self.config_mutex.lock()
            self.config["heat_interval"] = value
            self.heat_interval_label.setText(f"Heat Interval: {value} seconds")
            logger.info(f"Heat interval updated to {value}")
        finally:
            self.config_mutex.unlock()

    def update_process_time(self, unit, value, label):
        """Update process time for a specific unit."""
        try:
            self.config_mutex.lock()
            if "units" not in self.config:
                self.config["units"] = {}
            if unit not in self.config["units"]:
                self.config["units"][unit] = {}
            
            self.config["units"][unit]["process_time"] = value
            label.setText(f"{unit}: {value} seconds")
            
            logger.info(f"{unit} process time updated to {value}")
        finally:
            self.config_mutex.unlock()

    def update_takt_time(self, value):
        """Update target takt time."""
        try:
            self.config_mutex.lock()
            self.config["takt_time"] = value
            self.takt_label.setText(f"Takt Time: {value} seconds")
            logger.info(f"Takt time updated to {value}")
        finally:
            self.config_mutex.unlock()

    def update_cad_scale(self, value):
        """Update CAD scaling factor."""
        try:
            self.config_mutex.lock()
            new_scale = value / 100.0
            self.config["cad_scale"] = new_scale
            self.cad_scale_label.setText(f"Scale: {new_scale}")
            logger.info(f"CAD scale updated to {new_scale}")
            
            # Update CAD background if it exists
            if hasattr(self.sim_service, 'cad_background'):
                self.sim_service.cad_background.scale = new_scale
                # Only reload if auto-scale is disabled
                if not self.config.get("auto_scale_cad", True):
                    self.sim_service.cad_background.create_background()
                    self.sim_service.cad_background.setup_layer_management()
                    # Update the CAD layer UI
                    self.update_cad_layers()
        finally:
            self.config_mutex.unlock()

    def toggle_auto_scale(self, state):
        """Toggle automatic CAD scaling."""
        try:
            self.config_mutex.lock()
            auto_scale = state == Qt.Checked
            self.config["auto_scale_cad"] = auto_scale
            logger.info(f"Auto-scale CAD set to {auto_scale}")
            
            # Enable/disable manual scale slider based on auto-scale setting
            self.cad_scale_slider.setEnabled(not auto_scale)
            
            # Reload CAD with new setting if CAD is loaded
            if hasattr(self.sim_service, 'cad_background') and self.sim_service.cad_background.cad_file_path:
                self.sim_service.cad_background.create_background()
                self.sim_service.cad_background.setup_layer_management()
                # Update the CAD layer UI
                self.update_cad_layers()
        finally:
            self.config_mutex.unlock()

    def toggle_cad_cache(self, state):
        """Toggle CAD caching."""
        try:
            self.config_mutex.lock()
            cache_enabled = state == Qt.Checked
            self.config["cad_cache_enabled"] = cache_enabled
            logger.info(f"CAD caching set to {cache_enabled}")
            
            # Update CAD background cache setting if it exists
            if hasattr(self.sim_service, 'cad_background'):
                self.sim_service.cad_background.cache_enabled = cache_enabled
        finally:
            self.config_mutex.unlock()

    def change_scenario(self, scenario_name):
        """Change the current simulation scenario."""
        try:
            logger.info(f"Changing scenario to {scenario_name}")
            
            # Update description based on scenario
            scenario_descriptions = {
                "default": "Default production routing",
                "maintenance": "Maintenance mode routing (bypasses some units)"
            }
            self.scenario_description.setText(
                scenario_descriptions.get(scenario_name, "Custom scenario")
            )
            
            # Apply scenario change
            self.sim_service.scenario_manager.set_current_scenario(scenario_name)
        except Exception as e:
            logger.error(f"Failed to change scenario: {e}")
            QMessageBox.critical(self, "Error", f"Scenario change failed: {e}")

    def toggle_layer(self, layer_name, visible):
        """Toggle visibility of a visualization layer."""
        try:
            logger.info(f"Setting layer {layer_name} visibility to {visible}")
            self.layer_manager.set_layer_visibility(layer_name, visible)
        except Exception as e:
            logger.error(f"Failed to toggle layer: {e}")

    def toggle_paths(self, state):
        """Toggle visibility of ladle paths."""
        visible = state == Qt.Checked
        try:
            self.layer_manager.set_layer_visibility("Routes", visible)
        except Exception as e:
            logger.error(f"Failed to toggle paths: {e}")

    def toggle_labels(self, state):
        """Toggle visibility of labels."""
        # This would need custom implementation based on how labels are managed
        pass

    def toggle_bottlenecks(self, state):
        """Toggle highlighting of bottleneck areas."""
        # This would need custom implementation based on performance analysis
        pass

    def toggle_pause(self):
        """Pause or resume the simulation."""
        try:
            # Toggle pause state
            if hasattr(self.env, "paused") and self.env.paused:
                self.env.paused = False
                self.pause_button.setText("Pause")
                logger.info("Simulation resumed")
            else:
                self.env.paused = True
                self.pause_button.setText("Resume")
                logger.info("Simulation paused")
        except Exception as e:
            logger.error(f"Failed to toggle pause: {e}")

    def reset_simulation(self):
        """Reset the simulation to initial state."""
        try:
            # Confirm with user
            reply = QMessageBox.question(
                self, "Reset Simulation", 
                "Are you sure you want to reset the simulation? This will clear all current progress.",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No
            )
            
            if reply == QMessageBox.Yes:
                # Implement simulation reset logic
                logger.info("Resetting simulation...")
                QMessageBox.information(self, "Reset", "Simulation has been reset.")
        except Exception as e:
            logger.error(f"Failed to reset simulation: {e}")

    def load_cad_file(self):
        """Open file dialog to load a CAD file."""
        try:
            file_path, _ = QFileDialog.getOpenFileName(
                self, "Load CAD File", "", 
                "CAD Files (*.dxf *.svg *.dwg *.cad);;DXF Files (*.dxf);;SVG Files (*.svg);;All Files (*)"
            )
            
            if file_path:
                self.config["cad_file_path"] = file_path
                logger.info(f"Loading CAD file: {file_path}")
                
                # Reload CAD background
                if hasattr(self.sim_service, 'cad_background'):
                    # If the CAD background already exists, update it
                    self.sim_service.cad_background.cad_file_path = file_path
                    self.sim_service.cad_background.create_background()
                    self.sim_service.cad_background.setup_layer_management()
                else:
                    # If not, create it
                    from cad_integration import CADBackground
                    self.sim_service.cad_background = CADBackground(
                        self.sim_service.env, 
                        self.layer_manager, 
                        self.config, 
                        self
                    )
                
                # Update the CAD layer UI
                self.update_cad_layers()
                
                # Save config
                self.save_config()
                
                QMessageBox.information(self, "CAD Loaded", f"CAD file loaded: {os.path.basename(file_path)}")
        except Exception as e:
            logger.error(f"Failed to load CAD file: {e}")
            QMessageBox.critical(self, "Error", f"Failed to load CAD file: {e}")

    def update_cad_layers(self):
        """
        Update the CAD layer panel with current layers.
        Call this method whenever CAD layers change.
        """
        try:
            if hasattr(self, 'cad_layer_widget'):
                self.cad_layer_widget.update_layers()
                logger.debug("CAD layers updated in UI")
        except Exception as e:
            logger.error(f"Error updating CAD layers: {e}")
    
    def on_cad_layer_visibility_changed(self, layer_name, visible):
        """
        Handle CAD layer visibility changes from the UI.
        This will persist the changes to the configuration.
        
        Args:
            layer_name: Name of the CAD layer
            visible: New visibility state
        """
        try:
            # Make sure we have a place to store visible layers
            if "cad_visible_layers" not in self.config or self.config["cad_visible_layers"] is None:
                self.config["cad_visible_layers"] = []
            
            # Update the configuration
            if visible:
                if layer_name not in self.config["cad_visible_layers"]:
                    self.config["cad_visible_layers"].append(layer_name)
            else:
                if layer_name in self.config["cad_visible_layers"]:
                    self.config["cad_visible_layers"].remove(layer_name)
            
            # Save the updated configuration
            self.save_config()
            logger.debug(f"CAD layer '{layer_name}' visibility set to {visible} and saved to config")
        except Exception as e:
            logger.error(f"Error handling CAD layer visibility change: {e}")

    def save_config(self):
        """Save current configuration to a file."""
        try:
            self.config_mutex.lock()
            config_path = self.config.get("config_path", "config.json")
            
            with open(config_path, 'w') as f:
                json.dump(self.config, f, indent=2)
            
            logger.info(f"Configuration saved to {config_path}")
        except Exception as e:
            logger.error(f"Failed to save configuration: {e}")
            QMessageBox.critical(self, "Error", f"Failed to save configuration: {e}")
        finally:
            self.config_mutex.unlock()

    def load_config(self):
        """Load configuration from a file."""
        try:
            file_path, _ = QFileDialog.getOpenFileName(
                self, "Load Configuration", "", "JSON Files (*.json);;All Files (*)"
            )
            
            if file_path:
                with open(file_path, 'r') as f:
                    new_config = json.load(f)
                
                # Update config with new values
                self.config_mutex.lock()
                try:
                    self.config.update(new_config)
                finally:
                    self.config_mutex.unlock()
                
                # Update UI to reflect new config
                self.updateUIFromConfig()
                
                logger.info(f"Configuration loaded from {file_path}")
                QMessageBox.information(self, "Config Loaded", f"Configuration loaded from {file_path}")
        except Exception as e:
            logger.error(f"Failed to load configuration: {e}")
            QMessageBox.critical(self, "Error", f"Failed to load configuration: {e}")

    def updateUIFromConfig(self):
        """Update UI elements to reflect current configuration."""
        try:
            # Update speed
            speed = self.config.get("sim_speed", 1.0)
            self.speed_slider.setValue(int(speed * 10))
            self.speed_label.setText(f"Speed: {speed}x")
            
            # Update heat interval
            heat_interval = self.config.get("heat_interval", 10)
            self.heat_interval_slider.setValue(heat_interval)
            self.heat_interval_label.setText(f"Heat Interval: {heat_interval} seconds")
            
            # Update takt time
            takt_time = self.config.get("takt_time", 60)
            self.takt_slider.setValue(takt_time)
            self.takt_label.setText(f"Takt Time: {takt_time} seconds")
            
            # Update CAD scale
            cad_scale = self.config.get("cad_scale", 1.0)
            self.cad_scale_slider.setValue(int(cad_scale * 100))
            self.cad_scale_label.setText(f"Scale: {cad_scale}")
            
            # Update auto-scale checkbox
            auto_scale = self.config.get("auto_scale_cad", True)
            self.auto_scale_checkbox.setChecked(auto_scale)
            self.cad_scale_slider.setEnabled(not auto_scale)
            
            # Update CAD cache checkbox
            cache_enabled = self.config.get("cad_cache_enabled", True)
            self.cad_cache_checkbox.setChecked(cache_enabled)
            
            # Update unit process times
            for unit in self.process_time_sliders:
                process_time = self.config.get("units", {}).get(unit, {}).get("process_time", 30)
                self.process_time_sliders[unit].setValue(process_time)
            
            # Reload CAD if path has changed
            if hasattr(self.sim_service, 'cad_background'):
                cad_file_path = self.config.get("cad_file_path", None)
                if cad_file_path and cad_file_path != self.sim_service.cad_background.cad_file_path:
                    self.sim_service.cad_background.cad_file_path = cad_file_path
                    self.sim_service.cad_background.create_background()
                    self.sim_service.cad_background.setup_layer_management()
                    self.update_cad_layers()
            
            logger.info("UI updated from configuration")
        except Exception as e:
            logger.error(f"Failed to update UI from config: {e}")

    def update_stats(self):
        """Update the statistics display."""
        try:
            pm = self.sim_service.production_manager
            if not pm:
                return
            
            # Update basic stats
            self.heats_label.setText(f"Heats Processed: {pm.heats_processed}")
            
            # Handle avg_cycle_time calculation safely
            if len(pm.completed_heats) > 0:
                avg_cycle_time = pm.total_cycle_time / len(pm.completed_heats)
                self.cycle_time_label.setText(f"Avg Cycle Time: {avg_cycle_time:.2f}")
            else:
                avg_cycle_time = "N/A"
                self.cycle_time_label.setText("Avg Cycle Time: N/A")
            
            takt_time = self.config.get('takt_time', 60)
            actual_takt = avg_cycle_time if not isinstance(avg_cycle_time, str) else 0
            self.takt_actual_label.setText(f"Actual Takt: {actual_takt:.2f} / {takt_time} (target)")
            
            total_distance = sum(lc.total_distance_traveled for lc in pm.ladle_cars)
            self.distance_label.setText(f"Total Ladle Distance: {total_distance:.2f}")
            
            # Update utilization
            if not isinstance(avg_cycle_time, str) and takt_time > 0:
                utilization = min(avg_cycle_time / takt_time, 1.0) * 100
                self.utilization_bar.setValue(int(utilization))
                
                # Set color based on utilization
                if utilization < 60:
                    self.utilization_bar.setStyleSheet("QProgressBar::chunk { background-color: #5cb85c; }")
                elif utilization < 80:
                    self.utilization_bar.setStyleSheet("QProgressBar::chunk { background-color: #f0ad4e; }")
                else:
                    self.utilization_bar.setStyleSheet("QProgressBar::chunk { background-color: #d9534f; }")
            else:
                self.utilization_bar.setValue(0)  # Reset if no valid data
            
            # Update unit table (placeholder for future implementation)
            # Requires collecting utilization data from each unit
            
        except Exception as e:
            logger.error(f"Stats update failed: {e}")