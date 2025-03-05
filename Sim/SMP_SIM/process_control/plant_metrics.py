import logging
import salabim as sim
from collections import deque

logger = logging.getLogger(__name__)

class PlantMetricsTracker(sim.Component):
    """
    Tracks and reports on steel plant performance metrics.
    """
    def __init__(self, env, production_manager, reporting_interval=50, metrics_window=20, **kwargs):
        """
        Initialize the metrics tracker.
        
        Args:
            env: Salabim environment
            production_manager: Reference to the ProductionManager
            reporting_interval: How often to generate reports (simulation time)
            metrics_window: Size of metrics history window
        """
        super().__init__(env=env, **kwargs)
        self.env = env
        self.production_manager = production_manager
        self.reporting_interval = reporting_interval
        self.metrics_window = metrics_window
        
        # Performance metrics
        self.metrics_history = {
            "heats_processed": deque(maxlen=metrics_window),
            "throughput": deque(maxlen=metrics_window),
            "yield": deque(maxlen=metrics_window),
            "availability": deque(maxlen=metrics_window),
            "bottlenecks": deque(maxlen=metrics_window)
        }
        
        # Unit-specific metrics
        self.unit_metrics = {}
        
    def process(self):
        """Main process loop to collect metrics at regular intervals."""
        while True:
            # Wait for reporting interval
            yield self.hold(self.reporting_interval)
            
            # Collect and record metrics
            self.collect_metrics()
            
            # Generate report
            self.generate_report()
            
    def collect_metrics(self):
        """Collect current performance metrics."""
        try:
            # Get production data
            completed_heats = self.production_manager.completed_heats
            
            # Calculate throughput (heats per day, assuming 1 sim unit = 1 minute)
            sim_minutes = self.env.now()
            throughput = (completed_heats / sim_minutes) * 60 * 24 if sim_minutes > 0 else 0
            
            # Collect metrics from all units
            units_data = self.collect_units_data()
            
            # Calculate overall plant availability
            total_availability = 0
            unit_count = 0
            
            for bay_data in units_data.values():
                for unit_type, units in bay_data.items():
                    if isinstance(units, list):
                        for unit in units:
                            total_uptime = unit.busy_time + unit.idle_time
                            availability = unit.busy_time / total_uptime if total_uptime > 0 else 0
                            total_availability += availability
                            unit_count += 1
                    else:
                        unit = units
                        total_uptime = unit.busy_time + unit.idle_time
                        availability = unit.busy_time / total_uptime if total_uptime > 0 else 0
                        total_availability += availability
                        unit_count += 1
                        
            # Overall plant availability (0-100%)
            plant_availability = (total_availability / unit_count) * 100 if unit_count > 0 else 0
            
            # Identify bottlenecks
            bottlenecks = self.identify_bottlenecks(units_data)
            
            # Calculate yield
            tons_in = sum(heat.initial_tons for heat in self.production_manager.completed_heats_list)
            tons_out = sum(heat.final_tons for heat in self.production_manager.completed_heats_list)
            steel_yield = (tons_out / tons_in) * 100 if tons_in > 0 else 97.31  # Default from requirements
            
            # Record metrics
            self.metrics_history["heats_processed"].append(completed_heats)
            self.metrics_history["throughput"].append(throughput)
            self.metrics_history["yield"].append(steel_yield)
            self.metrics_history["availability"].append(plant_availability)
            self.metrics_history["bottlenecks"].append(bottlenecks)
            
            # Record unit-specific metrics
            self.unit_metrics = units_data
            
        except Exception as e:
            logger.error(f"Error collecting metrics: {e}")
            
    def collect_units_data(self):
        """Collect data from all production units."""
        units_data = {}
        
        try:
            for bay, bay_units in self.production_manager.units.items():
                units_data[bay] = {}
                
                for unit_type, units in bay_units.items():
                    if isinstance(units, list):
                        units_data[bay][unit_type] = [self.get_unit_metrics(unit) for unit in units]
                    else:
                        units_data[bay][unit_type] = self.get_unit_metrics(units)
        except Exception as e:
            logger.error(f"Error collecting unit data: {e}")
            
        return units_data
    
    def get_unit_metrics(self, unit):
        """Get metrics for a specific unit."""
        total_time = unit.busy_time + unit.idle_time + unit.blocked_time
        
        metrics = {
            "name": unit.name,
            "heats_processed": unit.heats_processed,
            "busy_time": unit.busy_time,
            "idle_time": unit.idle_time,
            "blocked_time": unit.blocked_time,
            "queue_length": len(unit.heat_queue),
            "utilization": (unit.busy_time / total_time * 100) if total_time > 0 else 0
        }
        
        return metrics
    
    def identify_bottlenecks(self, units_data):
        """Identify bottlenecks in the production process."""
        bottlenecks = []
        high_utilization_threshold = 90  # Units with utilization above this % are potential bottlenecks
        
        for bay, bay_units in units_data.items():
            for unit_type, units in bay_units.items():
                if isinstance(units, list):
                    for unit_metrics in units:
                        if unit_metrics["utilization"] > high_utilization_threshold:
                            bottlenecks.append({
                                "name": unit_metrics["name"],
                                "utilization": unit_metrics["utilization"]
                            })
                else:
                    unit_metrics = units
                    if unit_metrics["utilization"] > high_utilization_threshold:
                        bottlenecks.append({
                            "name": unit_metrics["name"],
                            "utilization": unit_metrics["utilization"]
                        })
        
        # Sort bottlenecks by utilization (highest first)
        bottlenecks.sort(key=lambda x: x["utilization"], reverse=True)
        
        return bottlenecks[:3]  # Return top 3 bottlenecks
    
    def generate_report(self):
        """Generate a report of current performance metrics."""
        try:
            # Most recent metrics
            completed_heats = self.metrics_history["heats_processed"][-1] if self.metrics_history["heats_processed"] else 0
            throughput = self.metrics_history["throughput"][-1] if self.metrics_history["throughput"] else 0
            steel_yield = self.metrics_history["yield"][-1] if self.metrics_history["yield"] else 0
            availability = self.metrics_history["availability"][-1] if self.metrics_history["availability"] else 0
            bottlenecks = self.metrics_history["bottlenecks"][-1] if self.metrics_history["bottlenecks"] else []
            
            # Report header
            report = f"\n{'='*80}\n"
            report += f"STEEL PLANT PERFORMANCE REPORT - Simulation Time: {self.env.now():.2f} minutes\n"
            report += f"{'='*80}\n\n"
            
            # Production metrics
            report += f"PRODUCTION METRICS:\n"
            report += f"- Heats processed: {completed_heats}\n"
            report += f"- Throughput: {throughput:.2f} heats/day\n"
            report += f"- Steel yield: {steel_yield:.2f}%\n"
            report += f"- Overall availability: {availability:.2f}%\n\n"
            
            # Bottlenecks
            report += f"TOP BOTTLENECKS:\n"
            if bottlenecks:
                for i, bottleneck in enumerate(bottlenecks, 1):
                    report += f"  {i}. {bottleneck['name']} - Utilization: {bottleneck['utilization']:.2f}%\n"
            else:
                report += f"  No significant bottlenecks detected\n\n"
            
            # Unit utilization report
            report += f"UNIT UTILIZATION:\n"
            for bay, bay_units in self.unit_metrics.items():
                report += f"BAY: {bay}\n"
                for unit_type, units in bay_units.items():
                    if isinstance(units, list):
                        for unit_data in units:
                            report += f"  {unit_data['name']}: {unit_data['utilization']:.2f}%\n"
                    else:
                        unit_data = units
                        report += f"  {unit_data['name']}: {unit_data['utilization']:.2f}%\n"
            
            # Ladle metrics (if available)
            ladle_manager = self.production_manager.ladle_manager if hasattr(self.production_manager, 'ladle_manager') else None
            if ladle_manager:
                ladle_stats = ladle_manager.get_stats()
                report += f"\nLADLE USAGE METRICS:\n"
                report += f"  Total ladles: {ladle_stats['total_ladles']}\n"
                report += f"  Available: {ladle_stats['available']}\n"
                report += f"  In use: {ladle_stats['in_use']}\n"
                report += f"  Warming: {ladle_stats['warming']}\n"
                report += f"  Total heats processed: {ladle_stats['total_heats_processed']}\n"
            
            # Grade distribution metrics
            grade_counts = self.calculate_grade_distribution()
            if grade_counts:
                report += f"\nGRADE DISTRIBUTION:\n"
                for grade, count in grade_counts.items():
                    percentage = (count / completed_heats) * 100 if completed_heats > 0 else 0
                    report += f"  {grade}: {count} heats ({percentage:.1f}%)\n"
            
            # Output the report
            logger.info(report)
            
        except Exception as e:
            logger.error(f"Error generating metrics report: {e}")
    
    def calculate_grade_distribution(self):
        """Calculate the distribution of processed steel grades."""
        grade_counts = {}
        
        # Get completed heats from production manager
        if hasattr(self.production_manager, 'completed_heats_list'):
            for heat in self.production_manager.completed_heats_list:
                grade = heat.grade
                if grade not in grade_counts:
                    grade_counts[grade] = 0
                grade_counts[grade] += 1
                
        return grade_counts