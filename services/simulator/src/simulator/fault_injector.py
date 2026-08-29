import random
from typing import Dict
import logging

logger = logging.getLogger(__name__)

class FaultInjector:
    def __init__(self, probability: float = 0.05):
        self.probability = probability
        
    def inject(self, reading: Dict) -> Dict:
        """Randomly degrades a signal by multiplying it by a noise factor."""
        if random.random() < self.probability:
            # Degrade signal: multiply by a factor between 1.5 and 3.0
            factor = random.uniform(1.5, 3.0)
            original = reading["value"]
            reading["value"] = original * factor
            reading["quality"] = int(max(0, reading["quality"] - (factor * 10)))
            logger.debug(f"Injected fault on {reading['machine_id']} sensor {reading['sensor']}: {original} -> {reading['value']}")
        return reading
