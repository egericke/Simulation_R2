"""
Production settings manager for steel plant simulation.

This module provides functionality to configure production parameters
including production hours, shifts, and performance metrics.
"""

import os
import json
import logging
import datetime
import calendar
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QSpinBox,
    QDoubleSpinBox, QComboBox, QGroupBox, QGridLayout, QPushButton,
    QTabWidget, QCheckBox, QDateEdit, QTimeEdit, QTableWidget,
    QTableWidgetItem, QHeaderView, QMessageBox, QFileDialog, QFrame,
    QWidget
)
from PyQt5.QtCore import Qt, QDate, QTime
from PyQt5.QtGui import QColor, QPalette, QFont

logger = logging.getLogger(__name__)

class ProductionSettingsDialog(QDialog):
    """Dialog for configuring production settings."""
    
    def __init__(self, config, parent=None):
        super().__init__(parent)
        self.config = config
        self.modified = False
        
        self.setWindowTitle("Production Settings")
        self.setMinimumSize(800, 600)
        
        # Create UI
        self.create_ui()
        
        # Load data
        self.load_production_settings()
    
    def create_ui(self):
        """Create the user interface."""
        main_layout = QVBoxLayout()
        
        # Create tabs
        tabs = QTabWidget()
        
        # Basic settings tab
        basic_tab = QWidget()
        basic_layout = QVBoxLayout(basic_tab)
        
        # Production targets
        target_group = QGroupBox("Production Targets")
        target_layout = QGridLayout()
        
        target_layout.addWidget(QLabel("Annual Production (heats):"), 0, 0)
        self.annual_heats_spin = QSpinBox()
        self.annual_heats_spin.setRange(1000, 1000000)
        self.annual_heats_spin.setSingleStep(1000)
        self.annual_heats_spin.valueChanged.connect(self.calculate_daily_production)
        target_layout.addWidget(self.annual_heats_spin, 0, 1)
        
        target_layout.addWidget(QLabel("Daily Production (heats):"), 1, 0)
        self.daily_heats_label = QLabel("0")
        target_layout.addWidget(self.daily_heats_label, 1, 1)
        
        target_layout.addWidget(QLabel("Takt Time (minutes):"), 2, 0)
        self.takt_time_spin = QSpinBox()
        self.takt_time_spin.setRange(5, 180)
        self.takt_time_spin.valueChanged.connect(self.calculate_throughput)
        target_layout.addWidget(self.takt_time_spin, 2, 1)
        
        target_layout.addWidget(QLabel("Targeted Heats per Hour:"), 3, 0)
        self.heats_per_hour_label = QLabel("0")
        target_layout.addWidget(self.heats_per_hour_label, 3, 1)
        
        target_group.setLayout(target_layout)
        basic_layout.addWidget(target_group)
        
        # Production time settings
        time_group = QGroupBox("Production Time")
        time_layout = QGridLayout()
        
        time_layout.addWidget(QLabel("Production Hours per Year:"), 0, 0)
        self.prod_hours_spin = QSpinBox()
        self.prod_hours_spin.setRange(1000, 8760)  # 8760 hours in a year
        self.prod_hours_spin.setSingleStep(100)
        self.prod_hours_spin.valueChanged.connect(self.calculate_operating_days)
        time_layout.addWidget(self.prod_hours_spin, 0, 1)
        
        time_layout.addWidget(QLabel("Days per Week:"), 1, 0)
        self.days_per_week_spin = QSpinBox()
        self.days_per_week_spin.setRange(1, 7)
        self.days_per_week_spin.valueChanged.connect(self.calculate_operating_days)
        time_layout.addWidget(self.days_per_week_spin, 1, 1)
        
        time_layout.addWidget(QLabel("Shifts per Day:"), 2, 0)
        self.shifts_per_day_spin = QSpinBox()
        self.shifts_per_day_spin.setRange(1, 3)
        self.shifts_per_day_spin.valueChanged.connect(self.calculate_operating_days)
        time_layout.addWidget(self.shifts_per_day_spin, 2, 1)
        
        time_layout.addWidget(QLabel("Hours per Shift:"), 3, 0)
        self.hours_per_shift_spin = QSpinBox()
        self.hours_per_shift_spin.setRange(4, 12)
        self.hours_per_shift_spin.valueChanged.connect(self.calculate_operating_days)
        time_layout.addWidget(self.hours_per_shift_spin, 3, 1)
        
        time_layout.addWidget(QLabel("Operating Days per Year:"), 4, 0)
        self.operating_days_label = QLabel("0")
        time_layout.addWidget(self.operating_days_label, 4, 1)
        
        time_group.setLayout(time_layout)
        basic_layout.addWidget(time_group)
        
        # Grade distribution
        grade_group = QGroupBox("Steel Grade Distribution")
        grade_layout = QGridLayout()
        
        grade_layout.addWidget(QLabel("Standard Steel (%):"), 0, 0)
        self.standard_grade_spin = QSpinBox()
        self.standard_grade_spin.setRange(0, 100)
        self.standard_grade_spin.valueChanged.connect(self.update_grade_total)
        grade_layout.addWidget(self.standard_grade_spin, 0, 1)
        
        grade_layout.addWidget(QLabel("High Clean Steel (%):"), 1, 0)
        self.high_clean_grade_spin = QSpinBox()
        self.high_clean_grade_spin.setRange(0, 100)
        self.high_clean_grade_spin.valueChanged.connect(self.update_grade_total)
        grade_layout.addWidget(self.high_clean_grade_spin, 1, 1)
        
        grade_layout.addWidget(QLabel("Decarburized Steel (%):"), 2, 0)
        self.decarb_grade_spin = QSpinBox()
        self.decarb_grade_spin.setRange(0, 100)
        self.decarb_grade_spin.valueChanged.connect(self.update_grade_total)
        grade_layout.addWidget(self.decarb_grade_spin, 2, 1)
        
        grade_layout.addWidget(QLabel("Temperature Sensitive Steel (%):"), 3, 0)
        self.temp_sensitive_grade_spin = QSpinBox()
        self.temp_sensitive_grade_spin.setRange(0, 100)
        self.temp_sensitive_grade_spin.valueChanged.connect(self.update_grade_total)
        grade_layout.addWidget(self.temp_sensitive_grade_spin, 3, 1)
        
        grade_layout.addWidget(QLabel("Total Percentage:"), 4, 0)
        self.total_percentage_label = QLabel("0%")
        grade_layout.addWidget(self.total_percentage_label, 4, 1)
        
        grade_group.setLayout(grade_layout)
        basic_layout.addWidget(grade_group)
        
        tabs.addTab(basic_tab, "Basic Settings")
        
        # Schedule tab
        schedule_tab = QWidget()
        schedule_layout = QVBoxLayout(schedule_tab)
        
        # Calendar settings
        calendar_group = QGroupBox("Production Calendar")
        calendar_layout = QGridLayout()
        
        calendar_layout.addWidget(QLabel("Production Start Date:"), 0, 0)
        self.start_date_edit = QDateEdit()
        self.start_date_edit.setDisplayFormat("yyyy-MM-dd")
        self.start_date_edit.setCalendarPopup(True)
        self.start_date_edit.setDate(QDate.currentDate())
        calendar_layout.addWidget(self.start_date_edit, 0, 1)
        
        calendar_layout.addWidget(QLabel("Production End Date:"), 1, 0)
        self.end_date_edit = QDateEdit()
        self.end_date_edit.setDisplayFormat("yyyy-MM-dd")
        self.end_date_edit.setCalendarPopup(True)
        end_date = QDate.currentDate().addYears(1)
        self.end_date_edit.setDate(end_date)
        calendar_layout.addWidget(self.end_date_edit, 1, 1)
        
        # Workdays selection
        calendar_layout.addWidget(QLabel("Production Days:"), 2, 0)
        workdays_layout = QHBoxLayout()
        self.day_checkboxes = {}
        for i, day in enumerate(["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]):
            self.day_checkboxes[day] = QCheckBox(day)
            if i < 5:  # Monday to Friday
                self.day_checkboxes[day].setChecked(True)
            workdays_layout.addWidget(self.day_checkboxes[day])
        calendar_layout.addLayout(workdays_layout, 2, 1)
        
        calendar_group.setLayout(calendar_layout)
        schedule_layout.addWidget(calendar_group)
        
        # Shift schedule
        shifts_group = QGroupBox("Shift Schedule")
        shifts_layout = QVBoxLayout()
        
        self.shifts_table = QTableWidget(3, 5)  # 3 shifts, 5 columns
        self.shifts_table.setHorizontalHeaderLabels(["Shift", "Start Time", "End Time", "Enabled", "Production %"])
        self.shifts_table.verticalHeader().setVisible(False)
        self.shifts_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        
        # Initialize shifts
        shift_names = ["Morning", "Afternoon", "Night"]
        shift_starts = ["06:00", "14:00", "22:00"]
        shift_ends = ["14:00", "22:00", "06:00"]
        shift_enabled = [True, True, True]
        shift_production = [100, 95, 90]
        
        for row in range(3):
            # Shift name
            name_item = QTableWidgetItem(shift_names[row])
            name_item.setFlags(name_item.flags() & ~Qt.ItemIsEditable)
            self.shifts_table.setItem(row, 0, name_item)
            
            # Start time
            start_time = QTimeEdit()
            start_time.setDisplayFormat("HH:mm")
            time_parts = shift_starts[row].split(":")
            start_time.setTime(QTime(int(time_parts[0]), int(time_parts[1])))
            self.shifts_table.setCellWidget(row, 1, start_time)
            
            # End time
            end_time = QTimeEdit()
            end_time.setDisplayFormat("HH:mm")
            time_parts = shift_ends[row].split(":")
            end_time.setTime(QTime(int(time_parts[0]), int(time_parts[1])))
            self.shifts_table.setCellWidget(row, 2, end_time)
            
            # Enabled
            enabled_checkbox = QCheckBox()
            enabled_checkbox.setChecked(shift_enabled[row])
            self.shifts_table.setCellWidget(row, 3, self.create_checkbox_widget(enabled_checkbox))
            
            # Production percentage
            production_spin = QSpinBox()
            production_spin.setRange(50, 100)
            production_spin.setValue(shift_production[row])
            production_spin.setSuffix("%")
            self.shifts_table.setCellWidget(row, 4, production_spin)
        
        shifts_layout.addWidget(self.shifts_table)
        shifts_group.setLayout(shifts_layout)
        schedule_layout.addWidget(shifts_group)
        
        # Maintenance scheduling
        maintenance_group = QGroupBox("Scheduled Maintenance")
        maintenance_layout = QVBoxLayout()
        
        # Add maintenance scheduling controls
        self.maintenance_table = QTableWidget(0, 4)
        self.maintenance_table.setHorizontalHeaderLabels(["Equipment", "Date", "Duration (hours)", "Description"])
        self.maintenance_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        
        maintenance_layout.addWidget(self.maintenance_table)
        
        # Add/Remove maintenance buttons
        maint_buttons_layout = QHBoxLayout()
        add_maint_button = QPushButton("Add Maintenance")
        add_maint_button.clicked.connect(self.add_maintenance)
        maint_buttons_layout.addWidget(add_maint_button)
        
        remove_maint_button = QPushButton("Remove Maintenance")
        remove_maint_button.clicked.connect(self.remove_maintenance)
        maint_buttons_layout.addWidget(remove_maint_button)
        
        maintenance_layout.addLayout(maint_buttons_layout)
        
        maintenance_group.setLayout(maintenance_layout)
        schedule_layout.addWidget(maintenance_group)
        
        tabs.addTab(schedule_tab, "Schedule")
        
        # Advanced tab
        advanced_tab = QWidget()
        advanced_layout = QVBoxLayout(advanced_tab)
        
        # Performance parameters
        performance_group = QGroupBox("Performance Parameters")
        performance_layout = QGridLayout()
        
        performance_layout.addWidget(QLabel("Heat Generation Interval (minutes):"), 0, 0)
        self.heat_interval_spin = QSpinBox()
        self.heat_interval_spin.setRange(1, 60)
        performance_layout.addWidget(self.heat_interval_spin, 0, 1)
        
        performance_layout.addWidget(QLabel("Target Utilization (%):"), 1, 0)
        self.utilization_spin = QSpinBox()
        self.utilization_spin.setRange(50, 100)
        performance_layout.addWidget(self.utilization_spin, 1, 1)
        
        performance_layout.addWidget(QLabel("Target OEE (%):"), 2, 0)
        self.oee_spin = QSpinBox()
        self.oee_spin.setRange(50, 100)
        performance_layout.addWidget(self.oee_spin, 2, 1)
        
        performance_layout.addWidget(QLabel("Simulation Speed:"), 3, 0)
        self.sim_speed_spin = QDoubleSpinBox()
        self.sim_speed_spin.setRange(0.1, 100.0)
        self.sim_speed_spin.setDecimals(1)
        self.sim_speed_spin.setSingleStep(0.1)
        performance_layout.addWidget(self.sim_speed_spin, 3, 1)
        
        performance_group.setLayout(performance_layout)
        advanced_layout.addWidget(performance_group)
        
        # Energy and utilities
        energy_group = QGroupBox("Energy and Utilities")
        energy_layout = QGridLayout()
        
        energy_layout.addWidget(QLabel("Electricity Cost ($/kWh):"), 0, 0)
        self.electricity_cost_spin = QDoubleSpinBox()
        self.electricity_cost_spin.setRange(0.01, 1.0)
        self.electricity_cost_spin.setDecimals(3)
        self.electricity_cost_spin.setSingleStep(0.001)
        energy_layout.addWidget(self.electricity_cost_spin, 0, 1)
        
        energy_layout.addWidget(QLabel("Natural Gas Cost ($/MMBTU):"), 1, 0)
        self.gas_cost_spin = QDoubleSpinBox()
        self.gas_cost_spin.setRange(1.0, 20.0)
        self.gas_cost_spin.setDecimals(2)
        self.gas_cost_spin.setSingleStep(0.1)
        energy_layout.addWidget(self.gas_cost_spin, 1, 1)
        
        energy_layout.addWidget(QLabel("EAF Power (MW):"), 2, 0)
        self.eaf_power_spin = QDoubleSpinBox()
        self.eaf_power_spin.setRange(20.0, 150.0)
        self.eaf_power_spin.setDecimals(1)
        energy_layout.addWidget(self.eaf_power_spin, 2, 1)
        
        energy_layout.addWidget(QLabel("LMF Power (MW):"), 3, 0)
        self.lmf_power_spin = QDoubleSpinBox()
        self.lmf_power_spin.setRange(5.0, 30.0)
        self.lmf_power_spin.setDecimals(1)
        energy_layout.addWidget(self.lmf_power_spin, 3, 1)
        
        energy_group.setLayout(energy_layout)
        advanced_layout.addWidget(energy_group)
        
        tabs.addTab(advanced_tab, "Advanced")
        
        main_layout.addWidget(tabs)
        
        # Bottom buttons
        button_layout = QHBoxLayout()
        
        # Save/load buttons
        save_button = QPushButton("Save Settings")
        save_button.clicked.connect(self.save_settings)
        button_layout.addWidget(save_button)
        
        load_button = QPushButton("Load Settings")
        load_button.clicked.connect(self.load_settings)
        button_layout.addWidget(load_button)
        
        button_layout.addStretch()
        
        # Dialog buttons
        cancel_button = QPushButton("Cancel")
        cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(cancel_button)
        
        apply_button = QPushButton("Apply")
        apply_button.clicked.connect(self.apply_settings)
        button_layout.addWidget(apply_button)
        
        ok_button = QPushButton("OK")
        ok_button.clicked.connect(self.accept)
        button_layout.addWidget(ok_button)
        
        main_layout.addLayout(button_layout)
        
        self.setLayout(main_layout)
    
    def create_checkbox_widget(self, checkbox):
        """Create a centered checkbox widget for a table cell."""
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.addWidget(checkbox)
        layout.setAlignment(Qt.AlignCenter)
        layout.setContentsMargins(0, 0, 0, 0)
        widget.setLayout(layout)
        return widget
    
    def load_production_settings(self):
        """Load production settings from configuration."""
        # Load basic settings
        self.annual_heats_spin.setValue(self.config.get("annual_production_heats", 100000))
        self.takt_time_spin.setValue(self.config.get("takt_time", 60))
        self.prod_hours_spin.setValue(self.config.get("production_hours_per_year", 7000))
        self.days_per_week_spin.setValue(self.config.get("days_per_week", 5))
        self.shifts_per_day_spin.setValue(self.config.get("shifts_per_day", 3))
        self.hours_per_shift_spin.setValue(self.config.get("hours_per_shift", 8))
        
        # Calculate dependent values
        self.calculate_daily_production()
        self.calculate_throughput()
        self.calculate_operating_days()
        
        # Load grade distribution
        grade_distribution = self.config.get("grade_distribution", {
            "standard": 60,
            "high_clean": 20,
            "decarb": 15,
            "temp_sensitive": 5
        })
        
        self.standard_grade_spin.setValue(grade_distribution.get("standard", 60))
        self.high_clean_grade_spin.setValue(grade_distribution.get("high_clean", 20))
        self.decarb_grade_spin.setValue(grade_distribution.get("decarb", 15))
        self.temp_sensitive_grade_spin.setValue(grade_distribution.get("temp_sensitive", 5))
        
        self.update_grade_total()
        
        # Load calendar settings
        start_date_str = self.config.get("production_start_date", None)
        if start_date_str:
            try:
                year, month, day = map(int, start_date_str.split('-'))
                self.start_date_edit.setDate(QDate(year, month, day))
            except:
                self.start_date_edit.setDate(QDate.currentDate())
        
        end_date_str = self.config.get("production_end_date", None)
        if end_date_str:
            try:
                year, month, day = map(int, end_date_str.split('-'))
                self.end_date_edit.setDate(QDate(year, month, day))
            except:
                self.end_date_edit.setDate(QDate.currentDate().addYears(1))
        
        # Load workdays
        workdays = self.config.get("workdays", ["Mon", "Tue", "Wed", "Thu", "Fri"])
        for day, checkbox in self.day_checkboxes.items():
            checkbox.setChecked(day in workdays)
        
        # Load shifts
        shifts = self.config.get("shifts", [
            {"name": "Morning", "start": "06:00", "end": "14:00", "enabled": True, "production_factor": 1.0},
            {"name": "Afternoon", "start": "14:00", "end": "22:00", "enabled": True, "production_factor": 0.95},
            {"name": "Night", "start": "22:00", "end": "06:00", "enabled": True, "production_factor": 0.9}
        ])
        
        for row, shift in enumerate(shifts[:3]):  # Only use first 3 shifts
            # Update shift data
            self.shifts_table.item(row, 0).setText(shift.get("name", f"Shift {row+1}"))
            
            # Start time
            start_time = shift.get("start", "08:00")
            hours, minutes = map(int, start_time.split(":"))
            start_widget = self.shifts_table.cellWidget(row, 1)
            if isinstance(start_widget, QTimeEdit):
                start_widget.setTime(QTime(hours, minutes))
            
            # End time
            end_time = shift.get("end", "16:00")
            hours, minutes = map(int, end_time.split(":"))
            end_widget = self.shifts_table.cellWidget(row, 2)
            if isinstance(end_widget, QTimeEdit):
                end_widget.setTime(QTime(hours, minutes))
            
            # Enabled
            enabled = shift.get("enabled", True)
            enabled_widget = self.shifts_table.cellWidget(row, 3)
            if enabled_widget:
                checkbox = enabled_widget.findChild(QCheckBox)
                if checkbox:
                    checkbox.setChecked(enabled)
            
            # Production factor
            production = int(shift.get("production_factor", 1.0) * 100)
            production_widget = self.shifts_table.cellWidget(row, 4)
            if isinstance(production_widget, QSpinBox):
                production_widget.setValue(production)
        
        # Load maintenance
        maintenance = self.config.get("scheduled_maintenance", [])
        self.maintenance_table.setRowCount(len(maintenance))
        
        for row, maint in enumerate(maintenance):
            # Equipment
            self.maintenance_table.setItem(row, 0, QTableWidgetItem(maint.get("equipment", "")))
            
            # Date
            self.maintenance_table.setItem(row, 1, QTableWidgetItem(maint.get("date", "")))
            
            # Duration
            self.maintenance_table.setItem(row, 2, QTableWidgetItem(str(maint.get("duration", 8))))
            
            # Description
            self.maintenance_table.setItem(row, 3, QTableWidgetItem(maint.get("description", "")))
        
        # Load advanced settings
        self.heat_interval_spin.setValue(self.config.get("heat_interval", 10))
        self.utilization_spin.setValue(int(self.config.get("lean_metrics", {}).get("target_utilization", 0.8) * 100))
        self.oee_spin.setValue(int(self.config.get("lean_metrics", {}).get("target_oee", 0.75) * 100))
        self.sim_speed_spin.setValue(self.config.get("sim_speed", 1.0))
        
        # Load energy settings
        energy = self.config.get("energy", {})
        self.electricity_cost_spin.setValue(energy.get("electricity_cost", 0.08))
        self.gas_cost_spin.setValue(energy.get("gas_cost", 5.0))
        self.eaf_power_spin.setValue(energy.get("eaf_power", 80.0))
        self.lmf_power_spin.setValue(energy.get("lmf_power", 15.0))
    
    def calculate_daily_production(self):
        """Calculate daily production based on annual targets."""
        annual_heats = self.annual_heats_spin.value()
        
        # Get operating days
        days_per_week = self.days_per_week_spin.value()
        operating_days = int(days_per_week * 52)  # Approximate
        
        if operating_days > 0:
            daily_heats = annual_heats / operating_days
            self.daily_heats_label.setText(f"{daily_heats:.1f}")
        else:
            self.daily_heats_label.setText("0")
    
    def calculate_throughput(self):
        """Calculate throughput based on takt time."""
        takt_time = self.takt_time_spin.value()
        
        if takt_time > 0:
            heats_per_hour = 60 / takt_time
            self.heats_per_hour_label.setText(f"{heats_per_hour:.2f}")
        else:
            self.heats_per_hour_label.setText("0")
    
    def calculate_operating_days(self):
        """Calculate operating days based on production hours."""
        prod_hours = self.prod_hours_spin.value()
        days_per_week = self.days_per_week_spin.value()
        shifts_per_day = self.shifts_per_day_spin.value()
        hours_per_shift = self.hours_per_shift_spin.value()
        
        # Calculate daily hours
        daily_hours = shifts_per_day * hours_per_shift
        
        if daily_hours > 0:
            # Calculate operating days
            operating_days = prod_hours / daily_hours
            
            # Adjust for days per week
            weeks = operating_days / days_per_week
            operating_days = weeks * days_per_week
            
            self.operating_days_label.setText(f"{operating_days:.1f}")
        else:
            self.operating_days_label.setText("0")
    
    def update_grade_total(self):
        """Update the total percentage label for grade distribution."""
        total = (
            self.standard_grade_spin.value() +
            self.high_clean_grade_spin.value() +
            self.decarb_grade_spin.value() +
            self.temp_sensitive_grade_spin.value()
        )
        
        if total == 100:
            self.total_percentage_label.setText(f"<font color='green'>{total}%</font>")
        else:
            self.total_percentage_label.setText(f"<font color='red'>{total}% (should be 100%)</font>")
    
    def add_maintenance(self):
        """Add a new maintenance entry to the table."""
        row = self.maintenance_table.rowCount()
        self.maintenance_table.insertRow(row)
        
        # Set default values
        self.maintenance_table.setItem(row, 0, QTableWidgetItem("EAF"))
        
        # Default date (next month)
        next_month = QDate.currentDate().addMonths(1)
        self.maintenance_table.setItem(row, 1, QTableWidgetItem(next_month.toString("yyyy-MM-dd")))
        
        # Default duration
        self.maintenance_table.setItem(row, 2, QTableWidgetItem("8"))
        
        # Default description
        self.maintenance_table.setItem(row, 3, QTableWidgetItem("Scheduled maintenance"))
    
    def remove_maintenance(self):
        """Remove the selected maintenance entry."""
        selected = self.maintenance_table.selectedIndexes()
        if selected:
            row = selected[0].row()
            self.maintenance_table.removeRow(row)
    
    def save_settings(self):
        """Save settings to a file."""
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Save Production Settings", "", "JSON Files (*.json);;All Files (*)"
        )
        
        if not file_path:
            return
        
        try:
            # Get current settings
            settings = self.get_settings_dict()
            
            # Save to file
            with open(file_path, 'w') as f:
                json.dump(settings, f, indent=2)
            
            QMessageBox.information(
                self, "Settings Saved", f"Production settings saved to {file_path}"
            )
        except Exception as e:
            QMessageBox.critical(
                self, "Error", f"Failed to save settings: {e}"
            )
    
    def load_settings(self):
        """Load settings from a file."""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Load Production Settings", "", "JSON Files (*.json);;All Files (*)"
        )
        
        if not file_path:
            return
        
        try:
            with open(file_path, 'r') as f:
                settings = json.load(f)
            
            # Update configuration with loaded settings
            for key, value in settings.items():
                self.config[key] = value
            
            # Reload UI with new settings
            self.load_production_settings()
            
            QMessageBox.information(
                self, "Settings Loaded", f"Production settings loaded from {file_path}"
            )
        except Exception as e:
            QMessageBox.critical(
                self, "Error", f"Failed to load settings: {e}"
            )
    
    def get_settings_dict(self):
        """Get the current settings as a dictionary."""
        # Basic settings
        settings = {
            "annual_production_heats": self.annual_heats_spin.value(),
            "takt_time": self.takt_time_spin.value(),
            "production_hours_per_year": self.prod_hours_spin.value(),
            "days_per_week": self.days_per_week_spin.value(),
            "shifts_per_day": self.shifts_per_day_spin.value(),
            "hours_per_shift": self.hours_per_shift_spin.value(),
            
            # Grade distribution
            "grade_distribution": {
                "standard": self.standard_grade_spin.value(),
                "high_clean": self.high_clean_grade_spin.value(),
                "decarb": self.decarb_grade_spin.value(),
                "temp_sensitive": self.temp_sensitive_grade_spin.value()
            },
            
            # Calendar settings
            "production_start_date": self.start_date_edit.date().toString("yyyy-MM-dd"),
            "production_end_date": self.end_date_edit.date().toString("yyyy-MM-dd"),
            
            # Workdays
            "workdays": [day for day, checkbox in self.day_checkboxes.items() if checkbox.isChecked()],
            
            # Advanced settings
            "heat_interval": self.heat_interval_spin.value(),
            "sim_speed": self.sim_speed_spin.value(),
            
            "lean_metrics": {
                "target_utilization": self.utilization_spin.value() / 100.0,
                "target_oee": self.oee_spin.value() / 100.0
            },
            
            "energy": {
                "electricity_cost": self.electricity_cost_spin.value(),
                "gas_cost": self.gas_cost_spin.value(),
                "eaf_power": self.eaf_power_spin.value(),
                "lmf_power": self.lmf_power_spin.value()
            }
        }
        
        # Shifts
        shifts = []
        for row in range(self.shifts_table.rowCount()):
            name = self.shifts_table.item(row, 0).text()
            
            start_widget = self.shifts_table.cellWidget(row, 1)
            start_time = start_widget.time().toString("HH:mm") if isinstance(start_widget, QTimeEdit) else "00:00"
            
            end_widget = self.shifts_table.cellWidget(row, 2)
            end_time = end_widget.time().toString("HH:mm") if isinstance(end_widget, QTimeEdit) else "00:00"
            
            enabled_widget = self.shifts_table.cellWidget(row, 3)
            enabled = False
            if enabled_widget:
                checkbox = enabled_widget.findChild(QCheckBox)
                if checkbox:
                    enabled = checkbox.isChecked()
            
            production_widget = self.shifts_table.cellWidget(row, 4)
            production_factor = 1.0
            if isinstance(production_widget, QSpinBox):
                production_factor = production_widget.value() / 100.0
            
            shifts.append({
                "name": name,
                "start": start_time,
                "end": end_time,
                "enabled": enabled,
                "production_factor": production_factor
            })
        
        settings["shifts"] = shifts
        
        # Maintenance
        maintenance = []
        for row in range(self.maintenance_table.rowCount()):
            equipment = self.maintenance_table.item(row, 0).text()
            date = self.maintenance_table.item(row, 1).text()
            
            try:
                duration = int(self.maintenance_table.item(row, 2).text())
            except:
                duration = 8
            
            description = self.maintenance_table.item(row, 3).text()
            
            maintenance.append({
                "equipment": equipment,
                "date": date,
                "duration": duration,
                "description": description
            })
        
        settings["scheduled_maintenance"] = maintenance
        
        return settings
    
    def apply_settings(self):
        """Apply the current settings to the configuration."""
        # Get settings dictionary
        settings = self.get_settings_dict()
        
        # Validate settings
        grade_total = sum(settings["grade_distribution"].values())
        if grade_total != 100:
            QMessageBox.warning(
                self, "Invalid Grade Distribution", 
                f"Grade distribution must add up to 100%. Current total: {grade_total}%"
            )
            return False
        
        # Update configuration
        for key, value in settings.items():
            self.config[key] = value
        
        self.modified = True
        
        return True
    
    def accept(self):
        """Handle dialog acceptance."""
        if self.apply_settings():
            super().accept()
    
    def generate_production_calendar(self):
        """Generate a production calendar based on settings."""
        # Get workdays
        workdays = [day for day, checkbox in self.day_checkboxes.items() if checkbox.isChecked()]
        day_indices = []
        for day in workdays:
            if day == "Mon":
                day_indices.append(0)
            elif day == "Tue":
                day_indices.append(1)
            elif day == "Wed":
                day_indices.append(2)
            elif day == "Thu":
                day_indices.append(3)
            elif day == "Fri":
                day_indices.append(4)
            elif day == "Sat":
                day_indices.append(5)
            elif day == "Sun":
                day_indices.append(6)
        
        # Get date range
        start_date = self.start_date_edit.date().toPyDate()
        end_date = self.end_date_edit.date().toPyDate()
        
        # Generate calendar
        calendar = []
        current_date = start_date
        
        while current_date <= end_date:
            # Check if this is a workday
            if current_date.weekday() in day_indices:
                # Get shifts for this day
                day_shifts = []
                
                for row in range(self.shifts_table.rowCount()):
                    enabled_widget = self.shifts_table.cellWidget(row, 3)
                    if enabled_widget:
                        checkbox = enabled_widget.findChild(QCheckBox)
                        if checkbox and checkbox.isChecked():
                            name = self.shifts_table.item(row, 0).text()
                            
                            start_widget = self.shifts_table.cellWidget(row, 1)
                            start_time = start_widget.time() if isinstance(start_widget, QTimeEdit) else QTime(0, 0)
                            
                            end_widget = self.shifts_table.cellWidget(row, 2)
                            end_time = end_widget.time() if isinstance(end_widget, QTimeEdit) else QTime(0, 0)
                            
                            production_widget = self.shifts_table.cellWidget(row, 4)
                            production_factor = 1.0
                            if isinstance(production_widget, QSpinBox):
                                production_factor = production_widget.value() / 100.0
                            
                            # Create shift entry
                            shift = {
                                "name": name,
                                "start": start_time.toString("HH:mm"),
                                "end": end_time.toString("HH:mm"),
                                "production_factor": production_factor
                            }
                            
                            day_shifts.append(shift)
                
                # Add this day to the calendar
                day_entry = {
                    "date": current_date.strftime("%Y-%m-%d"),
                    "weekday": calendar.day_name[current_date.weekday()],
                    "shifts": day_shifts
                }
                
                calendar.append(day_entry)
            
            # Next day
            current_date += datetime.timedelta(days=1)
        
        return calendar

def show_production_settings_dialog(config, parent=None):
    """Show the production settings dialog."""
    dialog = ProductionSettingsDialog(config, parent)
    result = dialog.exec_()
    
    if result == QDialog.Accepted and dialog.modified:
        # Generate production calendar
        calendar = dialog.generate_production_calendar()
        config["production_calendar"] = calendar
        
        return True
    return False


if __name__ == "__main__":
    # Test the dialog
    from PyQt5.QtWidgets import QApplication
    import sys
    
    app = QApplication(sys.argv)
    
    # Sample configuration
    config = {
        "annual_production_heats": 100000,
        "takt_time": 60,
        "production_hours_per_year": 7000,
        "days_per_week": 5,
        "shifts_per_day": 3,
        "hours_per_shift": 8,
        "grade_distribution": {
            "standard": 60,
            "high_clean": 20,
            "decarb": 15,
            "temp_sensitive": 5
        }
    }
    
    result = show_production_settings_dialog(config)
    print(f"Dialog result: {result}")
    if result:
        print(f"Updated config: {config}")