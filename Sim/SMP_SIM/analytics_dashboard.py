import sys
import logging
from PyQt5.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, QTabWidget, QWidget, QGroupBox, 
    QTableWidget, QTableWidgetItem, QPushButton, QComboBox, QTextEdit
)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QColor, QBrush

from bottleneck_analyzer import BottleneckAnalyzer

logger = logging.getLogger(__name__)

class AnalyticsDashboard(QWidget):
    """
    Analytics dashboard extension that provides bottleneck analysis
    and production metrics visualization.
    """
    def __init__(self, sim_service, parent=None):
        super().__init__(parent)
        self.sim_service = sim_service
        self.config = sim_service.config
        self.analyzer = BottleneckAnalyzer(self.sim_service.production_manager, self.config)
        self.initUI()
        update_interval = self.config.get("analytics", {}).get("update_interval", 5000)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_analytics)
        self.timer.start(update_interval)

    def initUI(self):
        """Initialize the user interface."""
        main_layout = QVBoxLayout(self)
        tabs = QTabWidget()
        
        self.overview_tab = QWidget()
        self.bottleneck_tab = QWidget()
        self.unit_details_tab = QWidget()
        self.recommendations_tab = QWidget()
        
        self.setup_overview_tab()
        self.setup_bottleneck_tab()
        self.setup_unit_details_tab()
        self.setup_recommendations_tab()
        
        tabs.addTab(self.overview_tab, "System Overview")
        tabs.addTab(self.bottleneck_tab, "Bottleneck Analysis")
        tabs.addTab(self.unit_details_tab, "Unit Details")
        tabs.addTab(self.recommendations_tab, "Recommendations")
        
        main_layout.addWidget(tabs)
        
        refresh_button = QPushButton("Refresh Analytics")
        refresh_button.clicked.connect(self.update_analytics)
        main_layout.addWidget(refresh_button)

    def setup_overview_tab(self):
        """Set up the system overview tab."""
        layout = QVBoxLayout(self.overview_tab)
        metrics_group = QGroupBox("System Metrics")
        metrics_layout = QHBoxLayout()
        
        prod_layout = QVBoxLayout()
        self.heats_label = QLabel("Heats Processed: 0")
        self.completion_label = QLabel("Completion Rate: 0%")
        self.cycle_time_label = QLabel("Avg Cycle Time: 0")
        self.throughput_label = QLabel("Throughput: 0 heats/hour")
        prod_layout.addWidget(self.heats_label)
        prod_layout.addWidget(self.completion_label)
        prod_layout.addWidget(self.cycle_time_label)
        prod_layout.addWidget(self.throughput_label)
        metrics_layout.addLayout(prod_layout)
        
        eff_layout = QVBoxLayout()
        self.takt_label = QLabel("Takt Achievement: 0%")
        self.efficiency_label = QLabel("System Efficiency: 0%")
        self.distance_label = QLabel("Total Distance: 0")
        self.bottleneck_label = QLabel("Primary Bottleneck: None")
        eff_layout.addWidget(self.takt_label)
        eff_layout.addWidget(self.efficiency_label)
        eff_layout.addWidget(self.distance_label)
        eff_layout.addWidget(self.bottleneck_label)
        metrics_layout.addLayout(eff_layout)
        
        metrics_group.setLayout(metrics_layout)
        layout.addWidget(metrics_group)
        
        util_group = QGroupBox("Unit Utilization")
        util_layout = QVBoxLayout()
        self.util_table = QTableWidget(0, 3)
        self.util_table.setHorizontalHeaderLabels(["Unit", "Utilization", "Status"])
        self.util_table.horizontalHeader().setStretchLastSection(True)
        util_layout.addWidget(self.util_table)
        util_group.setLayout(util_layout)
        layout.addWidget(util_group)
        
        throughput_group = QGroupBox("Throughput Analysis")
        throughput_layout = QVBoxLayout()
        self.throughput_text = QLabel("Insufficient data for throughput analysis.")
        self.throughput_text.setWordWrap(True)
        throughput_layout.addWidget(self.throughput_text)
        throughput_group.setLayout(throughput_layout)
        layout.addWidget(throughput_group)

    def setup_bottleneck_tab(self):
        """Set up the bottleneck analysis tab."""
        layout = QVBoxLayout(self.bottleneck_tab)
        bottleneck_group = QGroupBox("Identified Bottlenecks")
        bottleneck_layout = QVBoxLayout()
        self.bottleneck_table = QTableWidget(0, 5)
        self.bottleneck_table.setHorizontalHeaderLabels(["Unit", "Severity", "Utilization", "Queue Length", "Causes"])
        self.bottleneck_table.horizontalHeader().setStretchLastSection(True)
        bottleneck_layout.addWidget(self.bottleneck_table)
        bottleneck_group.setLayout(bottleneck_layout)
        layout.addWidget(bottleneck_group)
        
        details_group = QGroupBox("Bottleneck Details")
        details_layout = QVBoxLayout()
        self.bottleneck_details = QTextEdit()
        self.bottleneck_details.setReadOnly(True)
        details_layout.addWidget(self.bottleneck_details)
        details_group.setLayout(details_layout)
        layout.addWidget(details_group)

    def setup_unit_details_tab(self):
        """Set up the unit details tab."""
        layout = QVBoxLayout(self.unit_details_tab)
        selector_layout = QHBoxLayout()
        selector_layout.addWidget(QLabel("Select Unit:"))
        self.unit_selector = QComboBox()
        self.unit_selector.currentIndexChanged.connect(self.update_unit_details)
        selector_layout.addWidget(self.unit_selector)
        layout.addLayout(selector_layout)
        
        metrics_group = QGroupBox("Unit Metrics")
        metrics_layout = QVBoxLayout()
        self.unit_metrics_table = QTableWidget(0, 3)
        self.unit_metrics_table.setHorizontalHeaderLabels(["Metric", "Current Value", "Average Value"])
        self.unit_metrics_table.horizontalHeader().setStretchLastSection(True)
        metrics_layout.addWidget(self.unit_metrics_table)
        metrics_group.setLayout(metrics_layout)
        layout.addWidget(metrics_group)
        
        details_group = QGroupBox("Unit Information")
        details_layout = QVBoxLayout()
        self.unit_info = QTextEdit()
        self.unit_info.setReadOnly(True)
        details_layout.addWidget(self.unit_info)
        details_group.setLayout(details_layout)
        layout.addWidget(details_group)
        self.populate_unit_selector()

    def setup_recommendations_tab(self):
        """Set up the recommendations tab."""
        layout = QVBoxLayout(self.recommendations_tab)
        recommendations_group = QGroupBox("Improvement Recommendations")
        recommendations_layout = QVBoxLayout()
        self.recommendations_table = QTableWidget(0, 3)
        self.recommendations_table.setHorizontalHeaderLabels(["Type", "Severity", "Recommendation"])
        self.recommendations_table.horizontalHeader().setStretchLastSection(True)
        recommendations_layout.addWidget(self.recommendations_table)
        recommendations_group.setLayout(recommendations_layout)
        layout.addWidget(recommendations_group)
        
        details_group = QGroupBox("Detailed Actions")
        details_layout = QVBoxLayout()
        self.recommendation_details = QTextEdit()
        self.recommendation_details.setReadOnly(True)
        details_layout.addWidget(self.recommendation_details)
        details_group.setLayout(details_layout)
        layout.addWidget(details_group)

    def populate_unit_selector(self):
        """Populate the unit selector with available units."""
        self.unit_selector.clear()
        pm = self.sim_service.production_manager
        if not pm or not hasattr(pm, "units"):
            return
        for bay_name, bay_units in pm.units.items():
            for unit_type, units in bay_units.items():
                if isinstance(units, list):
                    for unit in units:
                        unit_name = self._get_unit_name(unit)
                        if unit_name:
                            self.unit_selector.addItem(unit_name)
                else:
                    unit_name = self._get_unit_name(units)
                    if unit_name:
                        self.unit_selector.addItem(unit_name)
        if hasattr(pm, "ladle_cars"):
            for ladle_car in pm.ladle_cars:
                unit_name = self._get_unit_name(ladle_car)
                if unit_name:
                    self.unit_selector.addItem(unit_name)

    def _get_unit_name(self, unit):
        """Safely get the name of a unit."""
        if unit is None:
            return None
        if hasattr(unit, 'name') and callable(getattr(unit, 'name')):
            return unit.name()
        if hasattr(unit, 'name') and not callable(getattr(unit, 'name')):
            return unit.name
        if hasattr(unit, 'id'):
            return f"{unit.__class__.__name__}_{unit.id}"
        if hasattr(unit, 'unit_id'):
            return f"{unit.__class__.__name__}_{unit.unit_id}"
        return str(unit)

    def update_analytics(self):
        try:
            self.analyzer.collect_current_metrics()
            report = self.analyzer.generate_analytics_report()
            self.update_overview(report)
            self.update_bottleneck_analysis(report)
            self.update_unit_details()
            self.update_recommendations(report)
            
            # Add safety check for TappingCar move_queue attribute
            pm = self.sim_service.production_manager
            if hasattr(pm, 'ladle_cars'):
                for car in pm.ladle_cars:
                    if not hasattr(car, 'move_queue'):
                        logger.warning(f"LadleCar {self._get_unit_name(car)} missing 'move_queue' attribute")
                        # Optionally initialize move_queue if appropriate
                        # car.move_queue = []  # Uncomment if initialization is desired
            
            self.update_overview(report)
            self.update_bottleneck_analysis(report)
            self.update_unit_details()
            self.update_recommendations(report)
            logger.debug("Analytics dashboard updated successfully")
        except Exception as e:
            logger.error(f"Failed to update analytics: {e}", exc_info=True)
            raise 

    def update_overview(self, report):
        """Update the system overview tab."""
        metrics = report.get("system_metrics", {})
        heats_processed = metrics.get('heats_processed', 0)
        if heats_processed == 0:
            pm = self.sim_service.production_manager
            if hasattr(pm, 'heats_processed'):
                heats_processed = pm.heats_processed
            elif hasattr(pm, 'completed_heats'):
                heats_processed = len(pm.completed_heats)
            elif hasattr(pm, 'heat_counter'):
                heats_processed = pm.heat_counter
        self.heats_label.setText(f"Heats Processed: {heats_processed}")
        completion_rate = metrics.get('completion_rate', 0) * 100
        self.completion_label.setText(f"Completion Rate: {completion_rate:.1f}%")
        self.cycle_time_label.setText(f"Avg Cycle Time: {metrics.get('avg_cycle_time', 0):.2f}")
        
        hourly_factor = 60.0
        total_simulation_time = metrics.get('total_simulation_time', 0)
        heats_completed = metrics.get('heats_completed', 0)
        throughput = (heats_completed / total_simulation_time) * hourly_factor if total_simulation_time > 0 else 0
        self.throughput_label.setText(f"Throughput: {throughput:.2f} heats/hour" if throughput else "Throughput: N/A")
        
        throughput_analysis = report.get("throughput_analysis", {})
        if throughput_analysis.get("status") == "ok":
            takt_achievement = throughput_analysis.get("takt_achievement", 0) * 100
            self.takt_label.setText(f"Takt Achievement: {takt_achievement:.1f}%")
            efficiency = throughput_analysis.get("system_efficiency", 0) * 100
            self.efficiency_label.setText(f"System Efficiency: {efficiency:.1f}%")
            bottleneck = throughput_analysis.get("primary_bottleneck", "None")
            self.bottleneck_label.setText(f"Primary Bottleneck: {bottleneck}")
        else:
            self.takt_label.setText("Takt Achievement: N/A")
            self.efficiency_label.setText("System Efficiency: N/A")
            self.bottleneck_label.setText("Primary Bottleneck: N/A")
        self.distance_label.setText(f"Total Distance: {metrics.get('total_distance', 0):.1f}")
        
        self.util_table.setRowCount(0)
        for bay_name, bay_units in self.sim_service.production_manager.units.items():
            for unit_type, units in bay_units.items():
                for unit in (units if isinstance(units, list) else [units]):
                    unit_name = self._get_unit_name(unit)
                    self._add_utilization_row(unit_name, report)
        if hasattr(self.sim_service.production_manager, "ladle_cars"):
            for car in self.sim_service.production_manager.ladle_cars:
                unit_name = self._get_unit_name(car)
                self._add_utilization_row(unit_name, report)
        
        if throughput_analysis.get("status") == "ok":
            self.throughput_text.setText(
                f"Current throughput: {throughput_analysis.get('throughput', 0):.3f} heats/min\n"
                f"Theoretical maximum: {throughput_analysis.get('theoretical_max_throughput', 0):.3f} heats/min\n"
                f"System efficiency: {throughput_analysis.get('system_efficiency', 0)*100:.1f}%\n"
                f"Primary bottleneck: {throughput_analysis.get('primary_bottleneck', 'None')}"
            )
        else:
            self.throughput_text.setText("Throughput analysis unavailable")

    def _add_utilization_row(self, unit_name, report):
        """Add a row to the utilization table."""
        utilization = 0
        for unit_metrics in report["unit_metrics"].values():
            if unit_metrics["status"] == "ok" and unit_metrics["unit_info"]["name"] == unit_name:
                utilization = unit_metrics["metrics"].get("utilization", {}).get("average", 0)
                break
        row = self.util_table.rowCount()
        self.util_table.insertRow(row)
        self.util_table.setItem(row, 0, QTableWidgetItem(unit_name))
        util_item = QTableWidgetItem(f"{utilization*100:.1f}%")
        self.util_table.setItem(row, 1, util_item)
        
        status = "Normal"
        color = QColor(0, 200, 0)
        if utilization > 0.85:
            status = "Overutilized"
            color = QColor(200, 0, 0)
        elif utilization > 0.7:
            status = "High Utilization"
            color = QColor(200, 200, 0)
        elif utilization < 0.3:
            status = "Underutilized"
            color = QColor(0, 0, 200)
        status_item = QTableWidgetItem(status)
        status_item.setForeground(QBrush(color))
        self.util_table.setItem(row, 2, status_item)

    def update_bottleneck_analysis(self, report):
        """Update the bottleneck analysis tab."""
        bottlenecks = report.get("bottlenecks", [])
        self.bottleneck_table.setRowCount(0)
        if not bottlenecks:
            self.bottleneck_details.setText("No bottlenecks detected.")
            return
        for i, bottleneck in enumerate(bottlenecks):
            row = self.bottleneck_table.rowCount()
            self.bottleneck_table.insertRow(row)
            self.bottleneck_table.setItem(row, 0, QTableWidgetItem(bottleneck.get("unit", "Unknown")))
            severity = bottleneck.get("severity", "Unknown")
            severity_item = QTableWidgetItem(severity)
            if severity == "High":
                severity_item.setForeground(QBrush(QColor(200, 0, 0)))
            elif severity == "Medium":
                severity_item.setForeground(QBrush(QColor(200, 200, 0)))
            self.bottleneck_table.setItem(row, 1, severity_item)
            metrics = bottleneck.get("metrics", {})
            util = metrics.get("utilization", 0) * 100
            self.bottleneck_table.setItem(row, 2, QTableWidgetItem(f"{util:.1f}%"))
            queue = metrics.get("queue_length", 0)
            self.bottleneck_table.setItem(row, 3, QTableWidgetItem(f"{queue:.1f}"))
            causes = ", ".join(bottleneck.get("causes", []))
            self.bottleneck_table.setItem(row, 4, QTableWidgetItem(causes))
        primary = bottlenecks[0]
        details = (
            f"## Primary Bottleneck: {primary.get('unit', 'Unknown')} ##\n\n"
            f"Severity: {primary.get('severity', 'Unknown')}\n"
            f"Bottleneck Score: {primary.get('score', 0)}\n\n"
            f"Causes:\n" + "\n".join(f"- {cause}" for cause in primary.get("causes", [])) + "\n\n"
            f"Metrics:\n"
            f"- Utilization: {primary.get('metrics', {}).get('utilization', 0) * 100:.1f}%\n"
            f"- Queue Length: {primary.get('metrics', {}).get('queue_length', 0):.1f}\n"
        )
        if "wait_time" in primary.get("metrics", {}):
            details += f"- Wait Time: {primary['metrics']['wait_time']:.1f} minutes\n"
        self.bottleneck_details.setText(details)

    def update_unit_details(self):
        """Update the unit details tab based on selected unit."""
        unit_name = self.unit_selector.currentText()
        if not unit_name:
            return
        try:
            unit_analytics = self.analyzer.get_unit_analytics(unit_name)
            if unit_analytics.get("status") != "ok":
                self.unit_info.setText(f"Error: Unable to get analytics for {unit_name}")
                return
            unit_info = unit_analytics.get("unit_info", {})
            info_text = (
                f"Unit: {unit_info.get('name', 'Unknown')}\n"
                f"Type: {unit_info.get('type', 'Unknown')}\n"
                f"Process Time: {unit_info.get('process_time', 'Unknown')} minutes\n"
                f"Capacity: {unit_info.get('capacity', 'Unknown')}\n"
                f"Current Queue Length: {unit_info.get('current_queue_length', 'Unknown')}\n"
            )
            self.unit_info.setText(info_text)
            self.unit_metrics_table.setRowCount(0)
            metrics = unit_analytics.get("metrics", {})
            for metric_name, metric_values in metrics.items():
                row = self.unit_metrics_table.rowCount()
                self.unit_metrics_table.insertRow(row)
                display_name = metric_name.replace("_", " ").title()
                self.unit_metrics_table.setItem(row, 0, QTableWidgetItem(display_name))
                current = metric_values.get("current", 0)
                average = metric_values.get("average", 0)
                if metric_name == "utilization":
                    self.unit_metrics_table.setItem(row, 1, QTableWidgetItem(f"{current*100:.1f}%"))
                    self.unit_metrics_table.setItem(row, 2, QTableWidgetItem(f"{average*100:.1f}%"))
                else:
                    self.unit_metrics_table.setItem(row, 1, QTableWidgetItem(f"{current:.2f}"))
                    self.unit_metrics_table.setItem(row, 2, QTableWidgetItem(f"{average:.2f}"))
        except Exception as e:
            logger.error(f"Error updating unit details: {e}")
            self.unit_info.setText(f"Error processing unit details: {str(e)}")

    def update_recommendations(self, report):
        """Update the recommendations tab."""
        recommendations = report.get("recommendations", [])
        self.recommendations_table.setRowCount(0)
        if not recommendations:
            self.recommendation_details.setText("No recommendations available.")
            return
        for recommendation in recommendations:
            row = self.recommendations_table.rowCount()
            self.recommendations_table.insertRow(row)
            rec_type = recommendation.get("type", "Unknown").capitalize()
            self.recommendations_table.setItem(row, 0, QTableWidgetItem(rec_type))
            severity = recommendation.get("severity", "Low")
            severity_item = QTableWidgetItem(severity)
            if severity == "High":
                severity_item.setForeground(QBrush(QColor(200, 0, 0)))
            elif severity == "Medium":
                severity_item.setForeground(QBrush(QColor(200, 100, 0)))
            else:
                severity_item.setForeground(QBrush(QColor(0, 150, 0)))
            self.recommendations_table.setItem(row, 1, severity_item)
            message = recommendation.get("message", "No details available")
            self.recommendations_table.setItem(row, 2, QTableWidgetItem(message))
        details = "# Recommended Actions #\n\n"
        for recommendation in recommendations:
            rec_type = recommendation.get("type", "Unknown").capitalize()
            severity = recommendation.get("severity", "Low")
            message = recommendation.get("message", "No details available")
            details += f"## {rec_type} ({severity}) ##\n{message}\n\n"
            if "actions" in recommendation:
                details += "Specific actions:\n" + "\n".join(f"- {action}" for action in recommendation["actions"]) + "\n\n"
        self.recommendation_details.setText(details)