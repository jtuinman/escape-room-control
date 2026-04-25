import queue
import threading
from typing import List


class Broadcaster:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._clients: List["queue.Queue[dict]"] = []

    def register(self) -> "queue.Queue[dict]":
        q: "queue.Queue[dict]" = queue.Queue(maxsize=200)
        with self._lock:
            self._clients.append(q)
        return q

    def unregister(self, q: "queue.Queue[dict]") -> None:
        with self._lock:
            if q in self._clients:
                self._clients.remove(q)

    def publish(self, event: dict) -> None:
        with self._lock:
            clients = list(self._clients)
        for q in clients:
            try:
                q.put_nowait(event)
            except queue.Full:
                pass
