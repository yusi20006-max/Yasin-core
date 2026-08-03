import queue
import threading
from typing import Optional, Any
from .models import Job


class JobQueue:
    """
    Thread-safe Priority Queue for Jobs.
    Sorts by:
      1. Priority (highest first, i.e., larger priority values executed first)
      2. Time created (oldest first, FIFO for equal priority)
      3. Unique counter (fallback tie-breaker to prevent comparison errors on Job objects)
    """

    def __init__(self):
        self._queue = queue.PriorityQueue()
        self._lock = threading.RLock()
        self._counter = 0

    def put(self, job: Job) -> None:
        """
        Thread-safely adds a Job to the priority queue.
        """
        with self._lock:
            self._counter += 1
            # Python's PriorityQueue retrieves lowest values first.
            # So, we negate priority (higher priority gets smaller negative number).
            # We use job.created_at for FIFO ordering, and self._counter as the tie-breaker.
            item = (-job.priority, job.created_at, self._counter, job)
            self._queue.put(item)

    def get(self, timeout: Optional[float] = None) -> Job:
        """
        Blocks or waits up to timeout to retrieve the next Job.
        Raises queue.Empty if timeout is reached or queue is empty in non-blocking mode.
        """
        # We don't hold the lock during blocking get() to allow other threads to put().
        item = self._queue.get(block=True, timeout=timeout)
        return item[3]

    def get_nowait(self) -> Job:
        """
        Non-blocking get. Raises queue.Empty if queue is empty.
        """
        item = self._queue.get_nowait()
        return item[3]

    def empty(self) -> bool:
        """
        Checks if the queue is empty.
        """
        return self._queue.empty()

    def size(self) -> int:
        """
        Returns the current approximate size of the queue.
        """
        return self._queue.qsize()

    def clear(self) -> None:
        """
        Clears all items in the queue thread-safely.
        """
        with self._lock:
            while not self._queue.empty():
                try:
                    self._queue.get_nowait()
                except queue.Empty:
                    break
