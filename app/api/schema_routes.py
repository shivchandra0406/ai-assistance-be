from flask import Blueprint, jsonify, request, send_file
from app.utils.schema_extractor import SchemaExtractor
from app.utils.query_builder import QueryBuilder
from app.utils.response_handler import ResponseHandler
import pandas as pd
from io import BytesIO
import base64
from datetime import datetime
import os
from app.websockets.socket_manager import start_background_task
from app.utils.timeout_utils import execute_with_timeout
import uuid

schema_bp = Blueprint('schema', __name__)

@schema_bp.route('/schemas/extract', methods=['POST'])
def extract_schemas():
    """Extract and store all database schemas in the vector database."""
    try:
        print("start")
        extractor = SchemaExtractor()
        print("end")
        num_schemas = extractor.store_schemas_in_vectordb()
        return ResponseHandler.success(
            data=num_schemas,
            type="text",
            message="Schemas extracted and stored successfully"
        )
    except Exception as e:
        return ResponseHandler.error(
            error=str(e),
            message="Failed to extract schemas"
        )

@schema_bp.route('/schemas/search', methods=['GET'])
def search_schemas():
    """Search for relevant schema information."""
    query = request.args.get('query')
    if not query:
        return jsonify({
            'message': 'Query parameter is required',
            'status': 'error'
        }), 400
    
    try:
        extractor = SchemaExtractor()
        results = extractor.search_schemas(query)
        return ResponseHandler.success(
            data=results,
            type="text",
            message="Schemas retrieved successfully"
        )
    except Exception as e:
        return ResponseHandler.error(
            error=str(e),
            message="Failed to search schemas"
        )

@schema_bp.route('/query/build', methods=['POST'])
def build_query():
    """Build a SQL query from natural language input."""
    data = request.get_json()
    print(data)
    if not data or 'query' not in data:
        return ResponseHandler.error(
            error="Query is required in request body",
            message="Query is required in request body"
        )
    
    try:
        builder = QueryBuilder()
        print("builder")
        query_result = builder.build_query(data['query'])
        print("query_result", query_result)
        if query_result.get('sql_query'):
            # Try to execute query with 30-second timeout
            result, timed_out = execute_with_timeout(
                builder.execute_query,
                timeout_seconds=30,
                query=query_result['sql_query'],
                parameters=None
            )
            
            if timed_out:
                # Query is taking too long, move to background processing
                room_id = str(uuid.uuid4())
                start_background_task(
                    builder=builder,
                    query=query_result['sql_query'],
                    parameters=None,
                    room=room_id
                )
                return ResponseHandler.success(
                    data={
                        "room_id": room_id,
                        "status": "processing",
                        "message": "Query is taking longer than 30 seconds, moved to background processing"
                    },
                    type="background_process",
                    message="Query moved to background processing. Listen for updates on the WebSocket."
                )
            
            # Query completed within timeout
            if result:
                if len(result) > 10:
                    # Convert to DataFrame and then to Excel for large results
                    df = pd.DataFrame(result)
                    excel_buffer = BytesIO()
                    df.to_excel(excel_buffer, index=False, engine='openpyxl')
                    excel_buffer.seek(0)
                    
                    # Convert to base64
                    excel_base64 = base64.b64encode(excel_buffer.getvalue()).decode('utf-8')
                    
                    return ResponseHandler.success(
                        data={
                            "excel_data": excel_base64,
                            "filename": f"query_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                            "row_count": len(result)
                        },
                        type="excel",
                        message=f"Query returned {len(result)} rows"
                    )
                else:
                    # Return raw data for small results
                    return ResponseHandler.success(
                        data=result,
                        type="text",
                        message=f"Query returned {len(result)} rows"
                    )
            else:
                # Query returned no results
                return ResponseHandler.success(
                    data=[],
                    type="text",
                    message="Query returned no results"
                )
        else:
            required_params = query_result.get('required_parameters', [])
            
            return ResponseHandler.error(
                error=", ".join(required_params) if isinstance(required_params, list) else str(required_params),
                message=query_result.get('explanation', 'An explanation is not available.')
            )

    except Exception as e:
        return ResponseHandler.error(
            error=str(e),
            message="Failed to build query"
        )

@schema_bp.route('/query/execute', methods=['POST'])
def execute_query():
    """Execute a SQL query with optional parameters."""
    data = request.get_json()
    if not data or 'query' not in data:
        return ResponseHandler.error(
            error="Query is required in request body",
            message="Query is required in request body"
        )
    
    try:
        builder = QueryBuilder()
        parameters = data.get('parameters')
        results = builder.execute_query(data['query'], parameters)
        return ResponseHandler.success(
            data=results,
            type="text",
            message="Query executed successfully"
        )
    except Exception as e:
        return ResponseHandler.error(
            error=str(e),
            message="Failed to execute query"
        )