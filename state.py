from transitions import Machine
import random
import time
from threading import Lock, Thread
import logging

class TalkingProcess:
    states = ['idle', 'intending_to_talk', 'talking', 'yield']
    
    def __init__(self, process_id, p_k=0.3, min_talk_duration=1, max_talk_duration=5):
        """
        Initialize a talking process with given parameters.
        
        Args:
            process_id (str): Unique identifier for the process
            p_k (float): Probability of initiating talk when idle
            min_talk_duration (float): Minimum talking duration in seconds
            max_talk_duration (float): Maximum talking duration in seconds
        """
        self.process_id = process_id
        self.p_k = p_k
        self.min_talk_duration = min_talk_duration
        self.max_talk_duration = max_talk_duration
        self.other_is_talking = False
        self.stop_event = False
        self.talk_start_time = None
        self.talk_duration = None
        self.lock = Lock()
        
        # Initialize the state machine
        self.machine = Machine(
            model=self,
            states=TalkingProcess.states,
            initial='idle',
            auto_transitions=False
        )
        
        # Add transitions
        self.machine.add_transition(
            trigger='try_talk',
            source='idle',
            dest='intending_to_talk',
            conditions=['should_start_talking']
        )
        
        self.machine.add_transition(
            trigger='begin_talking',
            source='intending_to_talk',
            dest='talking',
            conditions=['can_talk'],
            after='set_talking_duration'
        )
        
        self.machine.add_transition(
            trigger='yield_talking',
            source='intending_to_talk',
            dest='yield',
            conditions=['should_yield']
        )
        
        self.machine.add_transition(
            trigger='stop_talking',
            source='talking',
            dest='idle',
            conditions=['should_stop_talking']
        )
        
        self.machine.add_transition(
            trigger='return_to_idle',
            source='yield',
            dest='idle'
        )
    
    def should_start_talking(self):
        """Determine if the process should initiate talking based on probability."""
        return random.random() < self.p_k
    
    def can_talk(self):
        """Check if the process can start talking."""
        with self.lock:
            if not self.other_is_talking:
                return True
            # If there's a collision, decide based on process ID
            return self.should_interrupt()
    
    def should_yield(self):
        """Determine if the process should yield when attempting to talk."""
        return self.other_is_talking and not self.should_interrupt()
    
    def should_interrupt(self):
        """
        Determine if this process should interrupt another talking process.
        Currently based on process ID comparison, could be modified for other strategies.
        """
        return self.process_id > str(self.other_is_talking)
    
    def should_stop_talking(self):
        """Check if the process should stop talking."""
        if self.stop_event:
            return True
        if self.talk_start_time is None:
            return False
        return time.time() - self.talk_start_time >= self.talk_duration
    
    def set_talking_duration(self):
        """Set a random duration for talking within the specified range."""
        self.talk_duration = random.uniform(self.min_talk_duration, self.max_talk_duration)
        self.talk_start_time = time.time()
    
    def run(self):
        """Main loop for the talking process."""
        while not self.stop_event:
            if self.state == 'idle':
                self.try_talk()
            elif self.state == 'intending_to_talk':
                if self.can_talk():
                    self.begin_talking()
                else:
                    self.yield_talking()
            elif self.state == 'talking':
                if self.should_stop_talking():
                    self.stop_talking()
            elif self.state == 'yield':
                self.return_to_idle()
            
            time.sleep(0.1)  # Small delay to prevent busy waiting

    def start(self):
        """Start the talking process in a separate thread."""
        self.thread = Thread(target=self.run)
        self.thread.start()
    
    def stop(self):
        """Stop the talking process."""
        self.stop_event = True
        self.thread.join()

# Example usage
def example_usage():
    # Set up logging
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)
    
    # Create two talking processes
    process1 = TalkingProcess("P1", p_k=0.3)
    process2 = TalkingProcess("P2", p_k=0.3)
    
    # Link the processes so they can detect when the other is talking
    def update_other_talking(p1, p2):
        while not (p1.stop_event or p2.stop_event):
            p1.other_is_talking = p2.state == 'talking'
            p2.other_is_talking = p1.state == 'talking'
            time.sleep(0.1)
    
    # Start the processes
    process1.start()
    process2.start()
    
    # Start the monitoring thread
    monitor_thread = Thread(target=update_other_talking, args=(process1, process2))
    monitor_thread.start()
    
    # Log state changes
    try:
        while True:
            logger.info(f"P1: {process1.state}, P2: {process2.state}")
            time.sleep(1)
    except KeyboardInterrupt:
        # Clean shutdown
        process1.stop()
        process2.stop()
        monitor_thread.join()

if __name__ == "__main__":
    example_usage()