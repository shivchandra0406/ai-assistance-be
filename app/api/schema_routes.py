from flask import Blueprint, jsonify, request, send_file
from app.utils.schema_extractor import SchemaExtractor
from app.utils.query_builder import QueryBuilder
from app.utils.response_handler import ResponseHandler
import pandas as pd
from io import BytesIO
import base64
from datetime import datetime
import os

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
            execution_result = builder.execute_query(query_result['sql_query'], None)
            if len(execution_result) < 11:
                return ResponseHandler.success(
                    data=execution_result,
                    type="text",
                    message="Query built successfully"
                )
            else:
                # Convert to DataFrame and then to Excel
                df = pd.DataFrame(execution_result)
                excel_buffer = BytesIO()
                df.to_excel(excel_buffer, index=False, engine='openpyxl')
                excel_buffer.seek(0)
                
                # Convert to base64
                excel_base64 = base64.b64encode(excel_buffer.getvalue()).decode('utf-8')
                
                return ResponseHandler.success(
                    data={
                        "excel_data": excel_base64,
                        "filename": f"query_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                        "row_count": len(execution_result)
                    },
                    type="excel",
                    message=f"Generated Excel data with {len(execution_result)} rows"
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
