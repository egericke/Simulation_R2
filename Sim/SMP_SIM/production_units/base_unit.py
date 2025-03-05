import logging
import salabim as sim
import time
from collections import deque

logger = logging.getLogger(__name__)

class BaseProductionUnit(sim.Component):
    """
    Enhanced base class for all production units in the steelmaking process.
    Includes advanced metrics tracking for bottleneck analysis.
    """
    def __init__(self, name, process_time, capacity, env, x=0, y=0, bay="bay1", color="gray", **kwargs):
        """
        Initialize a production unit.
        
        Args:
            name: Unique identifier for the unit
            process_time: Time (in simulation units) required to process a heat
            capacity: Number of heats that can be processed simultaneously
            env: Salabim environment
            x: X-coordinate for visualization
            y: Y-coordinate for visualization
            bay: Bay identifier (e.g., "bay1")
            color: Color for visualization
        """
        super().__init__(name=name, env=env, **kwargs)
        self.resource = sim.Resource(name=f"{name}_resource", capacity=capacity, env=env)
        self.process_time = process_time
        self.heat_queue = sim.Queue(f"{name}_queue", env=env)
        self.x = x
        self.y = y
        self.bay = bay
        self.color = color
        
        # Enhanced metrics tracking
        self.heats_processed = 0
        self.total_processing_time = 0
        self.total_waiting_time = 0
        self.current_heat = None
        self.last_state_change = env.now()
        self.waiting_time = 0
        self.blocked_time = 0
        self.idle_time = 0
        self.busy_time = 0
        self.cycle_time = 0
        
        # For trend analysis
        self.metrics_window_size = 20  # Keep last 20 data points
        self.utilization_history = deque(maxlen=self.metrics_window_size)
        self.queue_length_history = deque(maxlen=self.metrics_window_size)
        self.cycle_time_history = deque(maxlen=self.metrics_window_size)
        
        # Last processing start/end times for cycle time calculation
        self.last_process_start = None
        self.state = "idle"  # idle, processing, blocked, waiting
        
        # Visual representation
        self.shape = sim.Animate(
            rectangle0=(-20, -20, 20, 20),
            x0=lambda t: self.x,
            y0=lambda t: self.y,
            fillcolor0=self.color,
            linecolor0="black",
            linewidth0=2,
            env=env
        )
        
        self.label = sim.Animate(
            text=name,
            x0=lambda t: self.x,
            y0=lambda t: self.y - 25,
            text_anchor="center",
            textcolor0="black",
            fontsize0=10,
            env=env
        )
        
        # Status indicator - color changes based on state
        self.status_indicator = sim.Animate(
            circle0=10,
            x0=lambda t: self.x + 15,
            y0=lambda t: self.y - 15,
            fillcolor0=lambda t: self._get_indicator_color(),
            linecolor0="black",
            env=env
        )
        
        # Queue indicator - shows queue length
        self.queue_indicator = sim.Animate(
            text=lambda t: str(len(self.heat_queue)) if self.heat_queue else "0",
            x0=lambda t: self.x - 15,
            y0=lambda t: self.y + 20,
            text_anchor="center",
            textcolor0="white",
            fillcolor0="blue",
            alpha0=0.7,
            fontsize0=8,
            env=env
        )

    def _get_indicator_color(self):
        """Get the color for the status indicator based on current state."""
        if self.state == "idle":
            return "gray"
        elif self.state == "processing":
            return "green"
        elif self.state == "blocked":
            return "red"
        elif self.state == "waiting":
            return "orange"
        return "black"

    def _update_metrics(self, new_state):
        """Update metrics based on state change."""
        current_time = self.env.now()
        time_in_state = current_time - self.last_state_change
        
        # Update time in previous state
        if self.state == "idle":
            self.idle_time += time_in_state
        elif self.state == "processing":
            self.busy_time += time_in_state
        elif self.state == "waiting":
            self.waiting_time += time_in_state
        elif self.state == "blocked":
            self.blocked_time += time_in_state
        
        # Calculate utilization and add to history
        total_time = self.idle_time + self.busy_time + self.waiting_time + self.blocked_time
        if total_time > 0:
            utilization = self.busy_time / total_time
            self.utilization_history.append(utilization)
        
        # Store queue length
        self.queue_length_history.append(len(self.heat_queue))
        
        # Update state and timestamp
        self.state = new_state
        self.last_state_change = current_time
        
        # Log state change
        logger.debug(f"{self.name} state changed to {new_state} at time {current_time:.2f}")

    def process(self):
        """Main process loop for the production unit."""
        while True:
            if not self.heat_queue:
                self._update_metrics("idle")
                yield self.passivate()
            
            # Get the next heat
            heat = self.heat_queue.pop()
            self.current_heat = heat
            
            # Record processing start time
            self.last_process_start = self.env.now()
            
            # Update state to processing
            self._update_metrics("processing")
            
            logger.info(f"{self.env.now():.2f} {self.name}: Processing heat {heat.id}")
            
            # Visual indication of processing (pulsing animation)
            start_size = 20
            pulse = sim.Animate(
                circle0=lambda t, size=start_size: size + 5 * sim.sin(t * 10),
                x0=lambda t: self.x,
                y0=lambda t: self.y,
                fillcolor0="yellow",
                alpha0=0.5,
                linewidth0=0,
                env=self.env
            )
            
            # Process the heat
            process_start = self.env.now()
            yield self.hold(self.process_time)
            process_end = self.env.now()
            
            # Remove pulse animation
            pulse.remove()
            
            # Update heat completion metrics
            self.heats_processed += 1
            self.total_processing_time += (process_end - process_start)
            
            # Calculate and store cycle time
            if hasattr(heat, 'start_time'):
                heat_cycle_time = process_end - heat.start_time
                self.cycle_time = heat_cycle_time
                self.cycle_time_history.append(heat_cycle_time)
            
            logger.info(f"{self.env.now():.2f} {self.name}: Finished processing heat {heat.id}")
            
            # Clear current heat
            self.current_heat = None

    def set_status(self, new_status):
        if not isinstance(new_status, str):
            logger.error(f"Attempting to set {self.name()}.car_status to non-string: {type(new_status)}")
            return
        valid_statuses = ["idle", "moving", "loading", "unloading"]

    def add_heat(self, heat):
        """Add a heat to the processing queue."""
        arrival_time = self.env.now()
        
        # Track waiting time if we already have heats in queue
        if self.heat_queue:
            self._update_metrics("waiting")
        
        # Add to queue
        self.heat_queue.add(heat)
        
        # Activate if idle
        if self.ispassive():
            self.activate()
    
    def get_current_metrics(self):
        """Get current metrics for this unit."""
        # Calculate current utilization
        total_time = self.idle_time + self.busy_time + self.waiting_time + self.blocked_time
        current_utilization = self.busy_time / total_time if total_time > 0 else 0
        
        # Calculate average cycle time
        avg_cycle_time = sum(self.cycle_time_history) / len(self.cycle_time_history) if self.cycle_time_history else 0
        
        return {
            "name": self.name,
            "utilization": current_utilization,
            "queue_length": len(self.heat_queue),
            "heats_processed": self.heats_processed,
            "avg_cycle_time": avg_cycle_time,
            "waiting_time": self.waiting_time,
            "blocked_time": self.blocked_time,
            "state": self.state,
            "current_heat": self.current_heat.id if self.current_heat else None
        }

    def is_available(self):
        """Check if the unit is available to process a new heat."""
        return self.state == "idle" and self.resource.available_quantity() > 0

    def get_name(self):
        """Return the name of this unit. Used by analytics dashboard."""
        return self.name if hasattr(self, 'name') else f"{self.__class__.__name__}_{getattr(self, 'unit_id', 'unknown')}"