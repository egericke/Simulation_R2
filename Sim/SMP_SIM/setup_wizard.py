import sys
import json
import math
import fitz  # PyMuPDF for PDF rendering
from PyQt5.QtWidgets import (QApplication, QWizard, QWizardPage, QLabel, QVBoxLayout, QHBoxLayout,
                             QLineEdit, QPushButton, QFileDialog, QDoubleSpinBox, QTableWidget,
                             QTableWidgetItem, QMessageBox, QScrollArea, QWidget, QFrame,
                             QComboBox, QCheckBox, QSpinBox, QGroupBox, QGridLayout, QInputDialog)
from PyQt5.QtCore import Qt, QRectF
from PyQt5.QtGui import QPainter, QPen, QColor, QPixmap
import logging

logger = logging.getLogger(__name__)

def is_valid_bay(bay_pos):
    """Check if a bay position dictionary is valid.

    Args:
        bay_pos (dict): The bay position dictionary to validate.

    Returns:
        bool: True if the bay has all required keys ("x", "y", "width", "height"), False otherwise.
    """
    if not isinstance(bay_pos, dict):
        logger.error(f"Bay position is not a dictionary: {type(bay_pos)}")
        return False
        
    required_keys = {"x", "y", "width", "height"}
    has_required_keys = required_keys.issubset(bay_pos.keys())
    
    if not has_required_keys:
        missing_keys = required_keys - set(bay_pos.keys())
        logger.error(f"Bay position missing required keys: {missing_keys}")
        return False
        
    # Check that values are numeric and positive
    for key in required_keys:
        try:
            value = float(bay_pos[key])
            if key in ('width', 'height') and value <= 0:
                logger.error(f"Bay {key} must be positive, got {value}")
                return False
        except (ValueError, TypeError):
            logger.error(f"Bay {key} has non-numeric value: {bay_pos[key]}")
            return False
            
    return True

def is_position_in_bay(position, bay):
    """Check if a position is within a bay's boundaries.
    
    Args:
        position (dict): Position with 'x' and 'y' keys.
        bay (dict): Bay with 'x', 'y', 'width', 'height' keys.
        
    Returns:
        bool: True if position is within bay, False otherwise.
    """
    if not is_valid_bay(bay):
        return False
        
    try:
        x = float(position.get('x', 0))
        y = float(position.get('y', 0))
        bay_x = float(bay['x'])
        bay_y = float(bay['y'])
        bay_width = float(bay['width']) 
        bay_height = float(bay['height'])
        
        return (bay_x <= x <= bay_x + bay_width and 
                bay_y <= y <= bay_y + bay_height)
    except (ValueError, TypeError) as e:
        logger.error(f"Error checking position in bay: {e}")
        return False


class SetupWizard(QWizard):
    """A wizard for setting up the simulation configuration."""

    def __init__(self, config=None, env=None, sim_service=None, layer_manager=None, parent=None):
        """Initialize the setup wizard.

        Args:
            config (dict, optional): Initial configuration. Defaults to None.
            env: Unused environment parameter (for compatibility). Defaults to None.
            sim_service: Unused simulation service parameter (for compatibility). Defaults to None.
            layer_manager: Unused layer manager parameter (for compatibility). Defaults to None.
            parent (QWidget, optional): Parent widget. Defaults to None.
        """
        super().__init__(parent)
        self.setWindowTitle("Simulation Setup Wizard")
        self.resize(800, 600)

        if config is None:
            self.config = {}
        else:
            self.config = config.copy()

        if "bays" not in self.config or not isinstance(self.config["bays"], dict):
            self.config["bays"] = {}

        self._validate_bays()
        
        # Store reference to simulation service
        self.sim_service = sim_service

        self.addPage(CADLoadPage(self.config))
        self.addPage(EquipmentConfigPage(self.config))
        self.addPage(PlacementPage(self.config))
        self.addPage(ProductionParametersPage(self.config))
        self.addPage(TransportationConfigPage(self.config))
        self.addPage(SummaryPage(self.config, self.sim_service))

        self.setWizardStyle(QWizard.ModernStyle)
        self.setOption(QWizard.HaveHelpButton, True)
        self.helpRequested.connect(self.show_help)
        
        logger.info("Setup wizard initialized")

    def _validate_bays(self):
        """Validate and clean the bays configuration by removing invalid entries."""
        bays = self.config.get("bays", {})
        invalid_bays = []

        for bay_name, bay_pos in bays.items():
            if not is_valid_bay(bay_pos):
                invalid_bays.append(bay_name)

        for bay_name in invalid_bays:
            del self.config["bays"][bay_name]
            logger.warning(f"Removed invalid bay: {bay_name}")

    def show_help(self):
        """Show help text for the current page."""
        current_page = self.currentPage()
        if hasattr(current_page, 'helpText'):
            QMessageBox.information(self, "Help", current_page.helpText)
        else:
            QMessageBox.information(self, "Help", "No help available for this page.")

    def accept(self):
        """Accept the wizard and apply the configuration."""
        self.applyConfiguration()
        super().accept()

    def applyConfiguration(self):
        """Apply the configuration and save a backup to 'config_backup.json'."""
        try:
            with open('config_backup.json', 'w') as config_file:
                json.dump(self.config, config_file, indent=2)
            logger.info("Configuration backup saved to config_backup.json")
            
            # Update SimulationService if available
            if hasattr(self, 'sim_service') and self.sim_service:
                self.sim_service.update_config(self.config)
        except Exception as e:
            logger.error(f"Failed to save configuration backup: {e}", exc_info=True)
            QMessageBox.critical(self, "Error", f"Failed to save configuration backup: {e}")


class CADLoadPage(QWizardPage):
    """Page for selecting the CAD file and defining scale."""

    def __init__(self, config, parent=None):
        """Initialize the CAD load page.

        Args:
            config (dict): The configuration dictionary.
            parent (QWidget, optional): Parent widget. Defaults to None.
        """
        super().__init__(parent)
        self.config = config
        self.setTitle("CAD File Selection")
        self.setSubTitle("Select your facility layout CAD file and define scale.")
        layout = QVBoxLayout()

        self.file_label = QLabel("CAD File: Not selected")
        layout.addWidget(self.file_label)

        file_btn = QPushButton("Browse CAD File")
        file_btn.clicked.connect(self.browse_file)
        layout.addWidget(file_btn)

        scale_group = QGroupBox("Scale Configuration")
        scale_layout = QGridLayout()

        scale_layout.addWidget(QLabel("CAD Scale:"), 0, 0)
        self.scale_spin = QDoubleSpinBox()
        self.scale_spin.setRange(0.001, 1000.0)
        self.scale_spin.setValue(self.config.get("cad_scale", 1.0))
        scale_layout.addWidget(self.scale_spin, 0, 1)

        self.pdf_fields = []
        if self.config.get("cad_file_path", "").lower().endswith('.pdf'):
            scale_layout.addWidget(QLabel("PDF Real Width (m):"), 1, 0)
            self.pdf_width_spin = QDoubleSpinBox()
            self.pdf_width_spin.setRange(1.0, 10000.0)
            self.pdf_width_spin.setValue(self.config.get("pdf_real_width", 100.0))
            scale_layout.addWidget(self.pdf_width_spin, 1, 1)
            self.pdf_fields.append(self.pdf_width_spin)

            scale_layout.addWidget(QLabel("PDF Real Height (m):"), 2, 0)
            self.pdf_height_spin = QDoubleSpinBox()
            self.pdf_height_spin.setRange(1.0, 10000.0)
            self.pdf_height_spin.setValue(self.config.get("pdf_real_height", 100.0))
            scale_layout.addWidget(self.pdf_height_spin, 2, 1)
            self.pdf_fields.append(self.pdf_height_spin)

        scale_group.setLayout(scale_layout)
        layout.addWidget(scale_group)
        self.setLayout(layout)

        self.helpText = (
            "Select a CAD file (e.g., PDF or DXF) representing your facility layout.\n\n"
            "1. CAD Scale: Define how CAD units translate to simulation units (default 1:1).\n"
            "2. For PDF files, specify the real-world width and height in meters to set the scale."
        )

    def browse_file(self):
        """Open a file dialog to select a CAD file."""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select CAD File", "", "CAD Files (*.pdf *.dxf);;All Files (*)"
        )
        if file_path:
            self.file_label.setText(f"CAD File: {file_path}")
            self.config["cad_file_path"] = file_path
            if file_path.lower().endswith('.pdf') and not self.pdf_fields:
                scale_group = self.findChild(QGroupBox, "Scale Configuration")
                scale_layout = scale_group.layout()
                scale_layout.addWidget(QLabel("PDF Real Width (m):"), 1, 0)
                self.pdf_width_spin = QDoubleSpinBox()
                self.pdf_width_spin.setRange(1.0, 10000.0)
                self.pdf_width_spin.setValue(100.0)
                scale_layout.addWidget(self.pdf_width_spin, 1, 1)
                self.pdf_fields.append(self.pdf_width_spin)

                scale_layout.addWidget(QLabel("PDF Real Height (m):"), 2, 0)
                self.pdf_height_spin = QDoubleSpinBox()
                self.pdf_height_spin.setRange(1.0, 10000.0)
                self.pdf_height_spin.setValue(100.0)
                scale_layout.addWidget(self.pdf_height_spin, 2, 1)
                self.pdf_fields.append(self.pdf_height_spin)
                
            logger.info(f"Selected CAD file: {file_path}")

    def validatePage(self):
        """Validate the page before proceeding.

        Returns:
            bool: True if valid, False otherwise.
        """
        if "cad_file_path" not in self.config or not self.config.get("cad_file_path"):
            logger.warning("No CAD file selected")
            QMessageBox.warning(self, "No File Selected", "Please select a CAD file.")
            return False
        self.config["cad_scale"] = self.scale_spin.value()
        if self.config.get("cad_file_path", "").lower().endswith('.pdf'):
            self.config["pdf_real_width"] = self.pdf_width_spin.value()
            self.config["pdf_real_height"] = self.pdf_height_spin.value()
        logger.info("CAD page validated successfully")
        return True


class EquipmentConfigPage(QWizardPage):
    """Page for configuring equipment types and their parameters."""

    def __init__(self, config, parent=None):
        """Initialize the equipment configuration page.

        Args:
            config (dict): The configuration dictionary.
            parent (QWidget, optional): Parent widget. Defaults to None.
        """
        super().__init__(parent)
        self.config = config
        self.setTitle("Equipment Configuration")
        self.setSubTitle("Define the number of each equipment type and their process times and sizes.")
        layout = QVBoxLayout()

        self.table = QTableWidget(4, 5)  # Add columns for width and height
        self.table.setHorizontalHeaderLabels(["Equipment Type", "Capacity", "Process Time (min)", "Width (units)", "Height (units)"])
        equipment_types = ["EAF", "LMF", "Degasser", "Caster"]
        default_process_times = {"EAF": 50, "LMF": 30, "Degasser": 40, "Caster": 20}
        default_sizes = {"EAF": {"width": 20, "height": 40}, "LMF": {"width": 15, "height": 30}, 
                         "Degasser": {"width": 15, "height": 30}, "Caster": {"width": 25, "height": 50}}

        for row, unit_type in enumerate(equipment_types):
            self.table.setItem(row, 0, QTableWidgetItem(unit_type))
            capacity = self.config.get("units", {}).get(unit_type, {}).get("capacity", 1)
            process_time = self.config.get("units", {}).get(unit_type, {}).get("process_time", default_process_times[unit_type])
            width = self.config.get("units", {}).get(unit_type, {}).get("width", default_sizes[unit_type]["width"])
            height = self.config.get("units", {}).get(unit_type, {}).get("height", default_sizes[unit_type]["height"])
            self.table.setItem(row, 1, QTableWidgetItem(str(capacity)))
            self.table.setItem(row, 2, QTableWidgetItem(str(process_time)))
            self.table.setItem(row, 3, QTableWidgetItem(str(width)))
            self.table.setItem(row, 4, QTableWidgetItem(str(height)))

        layout.addWidget(self.table)
        self.setLayout(layout)

        self.helpText = (
            "Configure your steel plant equipment:\n\n"
            "1. Capacity: Number of units for each equipment type.\n"
            "2. Process Time: Duration in minutes each unit takes to process a heat.\n"
            "3. Width & Height: Equipment dimensions for layout visualization."
        )

    def validatePage(self):
        """Validate the equipment configuration.

        Returns:
            bool: True if valid, False otherwise.
        """
        self.config["units"] = {}
        for row in range(self.table.rowCount()):
            unit_type_item = self.table.item(row, 0)
            capacity_item = self.table.item(row, 1)
            process_time_item = self.table.item(row, 2)
            width_item = self.table.item(row, 3)
            height_item = self.table.item(row, 4)

            if not (unit_type_item and capacity_item and process_time_item and width_item and height_item):
                logger.warning(f"Missing data for equipment in row {row}")
                QMessageBox.warning(self, "Invalid Input", f"Missing data for row {row}.")
                return False

            unit_type = unit_type_item.text()
            try:
                capacity = int(capacity_item.text())
                process_time = int(process_time_item.text())
                width = int(width_item.text())
                height = int(height_item.text())
                if capacity < 1 or process_time < 1 or width < 1 or height < 1:
                    raise ValueError("Values must be positive integers")
                self.config["units"][unit_type] = {
                    "capacity": capacity,
                    "process_time": process_time,
                    "width": width,
                    "height": height
                }
            except ValueError as e:
                logger.error(f"Invalid data for {unit_type}: {e}", exc_info=True)
                QMessageBox.warning(self, "Invalid Input", f"Invalid data for {unit_type}: {e}")
                return False
        logger.info("Equipment configuration validated successfully")
        return True


class PlacementPage(QWizardPage):
    """Page for placing equipment on the facility layout with PDF background."""

    def __init__(self, config, parent=None):
        """Initialize the equipment placement page.

        Args:
            config (dict): The configuration dictionary.
            parent (QWidget, optional): Parent widget. Defaults to None.
        """
        super().__init__(parent)
        self.config = config
        self.setTitle("Equipment Placement")
        self.setSubTitle("Place equipment on the facility layout overlaid on the CAD file.")
        layout = QVBoxLayout()

        preview_group = QGroupBox("Layout Preview")
        preview_layout = QHBoxLayout()

        self.scene_widget = QWidget()
        self.scene_widget.setMinimumSize(400, 300)
        self.scene_widget.setStyleSheet("background-color: white; border: 1px solid gray;")
        preview_layout.addWidget(self.scene_widget)

        controls_layout = QVBoxLayout()
        
        # Enhanced button styling for better visibility
        draw_bay_btn = QPushButton("Draw Bay")
        draw_bay_btn.setStyleSheet("background-color: #4CAF50; color: white; font-size: 14px; padding: 5px;")
        draw_bay_btn.clicked.connect(self.start_drawing_bay)
        draw_bay_btn.setToolTip("Click to start drawing a bay on the layout")
        controls_layout.addWidget(draw_bay_btn)

        undo_bay_btn = QPushButton("Undo Last Bay")
        undo_bay_btn.setStyleSheet("background-color: #f44336; color: white; font-size: 14px; padding: 5px;")
        undo_bay_btn.clicked.connect(self.undo_last_bay)
        undo_bay_btn.setToolTip("Undo the last bay addition")
        controls_layout.addWidget(undo_bay_btn)

        clear_bays_btn = QPushButton("Clear All Bays")
        clear_bays_btn.setStyleSheet("background-color: #2196F3; color: white; font-size: 14px; padding: 5px;")
        clear_bays_btn.clicked.connect(self.clear_bays)
        clear_bays_btn.setToolTip("Clear all bays from the layout")
        controls_layout.addWidget(clear_bays_btn)

        zoom_in_btn = QPushButton("Zoom In")
        zoom_in_btn.setStyleSheet("background-color: #9C27B0; color: white; font-size: 14px; padding: 5px;")
        zoom_in_btn.clicked.connect(self.zoom_in)
        zoom_in_btn.setToolTip("Zoom in on the layout")
        controls_layout.addWidget(zoom_in_btn)

        zoom_out_btn = QPushButton("Zoom Out")
        zoom_out_btn.setStyleSheet("background-color: #9C27B0; color: white; font-size: 14px; padding: 5px;")
        zoom_out_btn.clicked.connect(self.zoom_out)
        zoom_out_btn.setToolTip("Zoom out on the layout")
        controls_layout.addWidget(zoom_out_btn)

        controls_layout.addStretch()
        preview_layout.addLayout(controls_layout)
        preview_group.setLayout(preview_layout)
        layout.addWidget(preview_group)

        table_group = QGroupBox("Equipment Positions")
        table_layout = QVBoxLayout()
        self.position_table = QTableWidget(0, 5)
        self.position_table.setHorizontalHeaderLabels(["Bay", "Equipment Type", "Unit ID", "X Position", "Y Position"])
        table_layout.addWidget(self.position_table)

        buttons_layout = QHBoxLayout()
        auto_btn = QPushButton("Auto-Position Equipment")
        auto_btn.clicked.connect(self.auto_position_equipment)
        buttons_layout.addWidget(auto_btn)
        table_layout.addLayout(buttons_layout)
        table_group.setLayout(table_layout)
        layout.addWidget(table_group)

        self.setLayout(layout)
        self.bay_drawing = False
        self.start_pos = None
        self.current_rect = None
        self.bay_undo_stack = list(self.config.get("bays", {}).items())
        self.scene_widget.installEventFilter(self)
        self.zoom_factor = 1.0
        self.background_pixmap = None
        self.load_pdf_background()

        self.helpText = (
            "Place equipment on your facility layout:\n\n"
            "1. Draw bays by clicking and dragging on the preview (overlaid on the CAD file).\n"
            "2. Use 'Zoom In' and 'Zoom Out' buttons to adjust the view.\n"
            "3. Use 'Clear All Bays' to start fresh.\n"
            "4. Auto-position equipment within bays or edit positions manually."
        )

    def load_pdf_background(self):
        """Load the PDF as a background pixmap."""
        cad_file = self.config.get("cad_file_path", "")
        if cad_file and cad_file.lower().endswith('.pdf'):
            try:
                doc = fitz.open(cad_file)
                page = doc.load_page(0)
                pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))  # Higher resolution
                img_data = pix.tobytes("ppm")
                self.background_pixmap = QPixmap()
                self.background_pixmap.loadFromData(img_data)
                logger.info(f"PDF background loaded successfully: {cad_file}")
            except Exception as e:
                logger.error(f"Failed to load PDF: {e}", exc_info=True)
                QMessageBox.warning(self, "PDF Load Error", f"Failed to load PDF: {e}")
                self.background_pixmap = None

    def check_bay_name_unique(self, bay_name):
        """Check if the bay name is unique.
        
        Args:
            bay_name (str): Name to check for uniqueness
            
        Returns:
            bool: True if name is unique, False otherwise
        """
        return bay_name not in self.config["bays"]

    def eventFilter(self, obj, event):
        """Handle events for the scene widget.

        Args:
            obj (QObject): The object receiving the event.
            event (QEvent): The event being processed.

        Returns:
            bool: True if the event was handled, False otherwise.
        """
        if obj == self.scene_widget:
            if event.type() == event.MouseButtonPress and event.button() == Qt.LeftButton:
                if not self.bay_drawing:
                    return False
                self.start_pos = event.pos() / self.zoom_factor  # Adjust for zoom
                return True
            elif event.type() == event.MouseMove and self.bay_drawing and self.start_pos:
                self.current_rect = QRectF(self.start_pos, event.pos() / self.zoom_factor).normalized()
                self.scene_widget.update()
                return True
            elif event.type() == event.MouseButtonRelease and self.bay_drawing:
                end_pos = event.pos() / self.zoom_factor
                rect = QRectF(self.start_pos, end_pos).normalized()
                if rect.width() > 10 and rect.height() > 10:
                    bay_name, ok = QInputDialog.getText(self, "Bay Name", "Enter bay name:")
                    if ok and bay_name:
                        # Check if bay name is unique
                        if not self.check_bay_name_unique(bay_name):
                            logger.warning(f"Bay name already exists: {bay_name}")
                            QMessageBox.warning(self, "Duplicate Bay Name", 
                                             f"Bay name '{bay_name}' already exists. Please choose a unique name.")
                        else:
                            self.config["bays"][bay_name] = {
                                "x": rect.x(), "y": rect.y(),
                                "width": rect.width(), "height": rect.height()
                            }
                            self.bay_undo_stack.append((bay_name, self.config["bays"][bay_name]))
                            logger.info(f"Created new bay: {bay_name}")
                self.bay_drawing = False
                self.start_pos = None
                self.current_rect = None
                self.scene_widget.update()
                return True
            elif event.type() == event.Paint:
                painter = QPainter(self.scene_widget)
                painter.setRenderHint(QPainter.Antialiasing)
                # Apply zoom scaling
                painter.scale(self.zoom_factor, self.zoom_factor)
                self.draw_bay_boundaries(painter)
                self.render_equipment_items(painter)
                if self.current_rect:
                    painter.setPen(QPen(Qt.red, 2 / self.zoom_factor, Qt.DashLine))
                    painter.drawRect(self.current_rect)
                return True
        return super().eventFilter(obj, event)

    def start_drawing_bay(self):
        """Start drawing a new bay."""
        self.bay_drawing = True
        self.current_rect = None
        logger.info("Starting bay drawing mode")

    def undo_last_bay(self):
        """Undo the last drawn bay."""
        if self.bay_undo_stack:
            bay_name, _ = self.bay_undo_stack.pop()
            self.config["bays"].pop(bay_name, None)
            self.scene_widget.update()
            logger.info(f"Removed bay: {bay_name}")

    def clear_bays(self):
        """Clear all bays from the configuration."""
        self.config["bays"] = {}
        self.bay_undo_stack = []
        self.scene_widget.update()
        self.position_table.setRowCount(0)
        logger.info("Cleared all bays")

    def zoom_in(self):
        """Zoom in the scene."""
        self.zoom_factor *= 1.25
        self.scene_widget.update()

    def zoom_out(self):
        """Zoom out the scene."""
        self.zoom_factor /= 1.25
        self.scene_widget.update()

    def draw_bay_boundaries(self, painter=None):
        """Draw bay boundaries on the scene widget.

        Args:
            painter (QPainter, optional): The painter to use. If None, a new one is created.
        """
        if painter is None:
            painter = QPainter(self.scene_widget)
            painter.setRenderHint(QPainter.Antialiasing)

        # Draw PDF background if available, scaled to widget size initially
        if self.background_pixmap:
            painter.drawPixmap(self.scene_widget.rect(), self.background_pixmap)
        else:
            painter.fillRect(self.scene_widget.rect(), Qt.white)

        invalid_bays = []
        for bay_name, bay_pos in self.config.get("bays", {}).items():
            if not is_valid_bay(bay_pos):
                invalid_bays.append(bay_name)
                continue
            rect = QRectF(bay_pos["x"], bay_pos["y"], bay_pos["width"], bay_pos["height"])
            painter.setPen(QPen(Qt.black, 2 / self.zoom_factor))  # Adjust pen width for zoom
            painter.drawRect(rect)
            painter.drawText(rect, Qt.AlignCenter, bay_name)

        if invalid_bays:
            logger.warning(f"Skipped drawing {len(invalid_bays)} invalid bays: {', '.join(invalid_bays)}")
            QMessageBox.warning(self, "Invalid Bays", f"Skipped drawing {len(invalid_bays)} invalid bays: {', '.join(invalid_bays)}")

    def render_equipment_items(self, painter=None):
        """Render equipment items on the scene widget.

        Args:
            painter (QPainter, optional): The painter to use. If None, a new one is created.
        """
        if painter is None:
            painter = QPainter(self.scene_widget)
        positions = self.config.get("equipment_positions", {})
        units = self.config.get("units", {})
        for key, pos in positions.items():
            x = pos.get("x", 0)
            y = pos.get("y", 0)
            unit_type = pos.get("type", "Unknown")
            unit_size = units.get(unit_type, {"width": 10, "height": 10})
            width = unit_size.get("width", 10)
            height = unit_size.get("height", 10)
            
            painter.setPen(QPen(Qt.blue, 1 / self.zoom_factor))
            painter.setBrush(QColor(0, 0, 255, 100))
            painter.drawRect(int(x - width/2), int(y - height/2), width, height)
            label = f"{pos.get('type', 'Unknown')}{pos.get('id', 'Unknown')}"
            painter.drawText(int(x + width/2 + 5), int(y + height/2), label)

    def auto_position_equipment(self):
        """Automatically position equipment within bays."""
        self.position_table.setRowCount(0)
        bays = self.config.get("bays", {})
        units = self.config.get("units", {})
        if not bays or not units:
            logger.warning("Cannot position equipment: missing bays or units")
            QMessageBox.warning(self, "Configuration Error", "Define bays and equipment first.")
            return
        row = 0
        for bay_name, bay_pos in bays.items():
            if not is_valid_bay(bay_pos):
                logger.warning(f"Skipping invalid bay: {bay_name}")
                continue
            x_base = bay_pos["x"] + 10
            y_base = bay_pos["y"] + 10
            bay_width = bay_pos["width"] - 20  # Margin
            bay_height = bay_pos["height"] - 20
            for unit_type, unit_config in units.items():
                for i in range(unit_config.get("capacity", 0)):
                    self.position_table.insertRow(row)
                    self.position_table.setItem(row, 0, QTableWidgetItem(bay_name))
                    self.position_table.setItem(row, 1, QTableWidgetItem(unit_type))
                    self.position_table.setItem(row, 2, QTableWidgetItem(str(i)))
                    width = unit_config.get("width", 10)
                    height = unit_config.get("height", 10)
                    x_pos = x_base + (row % 3) * (width + 10)  # Spacing based on width
                    y_pos = y_base + (row // 3) * (height + 10)
                    
                    # Ensure fit within bay
                    x_pos = min(max(x_pos, bay_pos["x"] + 5), bay_pos["x"] + bay_width - width - 5)
                    y_pos = min(max(y_pos, bay_pos["y"] + 5), bay_pos["y"] + bay_height - height - 5)

                    self.position_table.setItem(row, 3, QTableWidgetItem(str(x_pos + width/2)))  # Center X
                    self.position_table.setItem(row, 4, QTableWidgetItem(str(y_pos + height/2)))  # Center Y
                    row += 1
        self.validatePage()
        self.scene_widget.update()
        logger.info(f"Auto-positioned {row} equipment units across {len(bays)} bays")

    def validatePage(self):
        """Validate the equipment positions with comprehensive validation.

        Returns:
            bool: True if valid, False otherwise.
        """
        # Initialize new equipment positions
        self.config["equipment_positions"] = {}
        
        # Track bays and their equipment counts for capacity checks
        bay_equipment_counts = {}
        unit_types_per_bay = {}
        
        # First pass: collect data and verify basic formats
        for row in range(self.position_table.rowCount()):
            items = [self.position_table.item(row, col) for col in range(5)]
            if not all(items):
                logger.warning(f"Missing data in row {row}")
                QMessageBox.warning(self, "Invalid Input", f"Missing data in row {row}.")
                return False
                
            bay, unit_type, unit_id, x_str, y_str = [item.text() for item in items]
            
            # Validate bay name is not empty
            if not bay:
                logger.error(f"Bay name cannot be empty in row {row}")
                QMessageBox.warning(self, "Invalid Input", "Bay name cannot be empty.")
                return False
                
            # Check bay existence
            if bay not in self.config["bays"]:
                logger.error(f"Bay '{bay}' does not exist")
                QMessageBox.warning(self, "Invalid Bay", f"Bay '{bay}' does not exist.")
                return False
            
            # Initialize tracking for this bay if needed
            if bay not in bay_equipment_counts:
                bay_equipment_counts[bay] = 0
                unit_types_per_bay[bay] = set()
            
            # Track counts
            bay_equipment_counts[bay] += 1
            unit_types_per_bay[bay].add(unit_type)
        
        # Verify that bays don't contain incompatible equipment
        incompatible_types = {
            "EAF": ["Caster"],
            "Caster": ["EAF"]
        }
        
        for bay, unit_types in unit_types_per_bay.items():
            for unit_type in unit_types:
                if unit_type in incompatible_types:
                    for incompatible in incompatible_types[unit_type]:
                        if incompatible in unit_types:
                            err_msg = f"Bay '{bay}' contains incompatible equipment types: {unit_type} and {incompatible}"
                            logger.error(err_msg)
                            QMessageBox.warning(self, "Incompatible Equipment", err_msg)
                            return False
        
        # Second pass: process and validate each equipment entry
        for row in range(self.position_table.rowCount()):
            items = [self.position_table.item(row, col) for col in range(5)]
            bay, unit_type, unit_id, x_str, y_str = [item.text() for item in items]
            
            try:
                # Validate numeric values with more specific errors
                try:
                    x = float(x_str)
                    if x < 0:
                        raise ValueError(f"X position must be positive, got {x}")
                except ValueError:
                    raise ValueError(f"X position must be a valid number, got '{x_str}'")
                
                try:
                    y = float(y_str)
                    if y < 0:
                        raise ValueError(f"Y position must be positive, got {y}")
                except ValueError:
                    raise ValueError(f"Y position must be a valid number, got '{y_str}'")
                
                try:
                    unit_id = int(unit_id)
                    if unit_id < 0:
                        raise ValueError(f"Unit ID must be positive, got {unit_id}")
                except ValueError:
                    raise ValueError(f"Unit ID must be an integer, got '{unit_id}'")
                
                # Check position is in bay with clear error message
                position = {"x": x, "y": y}
                bay_data = self.config["bays"][bay]
                if not is_position_in_bay(position, bay_data):
                    err_msg = f"Position ({x}, {y}) is outside bay '{bay}' boundaries: "
                    err_msg += f"x={bay_data['x']} to {bay_data['x'] + bay_data['width']}, "
                    err_msg += f"y={bay_data['y']} to {bay_data['y'] + bay_data['height']}"
                    logger.error(err_msg)
                    QMessageBox.warning(self, "Invalid Position", err_msg)
                    return False
                
                # Check for duplicate equipment IDs in the same bay
                key = f"{unit_type}_{unit_id}_{bay}"
                for existing_key in self.config["equipment_positions"]:
                    existing_data = self.config["equipment_positions"][existing_key]
                    if (existing_data["type"] == unit_type and 
                        existing_data["id"] == unit_id and 
                        existing_data["bay"] == bay):
                        err_msg = f"Duplicate equipment: {unit_type} with ID {unit_id} already exists in bay '{bay}'"
                        logger.error(err_msg)
                        QMessageBox.warning(self, "Duplicate Equipment", err_msg)
                        return False
                
                # Check for equipment collisions (equipment too close to each other)
                min_distance = 10  # Minimum distance between equipment
                new_pos = (x, y)
                for existing_key, existing_data in self.config["equipment_positions"].items():
                    if existing_data["bay"] == bay:  # Only check within the same bay
                        ex_pos = (existing_data["x"], existing_data["y"])
                        distance = ((new_pos[0] - ex_pos[0]) ** 2 + (new_pos[1] - ex_pos[1]) ** 2) ** 0.5
                        if distance < min_distance:
                            err_msg = f"Equipment at ({x}, {y}) is too close to existing equipment at ({ex_pos[0]}, {ex_pos[1]})"
                            logger.warning(err_msg)
                            response = QMessageBox.question(
                                self, "Equipment Collision",
                                f"{err_msg}\nMinimum distance should be {min_distance} units.\nContinue anyway?",
                                QMessageBox.Yes | QMessageBox.No, QMessageBox.No
                            )
                            if response == QMessageBox.No:
                                return False
                
                # If all checks pass, add the equipment position
                self.config["equipment_positions"][key] = {
                    "bay": bay, 
                    "type": unit_type, 
                    "id": unit_id, 
                    "x": x, 
                    "y": y
                }
                
            except ValueError as e:
                logger.error(f"Invalid data in row {row}: {e}", exc_info=True)
                QMessageBox.warning(self, "Invalid Input", f"Invalid data in row {row}: {e}")
                return False
        
        # Check bay capacity limits (optional warning)
        max_equipment_per_bay = 10  # Reasonable maximum for performance
        for bay, count in bay_equipment_counts.items():
            if count > max_equipment_per_bay:
                logger.warning(f"Bay '{bay}' has {count} equipment items, which may impact performance")
                response = QMessageBox.question(
                    self, "Bay Capacity Warning",
                    f"Bay '{bay}' has {count} equipment items, which exceeds the recommended limit of {max_equipment_per_bay}.\n"
                    "This may impact simulation performance.\nContinue anyway?",
                    QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes
                )
                if response == QMessageBox.No:
                    return False
        
        # Ensure required production equipment types exist
        required_types = {"EAF", "LMF", "Degasser", "Caster"}
        found_types = set()
        for pos in self.config["equipment_positions"].values():
            found_types.add(pos["type"])
        
        missing_types = required_types - found_types
        if missing_types:
            logger.warning(f"Missing required equipment types: {', '.join(missing_types)}")
            response = QMessageBox.question(
                self, "Missing Equipment Types",
                f"The following required equipment types are missing: {', '.join(missing_types)}.\n"
                "This may prevent the simulation from running correctly.\nContinue anyway?",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No
            )
            if response == QMessageBox.No:
                return False
        
        logger.info(f"Equipment positions validated successfully: {len(self.config['equipment_positions'])} items in {len(bay_equipment_counts)} bays")
        return True


class ProductionParametersPage(QWizardPage):
    """Page for configuring production parameters (placeholder)."""

    def __init__(self, config, parent=None):
        """Initialize the production parameters page.

        Args:
            config (dict): The configuration dictionary.
            parent (QWidget, optional): Parent widget. Defaults to None.
        """
        super().__init__(parent)
        self.config = config
        self.setTitle("Production Parameters")
        self.setSubTitle("Configure production parameters (placeholder).")
        layout = QVBoxLayout()
        layout.addWidget(QLabel("Production parameters configuration goes here."))
        self.setLayout(layout)

        self.helpText = "This page is a placeholder for production parameters configuration."


class TransportationConfigPage(QWizardPage):
    """Page for configuring transportation settings (placeholder)."""

    def __init__(self, config, parent=None):
        """Initialize the transportation configuration page.

        Args:
            config (dict): The configuration dictionary.
            parent (QWidget, optional): Parent widget. Defaults to None.
        """
        super().__init__(parent)
        self.config = config
        self.setTitle("Transportation Configuration")
        self.setSubTitle("Configure transportation settings (placeholder).")
        layout = QVBoxLayout()
        layout.addWidget(QLabel("Transportation configuration goes here."))
        self.setLayout(layout)

        self.helpText = "This page is a placeholder for transportation configuration."


class SummaryPage(QWizardPage):
    """Page for reviewing the configuration summary."""

    def __init__(self, config, sim_service=None, parent=None):
        """Initialize the summary page.

        Args:
            config (dict): The configuration dictionary.
            sim_service: SimulationService instance (optional).
            parent (QWidget, optional): Parent widget. Defaults to None.
        """
        super().__init__(parent)
        self.config = config
        self.sim_service = sim_service
        self.setTitle("Configuration Summary")
        self.setSubTitle("Review your settings before finishing.")
        layout = QVBoxLayout()

        self.summary_label = QLabel()
        self.summary_label.setTextFormat(Qt.RichText)
        self.summary_label.setWordWrap(True)
        layout.addWidget(self.summary_label)

        save_button = QPushButton("Save Configuration to File")
        save_button.clicked.connect(self.save_config_file)
        layout.addWidget(save_button)

        self.setLayout(layout)

        self.helpText = (
            "Review your simulation configuration:\n\n"
            "Check all settings and save the configuration if desired.\n"
            "Click 'Finish' to apply the settings."
        )

    def initializePage(self):
        """Initialize the page with the current configuration summary."""
        self.summary_label.setText(self.generate_summary())
        logger.info("Displaying configuration summary")

    def generate_summary(self):
        """Generate a summary of the configuration.

        Returns:
            str: The HTML-formatted summary text.
        """
        summary = "<h2>Simulation Configuration Summary</h2><br>"

        summary += "<h3>CAD Configuration</h3>"
        cad_file = self.config.get("cad_file_path", "None")
        summary += f"<b>CAD File:</b> {cad_file}<br>"
        summary += f"<b>Scale:</b> {self.config.get('cad_scale', 1.0)}<br>"
        if cad_file.lower().endswith('.pdf'):
            summary += f"<b>PDF Real Width (m):</b> {self.config.get('pdf_real_width', 100.0)}<br>"
            summary += f"<b>PDF Real Height (m):</b> {self.config.get('pdf_real_height', 100.0)}<br>"
        summary += "<br>"

        summary += "<h3>Bays</h3>"
        bays = self.config.get("bays", {})
        for bay_name, bay_pos in bays.items():
            if not is_valid_bay(bay_pos):
                summary += f"<b>{bay_name}:</b> Invalid bay data<br>"
            else:
                summary += f"<b>{bay_name}:</b> x={bay_pos['x']}, y={bay_pos['y']}, width={bay_pos['width']}, height={bay_pos['height']}<br>"
        summary += "<br>"

        summary += "<h3>Equipment Configuration</h3>"
        units = self.config.get("units", {})
        for unit_type, unit_config in units.items():
            summary += f"<b>{unit_type}:</b> Capacity: {unit_config.get('capacity', 1)}, Process Time: {unit_config.get('process_time', 30)} min"
            summary += f", Width: {unit_config.get('width', 10)}, Height: {unit_config.get('height', 10)}<br>"
        summary += "<br>"

        summary += "<h3>Equipment Positions</h3>"
        positions = self.config.get("equipment_positions", {})
        for key, pos in positions.items():
            summary += f"<b>{pos.get('type', 'Unknown')} {pos.get('id', 'Unknown')} in {pos.get('bay', 'Unknown')}:</b> x={pos.get('x', 0)}, y={pos.get('y', 0)}<br>"
        summary += "<br>"

        return summary

    def save_config_file(self):
        """Save the configuration to a user-specified file."""
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Save Configuration", "", "JSON Files (*.json);;All Files (*)"
        )
        if file_path:
            try:
                # Ensure equipment_positions and bays are included
                self.config["equipment_positions"] = self.config.get("equipment_positions", {})
                self.config["bays"] = self.config.get("bays", {})
                
                with open(file_path, 'w') as config_file:
                    json.dump(self.config, config_file, indent=2)
                logger.info(f"Configuration saved to {file_path}")
                QMessageBox.information(self, "Configuration Saved", f"Configuration saved to {file_path}")
                
                # Update SimulationService if available
                if hasattr(self, 'sim_service') and self.sim_service:
                    self.sim_service.update_config(self.config)
            except Exception as e:
                logger.error(f"Failed to save configuration: {e}", exc_info=True)
                QMessageBox.critical(self, "Error", f"Failed to save configuration: {e}")


if __name__ == '__main__':
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler("setup_wizard.log")
        ]
    )
    
    app = QApplication(sys.argv)
    wizard = SetupWizard()
    wizard.show()
    sys.exit(app.exec_())