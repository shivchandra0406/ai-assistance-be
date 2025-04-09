from flask_socketio import SocketIO, emit
from threading import Thread
import pandas as pd
from io import BytesIO
import base64
from datetime import datetime

socketio = SocketIO()

def init_socketio(app):
    """Initialize SocketIO with the Flask app"""
    socketio.init_app(app, cors_allowed_origins="*")
    return socketio

def execute_query_and_process(builder, query, parameters, room):
    """Execute query and process results in background"""
    try:
        # Emit status update
        socketio.emit('processing_status', {
            'status': 'executing_query',
            'message': 'Executing database query...'
        }, room=room)

        # Execute the query
        execution_result = builder.execute_query(query, parameters)
        
        # Handle non-SELECT query results (INSERT/UPDATE/DELETE)
        if isinstance(execution_result, dict):
            socketio.emit('processing_status', {
                'status': 'completed',
                'success': execution_result.get('success', False),
                'data': execution_result,
                'type': 'text',
                'message': execution_result.get('message', 'Query executed')
            }, room=room)
            return

        # Handle SELECT query results
        if not execution_result:
            socketio.emit('processing_status', {
                'status': 'completed',
                'success': True,
                'data': [],
                'type': 'text',
                'message': 'Query returned no results'
            }, room=room)
            return

        # For SELECT queries with data
        socketio.emit('processing_status', {
            'status': 'processing_data',
            'message': f'Query returned {len(execution_result)} rows. Processing data...'
        }, room=room)

        # Convert to DataFrame and then to Excel
        df = pd.DataFrame(execution_result)
        excel_buffer = BytesIO()
        df.to_excel(excel_buffer, index=False, engine='openpyxl')
        excel_buffer.seek(0)
        
        # Convert to base64
        excel_base64 = base64.b64encode(excel_buffer.getvalue()).decode('utf-8')
        
        # Prepare response data
        response_data = {
            'status': 'completed',
            'success': True,
            'data': {
                'excel_data': excel_base64,
                'filename': f"query_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                'row_count': len(execution_result)
            },
            'type': 'excel',
            'message': f'Generated Excel data with {len(execution_result)} rows'
        }
        
        # Emit the processed data
        socketio.emit('processing_status', response_data, room=room)
        
    except Exception as e:
        error_response = {
            'status': 'error',
            'success': False,
            'data': [],
            'type': 'text',
            'error': str(e),
            'message': f'Failed to process data: {str(e)}'
        }
        socketio.emit('processing_status', error_response, room=room)

def start_background_task(builder, query, parameters, room):
    """Start a background thread to execute query and process data"""
    thread = Thread(target=execute_query_and_process, args=(builder, query, parameters, room))
    thread.daemon = True
    thread.start()
    return thread
