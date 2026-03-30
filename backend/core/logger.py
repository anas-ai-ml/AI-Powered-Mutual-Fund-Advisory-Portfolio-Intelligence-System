from collections import deque
from typing import Any


_EVENTS = deque(maxlen=200)


def log_event(event: Any):
    _EVENTS.append(event)
