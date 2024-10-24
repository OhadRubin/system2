import multiprocessing
import threading
import queue
import time
import pygame
import sys
import random


class Logger:
    def __init__(self, status_queue, process_name, activity):
        self.status_queue = status_queue
        self.process_name = process_name
        self.activity = activity

    def log_status(self, status):
        self.status_queue.put((self.process_name, self.activity, status))


class ThinkingThread(threading.Thread):
    def __init__(
        self,
        mouth_queue,
        status_queue,
        stop_event,
        brain_queue,
        process_name,
        mult,
    ):
        super().__init__()
        self.mouth_queue = mouth_queue
        self.logger = Logger(status_queue, process_name, "thinking")
        self.stop_event = stop_event
        self.brain_queue = brain_queue
        self.thoughts = []
        self.mult = mult
        self.thinking_probability = 0.1

    def run(self):
        while not self.stop_event.is_set():
            self.think()

    def think(self):
        self._collect_messages()

        for thought in self.thoughts:
            self.mouth_queue.put(thought)
            self.logger.log_status("message_sent")

        if random.random() < self.thinking_probability:
            self_thought = f"Thought generated during thinking"
            self.brain_queue.put(self_thought)
            self.logger.log_status("message_generated")

    def _collect_messages(self):
        self.thoughts = []
        while True:
            try:
                received_message = self.brain_queue.get_nowait()
                self.thoughts.append(received_message)
                self.logger.log_status("message_received")
            except queue.Empty:
                break


class TalkingThread(threading.Thread):
    def __init__(
        self,
        pipe,
        mouth_queue,
        brain_queue,
        status_queue,
        stop_event,
        process_name,
        mult,
        shared_state,
    ):
        super().__init__()
        self.other_ear_conn = pipe
        self.mouth_queue = mouth_queue
        self.brain_queue = brain_queue
        self.logger = Logger(status_queue, process_name, "talking")
        self.stop_event = stop_event
        self.mult = mult
        self.thinking_probability = 0.1
        self.talking_probability = 0.5
        self.interrupt_probability = 0.05  # Probability to interrupt
        self.process_name = process_name
        self.shared_state = shared_state
        self.min_talking_duration = 0.5  # Minimum talking duration in seconds
        self.max_talking_duration = 2.0  # Maximum talking duration in seconds

    def run(self):
        while not self.stop_event.is_set():
            if random.random() < self.talking_probability:
                self.start_talking()
            try:
                message = self.mouth_queue.get(timeout=1)
                self.start_talking(message)
            except queue.Empty:
                pass

    def start_talking(self, message="bla"):
        other_process_name = (
            "Process1" if self.process_name == "Process2" else "Process2"
        )

        # Before talking, check if the other process is talking
        if self.shared_state.get(f"{other_process_name}_is_talking", False):
            # Other process is talking
            if random.random() < self.interrupt_probability:
                # Decide to interrupt
                pass  # Proceed to talk
            else:
                time.sleep(0.2)
                # Decide to yield
                return
        else:
            # Other process is not talking
            pass  # Proceed to talk

        # Indicate that this process intends to start talking
        self.shared_state[f"{self.process_name}_wants_to_talk"] = True

        # Small delay to simulate potential collision
        time.sleep(0.0001)  # Sleep for 0.1 milliseconds

        # Collision detection: check if both processes want to talk
        if self.shared_state.get(f"{other_process_name}_wants_to_talk", False):
            # Both processes want to talk at the same time
            if self.process_name > other_process_name:
                # This process yields
                self.shared_state[f"{self.process_name}_wants_to_talk"] = False
                return
            else:
                # Other process yields
                self.shared_state[f"{other_process_name}_wants_to_talk"] = False

        # Proceed to talk
        self.shared_state[f"{self.process_name}_is_talking"] = True
        self.shared_state[f"{self.process_name}_wants_to_talk"] = False
        self.logger.log_status("on")  # Log that the process has started talking

        # Generate random talking duration
        talking_duration = random.uniform(
            self.min_talking_duration, self.max_talking_duration
        )
        start_time = time.time()

        # Simulate talking by continuously sending messages for the duration
        while time.time() - start_time < talking_duration:
            if random.random() < self.thinking_probability:
                self_thought = f"Thought generated during talking"
                self.brain_queue.put(self_thought)
                self.logger.log_status("message_generated")

            # Send the message
            self.other_ear_conn.send(message)
            self.logger.log_status("message_sent")

            # Optional: sleep briefly to prevent tight loop (simulate natural speaking rate)
            time.sleep(0.1)  # Sleep for 0.1 seconds

            # Check if stop_event is set to allow for graceful shutdown
            if self.stop_event.is_set():
                break

        # Indicate that this process has finished talking
        self.shared_state[f"{self.process_name}_is_talking"] = False
        self.logger.log_status("off")  # Log that the process has stopped talking


class ListeningThread(threading.Thread):
    def __init__(
        self, other_conn, status_queue, stop_event, brain_queue, process_name, mult
    ):
        super().__init__()
        self.ear_conn = other_conn
        self.logger = Logger(status_queue, process_name, "listening")
        self.stop_event = stop_event
        self.brain_queue = brain_queue
        self.mult = mult
        self.shared_state = None  # Will be set in process_function
        self.process_name = process_name

    def run(self):
        while not self.stop_event.is_set():
            self.listen()

    def listen(self):
        if self.ear_conn.poll():
            message = self.ear_conn.recv()
            self.brain_queue.put(message)
            self.logger.log_status("message_received")
            # Optionally, handle any logic related to the shared state here


def process_function(conn, other_conn, status_queue, process_name, mult, shared_state):
    mouth_queue = queue.Queue()
    brain_queue = queue.Queue()
    stop_event = threading.Event()

    thinker = ThinkingThread(
        mouth_queue, status_queue, stop_event, brain_queue, process_name, mult
    )
    talker = TalkingThread(
        conn,
        mouth_queue,
        brain_queue,
        status_queue,
        stop_event,
        process_name,
        mult,
        shared_state,
    )
    listener = ListeningThread(
        other_conn, status_queue, stop_event, brain_queue, process_name, mult
    )
    listener.shared_state = shared_state  # Set shared_state for listener if needed

    thinker.start()
    talker.start()
    listener.start()

    thinker.join()
    talker.join()
    listener.join()


if __name__ == "__main__":
    mult = 0.5
    parent_conn1, child_conn1 = multiprocessing.Pipe()
    parent_conn2, child_conn2 = multiprocessing.Pipe()
    status_queue = multiprocessing.Queue()

    # Create a multiprocessing Manager to hold shared state
    manager = multiprocessing.Manager()
    shared_state = manager.dict()
    shared_state["Process1_is_talking"] = False
    shared_state["Process2_is_talking"] = False
    shared_state["Process1_wants_to_talk"] = False
    shared_state["Process2_wants_to_talk"] = False

    process1 = multiprocessing.Process(
        target=process_function,
        args=(parent_conn1, child_conn2, status_queue, "Process1", mult, shared_state),
        name="Process1",
    )
    process1.start()

    process2 = multiprocessing.Process(
        target=process_function,
        args=(parent_conn2, child_conn1, status_queue, "Process2", mult, shared_state),
        name="Process2",
    )
    process2.start()

    statuses = {
        "Process1": {
            "thinking": {
                "count": 0,
                "last_update": time.time(),
                "reset_time": time.time(),
                "messages_per_second": 0,
                "status": "off",
            },
            "talking": {
                "count": 0,
                "last_update": time.time(),
                "reset_time": time.time(),
                "messages_per_second": 0,
                "status": "off",
            },
            "listening": {
                "count": 0,
                "last_update": time.time(),
                "reset_time": time.time(),
                "messages_per_second": 0,
                "status": "off",
            },
        },
        "Process2": {
            "thinking": {
                "count": 0,
                "last_update": time.time(),
                "reset_time": time.time(),
                "messages_per_second": 0,
                "status": "off",
            },
            "talking": {
                "count": 0,
                "last_update": time.time(),
                "reset_time": time.time(),
                "messages_per_second": 0,
                "status": "off",
            },
            "listening": {
                "count": 0,
                "last_update": time.time(),
                "reset_time": time.time(),
                "messages_per_second": 0,
                "status": "off",
            },
        },
    }

    pygame.init()
    screen = pygame.display.set_mode((400, 200))
    pygame.display.set_caption("Process Status")
    clock = pygame.time.Clock()
    font = pygame.font.Font(None, 24)

    running = True
    try:
        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False

            try:
                while True:
                    process_name, activity, status = status_queue.get_nowait()
                    now = time.time()
                    data = statuses[process_name][activity]
                    if status in ("on", "off"):
                        data["status"] = status
                    elif status in (
                        "message_sent",
                        "message_received",
                        "message_generated",
                    ):
                        data["count"] += 1
                        data["last_update"] = now

                        if now - data["reset_time"] >= 1.0:
                            elapsed = now - data["reset_time"]
                            data["messages_per_second"] = data["count"] / elapsed
                            data["count"] = 0
                            data["reset_time"] = now
            except queue.Empty:
                pass

            screen.fill((255, 255, 255))

            x_offset = 50
            y_offset = 50
            processes = ["Process1", "Process2"]
            activities = ["thinking", "talking", "listening"]
            for i, process_name in enumerate(processes):
                x = x_offset + i * 200
                y = y_offset
                # Change color if the process is talking
                talking_status = statuses[process_name]["talking"]["status"]
                if talking_status == "on":
                    color = (255, 0, 0)  # Red color when talking
                else:
                    color = (0, 0, 0)  # Black color when not talking
                text = font.render(f"{process_name}", True, color)
                screen.blit(text, (x, y))
                y += 30
                for activity in activities:
                    data = statuses[process_name][activity]
                    messages_per_second = data["messages_per_second"]
                    activity_status = data["status"]
                    display_text = f"{activity}: {activity_status}, {messages_per_second:.2f} msg/s"
                    text = font.render(display_text, True, (0, 0, 0))
                    screen.blit(text, (x, y))
                    y += 30

            pygame.display.flip()
            clock.tick(60)

    except KeyboardInterrupt:
        pass

    process1.terminate()
    process2.terminate()

    process1.join()
    process2.join()

    pygame.quit()
    sys.exit()
