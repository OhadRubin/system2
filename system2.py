import multiprocessing
import threading
import queue
import time
import pygame
import sys
import random

CONST = 0.5

class SleepWait:
    def __init__(self, wait_time=1):
        self.wait_time = wait_time

    def __enter__(self):
        # Add randomness to the wait time
        random_wait = self.wait_time + random.uniform(
            -self.wait_time * CONST, self.wait_time * CONST
        )
        time.sleep(random_wait)

    def __exit__(self, exc_type, exc_val, exc_tb):
        random_wait = self.wait_time + random.uniform(
            -self.wait_time * CONST, self.wait_time * CONST
        )
        time.sleep(random_wait)


class Logger:
    def __init__(self, status_queue, process_name, activity):
        self.status_queue = status_queue
        self.process_name = process_name
        self.activity = activity

    def log_status(self, status):
        self.status_queue.put((self.process_name, self.activity, status))


class LogStatus:
    def __init__(self, logger, msg=None):
        self.logger = logger
        self.msg = msg
    def __enter__(self):
        if self.msg:
            self.logger.log_status(f"on ({self.msg})")
        else:
            self.logger.log_status("on")

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.logger.log_status("off")


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
        with LogStatus(self.logger, msg=f"{len(self.thoughts)}"):
            time.sleep((2 + len(self.thoughts)) * self.mult)


        with SleepWait(self.mult):
            for thought in self.thoughts:
                self.mouth_queue.put(thought)
            if random.random() < self.thinking_probability:
                self_thought = f"Thought generated during thinking at "
                self.brain_queue.put(self_thought)
        self._collect_messages()

    def _collect_messages(self):
        self.thoughts = []
        while True:
            try:
                received_message = self.brain_queue.get_nowait()
                self.thoughts.append(received_message)
            except queue.Empty:
                break


class TalkingThread(threading.Thread):
    def __init__(self, pipe, mouth_queue, brain_queue, status_queue, stop_event, process_name, mult):
        super().__init__()
        self.other_ear_conn = pipe
        self.mouth_queue = mouth_queue
        self.brain_queue = brain_queue
        self.logger = Logger(status_queue, process_name, "talking")
        self.stop_event = stop_event
        self.mult = mult
        self.thinking_probability = 0.1
        

    def run(self):
        while not self.stop_event.is_set():
            try:
                message = self.mouth_queue.get(timeout=1)
                self.talk(message)
            except queue.Empty:
                pass

    def talk(self, message):
        with LogStatus(self.logger):
            with SleepWait(self.mult):
                if random.random() < self.thinking_probability:
                    self_thought = f"Thought generated during talking at "
                    self.brain_queue.put(self_thought)
                self.other_ear_conn.send(message)


class ListeningThread(threading.Thread):
    def __init__(self, other_conn, status_queue, stop_event, brain_queue, process_name, mult):
        super().__init__()
        self.ear_conn = other_conn
        self.logger = Logger(status_queue, process_name, "listening")
        self.stop_event = stop_event
        self.brain_queue = brain_queue
        self.mult = mult

    def run(self):
        while not self.stop_event.is_set():
            self.listen()

    def listen(self):
        if self.ear_conn.poll():
            with LogStatus(self.logger):
                with SleepWait(self.mult):
                    message = self.ear_conn.recv()
                self.brain_queue.put(message)


def process_function(conn, other_conn, status_queue, process_name, mult):
    mouth_queue = queue.Queue()
    brain_queue = queue.Queue()
    stop_event = threading.Event()

    thinker = ThinkingThread(mouth_queue, status_queue, stop_event, brain_queue, process_name, mult)
    talker = TalkingThread(conn, mouth_queue, brain_queue, status_queue, stop_event, process_name, mult)
    listener = ListeningThread(other_conn, status_queue, stop_event, brain_queue, process_name, mult)

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

    process1 = multiprocessing.Process(
        target=process_function,
        args=(parent_conn1, child_conn2, status_queue, "Process1", mult),
        name="Process1",
    )
    process1.start()

    process2 = multiprocessing.Process(
        target=process_function,
        args=(parent_conn2, child_conn1, status_queue, "Process2", mult),
        name="Process2",
    )
    process2.start()

    statuses = {
        "Process1": {"thinking": "off", "talking": "off", "listening": "off"},
        "Process2": {"thinking": "off", "talking": "off", "listening": "off"},
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
                    process_name, activity, activity_status = status_queue.get_nowait()
                    statuses[process_name][activity] = activity_status
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
                text = font.render(f"{process_name}", True, (0, 0, 0))
                screen.blit(text, (x, y))
                y += 30
                for activity in activities:
                    status = statuses[process_name][activity]
                    display_text = f"{activity}: {status}"
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
