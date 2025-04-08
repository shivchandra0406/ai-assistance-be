from flask import Blueprint, jsonify, request
from app import db
from app.utils.data_generator import generate_bulk_data
from sqlalchemy.exc import SQLAlchemyError

bulk_routes = Blueprint('bulk', __name__)

@bulk_routes.route('/api/bulk/generate', methods=['POST'])
def generate_bulk_records():
    try:
        # Get count from request, default to 10
        count = request.json.get('count', 10)
        
        # Validate count
        if not isinstance(count, int) or count <= 0:
            return jsonify({
                'status': 'error',
                'message': 'Count must be a positive integer between 1 and 100'
            }), 400
        
        # Generate bulk data
        bulk_data = generate_bulk_data(count)
        
        # Insert data in batches
        for data in bulk_data:
            # First insert address and project
            db.session.add(data['address'])
            db.session.add(data['project'])
            db.session.flush()  # This assigns IDs to address and project
            
            # Now set the IDs in the lead
            data['lead'].address_id = data['address'].id
            data['lead'].project_id = data['project'].id
            db.session.add(data['lead'])
        
        # Commit all changes
        db.session.commit()
        
        return jsonify({
            'status': 'success',
            'message': f'Successfully generated {count} records',
            'count': count
        })
        
    except SQLAlchemyError as e:
        db.session.rollback()
        return jsonify({
            'status': 'error',
            'message': f'Database error: {str(e)}'
        }), 500
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'status': 'error',
            'message': f'Error: {str(e)}'
        }), 500
    finally:
        db.session.close()
