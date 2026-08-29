import logging
import sys
from simulator.config import config
from simulator.transports import get_transport
from simulator.fault_injector import FaultInjector
from simulator.replayer import Replayer

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)

logger = logging.getLogger(__name__)

def main():
    logger.info("Starting FactoryPulse Simulator...")
    
    transport = get_transport(config)
    injector = FaultInjector(config.fault_probability) if config.inject_faults else None
    
    replayer = Replayer(
        data_dir=config.data_dir,
        transport=transport,
        rate_hz=config.replay_rate_hz,
        machine_count=config.machine_count,
        injector=injector
    )
    
    try:
        replayer.start()
    except KeyboardInterrupt:
        logger.info("Simulator stopped by user.")
        sys.exit(0)

if __name__ == "__main__":
    main()
