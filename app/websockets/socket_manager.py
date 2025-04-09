from flask_socketio import SocketIO, emit, join_room, leave_room, disconnect
from threading import Thread, Event
import pandas as pd
from io import BytesIO
import base64
from datetime import datetime
import time

# Initialize SocketIO with specific configuration
socketio = SocketIO(
    async_mode='threading',
    cors_allowed_origins="*",
    logger=True,
    engineio_logger=True,
    ping_timeout=5000,  # 5 seconds in ms
    ping_interval=2500  # 2.5 seconds in ms
)

processing_tasks = {}  # Store processing status for each room

def init_socketio(app):
    """Initialize SocketIO with the Flask app"""
    socketio.init_app(
        app,
        async_mode='threading',
        cors_allowed_origins="*",
        logger=True,
        engineio_logger=True,
        ping_timeout=5000,
        ping_interval=2500
    )
    return socketio

def execute_query_and_process(builder, query, parameters, room):
    """Execute query and process results in background"""
    try:
        if room not in processing_tasks:
            processing_tasks[room] = {'status': 'started', 'room': room}
        
        # Check if task is already completed
        if processing_tasks[room].get('status') == 'completed':
            return
            
        # Emit status update
        socketio.emit('processing_status', {
            'status': 'executing_query',
            'message': 'Executing database query...',
            'room': room
        }, to=room, namespace='/ws')

        # Execute the query
        execution_result = builder.execute_query(query, parameters)
        print(f"Query execution result for room {room}:", execution_result)
        
        # Handle non-SELECT query results (INSERT/UPDATE/DELETE)
        if isinstance(execution_result, dict):
            result_data = {
                'status': 'completed',
                'success': execution_result.get('success', False),
                'data': execution_result,
                'type': 'text',
                'message': execution_result.get('message', 'Query executed'),
                'room': room
            }
            processing_tasks[room] = result_data
            socketio.emit('processing_status', result_data, to=room, namespace='/ws')
            return

        # Handle SELECT query results
        if not execution_result:
            result_data = {
                'status': 'completed',
                'success': True,
                'data': [],
                'type': 'text',
                'message': 'Query returned no results',
                'room': room
            }
            processing_tasks[room] = result_data
            socketio.emit('processing_status', result_data, to=room, namespace='/ws')
            return

        # For SELECT queries with data
        socketio.emit('processing_status', {
            'status': 'processing_data',
            'message': f'Query returned {len(execution_result)} rows. Processing data...',
            'room': room
        }, to=room, namespace='/ws')

        # Convert to DataFrame and then to Excel if needed
        if len(execution_result) > 10:
            df = pd.DataFrame(execution_result)
            excel_buffer = BytesIO()
            df.to_excel(excel_buffer, index=False, engine='openpyxl')
            excel_buffer.seek(0)
            
            # Convert to base64
            excel_base64 = base64.b64encode(excel_buffer.getvalue()).decode('utf-8')
            
            result_data = {
                'status': 'completed',
                'success': True,
                'data': {
                    'excel_data': excel_base64,
                    'filename': f"query_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                    'row_count': len(execution_result)
                },
                'type': 'excel',
                'message': f'Generated Excel data with {len(execution_result)} rows',
                'room': room
            }
        else:
            result_data = {
                'status': 'completed',
                'success': True,
                'data': execution_result,
                'type': 'text',
                'message': f'Query returned {len(execution_result)} rows',
                'room': room
            }
        
        # Store and emit the processed data
        processing_tasks[room] = result_data
        socketio.emit('processing_status', result_data, to=room, namespace='/ws')
        print(f"Emitted final result for room {room}")
        
    except Exception as e:
        error_data = {
            'status': 'error',
            'success': False,
            'data': [],
            'type': 'text',
            'error': str(e),
            'message': f'Failed to process data: {str(e)}',
            'room': room
        }
        processing_tasks[room] = error_data
        socketio.emit('processing_status', error_data, to=room, namespace='/ws')
        print(f"Error in room {room}:", str(e))
    finally:
        # Clean up task after delay
        time.sleep(5)  # Give time for client to receive the message
        if room in processing_tasks:
            del processing_tasks[room]

def start_background_task(builder, query, parameters, room):
    """Start a background thread to execute query and process data"""
    # Clear any existing task for this room
    if room in processing_tasks:
        del processing_tasks[room]
        
    thread = Thread(target=execute_query_and_process, args=(builder, query, parameters, room))
    thread.daemon = True
    thread.start()
    return thread

@socketio.on('connect', namespace='/ws')
def handle_connect():
    """Handle client connection"""
    print("Client connected to /ws namespace")
    emit('connect_response', {'status': 'connected'})

@socketio.on('disconnect', namespace='/ws')
def handle_disconnect():
    """Handle client disconnection"""
    print("Client disconnected from /ws namespace")

@socketio.on('join', namespace='/ws')
def on_join(data):
    """Handle client joining a room"""
    room = data.get('room')
    if room:
        join_room(room)
        print(f"Client joined room: {room}")
        # Send current status if exists
        if room in processing_tasks:
            emit('processing_status', processing_tasks[room], to=room)

@socketio.on('leave', namespace='/ws')
def on_leave(data):
    """Handle client leaving a room"""
    room = data.get('room')
    if room:
        leave_room(room)
        print(f"Client left room: {room}")

@socketio.on('check_status', namespace='/ws')
def handle_status_check(data):
    """Handle status check requests from client"""
    room = data.get('room')
    if room and room in processing_tasks:
        emit('processing_status', processing_tasks[room], to=room)
    else:
        emit('processing_status', {
            'status': 'unknown',
            'message': 'No task found for this room',
            'room': room
        }, to=room)

@socketio.on_error_default
def default_error_handler(e):
    """Handle any socket.io errors"""
    print(f"SocketIO Error: {str(e)}")
    return False  # Don't disconnect on error
