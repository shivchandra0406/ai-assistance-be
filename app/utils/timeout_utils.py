import signal
from contextlib import contextmanager
from typing import Optional
import threading
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
import uuid
from flask_socketio import emit

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

def start_background_task(builder, query: str, parameters: dict = None, room: str = None, user_email: str = None):
    """Start a background task for long-running queries
    
    Args:
        builder: QueryBuilder instance
        query: SQL query to execute
        parameters: Query parameters if any
        room: WebSocket room ID for updates
        user_email: User's email for notifications
    """
    def background_task():
        try:
            # Execute query
            result = builder.execute_query(query, parameters)
            
            if result:
                # Format success response
                response_data = {
                    "status": "completed",
                    "data": result,
                    "message": f"Query completed successfully with {len(result)} results"
                }
            else:
                # Format empty result response
                response_data = {
                    "status": "completed",
                    "data": [],
                    "message": "Query completed with no results"
                }
                
            # Emit result to WebSocket room
            if room:
                emit('query_result', response_data, room=room, namespace='/ws')
                
        except Exception as e:
            error_message = f"Error executing query: {str(e)}"
            print(error_message)
            
            # Emit error to WebSocket room
            if room:
                emit('query_error', {
                    "status": "error",
                    "error": error_message
                }, room=room, namespace='/ws')
    
    # Start the background thread
    thread = threading.Thread(target=background_task)
    thread.daemon = True
    thread.start()
    
    return thread
