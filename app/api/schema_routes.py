from flask import Blueprint, jsonify, request
from app.utils.schema_extractor import SchemaExtractor
from app.utils.query_builder import QueryBuilder

schema_bp = Blueprint('schema', __name__)

@schema_bp.route('/schemas/extract', methods=['POST'])
def extract_schemas():
    """Extract and store all database schemas in the vector database."""
    try:
        print("start")
        extractor = SchemaExtractor()
        print("end")
        num_schemas = extractor.store_schemas_in_vectordb()
        return jsonify({
            'message': f'Successfully extracted and stored {num_schemas} schemas',
            'status': 'success'
        })
    except Exception as e:
        return jsonify({
            'message': f'Error extracting schemas: {str(e)}',
            'status': 'error'
        }), 500

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
        return jsonify({
            'results': results,
            'status': 'success'
        })
    except Exception as e:
        return jsonify({
            'message': f'Error searching schemas: {str(e)}',
            'status': 'error'
        }), 500

@schema_bp.route('/query/build', methods=['POST'])
def build_query():
    """Build a SQL query from natural language input."""
    data = request.get_json()
    print(data)
    if not data or 'query' not in data:
        return jsonify({
            'message': 'Query is required in request body',
            'status': 'error'
        }), 400
    
    try:
        builder = QueryBuilder()
        print("builder")
        result = builder.build_query(data['query'])
        return jsonify({
            'result': result,
            'status': 'success'
        })
    except Exception as e:
        return jsonify({
            'message': f'Error building query: {str(e)}',
            'status': 'error'
        }), 500

@schema_bp.route('/query/execute', methods=['POST'])
def execute_query():
    """Execute a SQL query with optional parameters."""
    data = request.get_json()
    if not data or 'query' not in data:
        return jsonify({
            'message': 'Query is required in request body',
            'status': 'error'
        }), 400
    
    try:
        builder = QueryBuilder()
        parameters = data.get('parameters')
        results = builder.execute_query(data['query'], parameters)
        return jsonify({
            'results': results,
            'status': 'success'
        })
    except Exception as e:
        return jsonify({
            'message': f'Error executing query: {str(e)}',
            'status': 'error'
        }), 500
