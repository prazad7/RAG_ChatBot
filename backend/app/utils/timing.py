import time
from contextlib import contextmanager


@contextmanager
def elapsed_timer():
    start = time.perf_counter()
    box = {"seconds": 0.0}
    try:
        yield box
    finally:
        box["seconds"] = round(time.perf_counter() - start, 3)
