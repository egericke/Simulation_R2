import salabim as sim
import logging

logger = logging.getLogger(__name__)

class EnhancedCaster(sim.Component):
    def __init__(self, env, bay, unit_id, name=None, **kwargs):
        if "min_casting_time" not in kwargs or "critical_temp" not in kwargs:
            raise ValueError("Config must include 'min_casting_time' and 'critical_temp'")
        self.min_casting_time = kwargs.pop("min_casting_time")
        self.critical_temp = kwargs.pop("critical_temp")
        if kwargs:
            raise ValueError(f"Unexpected keyword arguments for Caster: {kwargs}")
        super().__init__(env=env, name=name or f"Caster_{unit_id}")
        if not isinstance(unit_id, int) or unit_id < 1:
            raise ValueError("unit_id must be a positive integer")
        if not bay or not isinstance(bay, str):
            raise ValueError("bay must be a non-empty string")
        self.unit_id = unit_id
        self.bay = bay
        self.config = {"min_casting_time": self.min_casting_time, "critical_temp": self.critical_temp}
        self.env = env
        self.heat_queue = []
        self.current_heat = None
        self.caster_status = "idle"
        self.activate()  # Remove process="process"
        logger.info(f"Caster {self.name()} initialized in bay {self.bay}")

    def process(self):
        while True:
            if self.caster_status == "idle" and self.heat_queue:
                heat = self.heat_queue.pop(0)
                self.caster_status = "processing"
                logger.info(f"Caster {self.name()} processing heat")
                yield self.hold(self.min_casting_time)
                self.caster_status = "idle"
            else:
                yield self.hold(1)
    def process_next_heat(self):
        if self.caster_status != "idle" or not self.heat_queue:  # Use caster_status
            return
        heat = self.heat_queue[0]
        if not self.can_process_heat(heat):
            return
        self.current_heat = self.heat_queue.pop(0)
        self.caster_status = "processing"  # Update custom attribute
        self.current_heat.status = "processing"
        self.current_heat.record_process(self.name(), "Caster", self.env.now())
        logger.info(f"Caster {self.name()} started processing Heat {self.current_heat.id}")
        processing_time = self.calculate_casting_time(self.current_heat)
        self.current_heat.update_temperature(self.env.now())
        logger.debug(f"Caster {self.name()} casting Heat {self.current_heat.id} for {processing_time} minutes")
        yield self.hold(processing_time)
        self.finish_casting()

    def finish_casting(self):
        if not self.current_heat:
            return
        self.current_heat.completion_time = self.env.now()
        self.current_heat.status = "completed"
        logger.info(f"Caster {self.name()} finished casting Heat {self.current_heat.id} at {self.current_heat.completion_time}")
        self.current_heat = None
        self.caster_status = "idle"  # Update custom attribute
        self.process_next_heat()

    def update(self, current_time):
        for heat in self.heat_queue:
            heat.update_temperature(current_time)
        if self.status == "idle":
            yield from self.process_next_heat()
    
    def is_available(self):
        return self.ispassive() or (self.state.value() == "idle" and len(self.heat_queue) < self.capacity * 2)

    @property
    def queue_length(self):
        return len(self.heat_queue)