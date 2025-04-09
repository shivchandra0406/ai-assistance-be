from flask import Blueprint, request
from app.utils.scheduler import QueryScheduler
from app.utils.response_handler import ResponseHandler

report_bp = Blueprint('report', __name__)
scheduler = QueryScheduler()

@report_bp.route('/analyze', methods=['POST'])
def analyze_report_request():
    try:
        # Get user email from header
        user_email = request.headers.get('User-Email')
        if not user_email:
            return ResponseHandler.error(
                error="Missing User-Email header",
                message="Please provide user email in the request header"
            )

        # Get request data
        data = request.get_json()
        if not data or 'request' not in data:
            return ResponseHandler.error(
                error="Missing request field",
                message="Please provide a request in the JSON body"
            )

        # Add email to data for scheduler
        data['user_email'] = user_email

        # Analyze request
        result = scheduler.analyze_request(data)

        if result.get('success', False):
            # Request was processed successfully
            if result.get('requires_scheduling', False):
                return ResponseHandler.success(
                    data={
                        'schedule_time': result['schedule_time'],
                        'timezone': result['timezone'],
                        'explanation': result['explanation'],
                        'confidence': result.get('confidence', 1.0)
                    },
                    message="Report has been scheduled successfully"
                )
            else:
                return ResponseHandler.success(
                    data={
                        'explanation': result.get('explanation', 'Report processed'),
                        'message': result.get('message', 'Report executed successfully')
                    },
                    message="Report has been processed successfully"
                )
        else:
            # There was an error
            return ResponseHandler.error(
                error=result.get('error', 'Unknown error'),
                message="Failed to process report request"
            )

    except Exception as e:
        return ResponseHandler.error(
            error=str(e),
            message="An error occurred while processing the request"
        )

@report_bp.route('/status', methods=['GET'])
def get_report_status():
    try:
        user_email = request.headers.get('User-Email')
        if not user_email:
            return ResponseHandler.error(
                error="Missing User-Email header",
                message="Please provide user email in the request header"
            )

        # Get scheduled jobs for the user
        jobs = scheduler.get_user_jobs(user_email)
        
        # Enhance job information for dashboard
        enhanced_jobs = []
        for job in jobs:
            enhanced_jobs.append({
                'id': job['id'],
                'next_run_time': job['next_run_time'],
                'sql_query': job['sql_query'],
                'status': 'Active' if job['next_run_time'] else 'Completed',
                'created_at': job.get('created_at', ''),
                'last_run': job.get('last_run', None),
                'last_status': job.get('last_status', 'Pending'),
                'actions': {
                    'can_delete': True,
                    'can_pause': True if job['next_run_time'] else False,
                    'can_resume': False if job['next_run_time'] else True
                }
            })
        
        return ResponseHandler.success(
            data={
                'jobs': enhanced_jobs,
                'total_jobs': len(enhanced_jobs),
                'active_jobs': sum(1 for j in enhanced_jobs if j['status'] == 'Active'),
                'completed_jobs': sum(1 for j in enhanced_jobs if j['status'] == 'Completed')
            },
            message="Successfully retrieved scheduled reports"
        )

    except Exception as e:
        return ResponseHandler.error(
            error=str(e),
            message="Failed to get report status"
        )

@report_bp.route('/job/<job_id>/action', methods=['POST'])
def job_action():
    """Control job actions (pause, resume, delete)"""
    try:
        user_email = request.headers.get('User-Email')
        if not user_email:
            return ResponseHandler.error(
                error="Missing User-Email header",
                message="Please provide user email in the request header"
            )

        job_id = request.view_args['job_id']
        action = request.json.get('action')

        if action not in ['pause', 'resume', 'delete']:
            return ResponseHandler.error(
                error="Invalid action",
                message="Action must be one of: pause, resume, delete"
            )

        result = scheduler.control_job(job_id, action, user_email)
        
        if result.get('success'):
            return ResponseHandler.success(
                data=result,
                message=f"Successfully {action}d job {job_id}"
            )
        else:
            return ResponseHandler.error(
                error=result.get('error', 'Unknown error'),
                message=f"Failed to {action} job {job_id}"
            )

    except Exception as e:
        return ResponseHandler.error(
            error=str(e),
            message="Failed to perform job action"
        )
