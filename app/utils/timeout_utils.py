import signal
from contextlib import contextmanager
from typing import Optional
import threading
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError

class QueryTimeoutError(Exception):
    """Exception raised when a query execution times out"""
    pass

@contextmanager
def timeout_context(seconds: int):
    """Context manager for timing out function execution"""
    def timeout_handler(signum, frame):
        raise QueryTimeoutError("Query execution timed out")

    # Set the timeout handler
    signal.signal(signal.SIGALRM, timeout_handler)
    signal.alarm(seconds)
    
    try:
        yield
    finally:
        # Disable the alarm
        signal.alarm(0)

def execute_with_timeout(func, timeout_seconds: int, *args, **kwargs):
    """Execute a function with a timeout using ThreadPoolExecutor"""
    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(func, *args, **kwargs)
        try:
            result = future.result(timeout=timeout_seconds)
            return result, False  # Second value indicates if timeout occurred
        except FutureTimeoutError:
            return None, True  # Timeout occurred
        except Exception as e:
            raise e  # Re-raise other exceptions
