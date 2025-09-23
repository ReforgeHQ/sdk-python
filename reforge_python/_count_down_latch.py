import threading
from typing import Optional


class CountDownLatch:
    def __init__(self, count: int = 1) -> None:
        self.count = count
        self.lock = threading.Condition()

    def count_down(self) -> None:
        with self.lock:
            self.count -= 1
            if self.count <= 0:
                self.lock.notify_all()

    def wait(self, timeout: Optional[int] = None) -> bool:
        with self.lock:
            if self.count > 0:
                self.lock.wait(timeout)
            return self.count <= 0
