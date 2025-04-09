from datetime import datetime, timedelta
import pytz
import json
import google.generativeai as genai
import os
import uuid
import pandas as pd
from io import BytesIO
import base64
from app.utils.timeout_utils import start_background_task
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.date import DateTrigger
from app.utils.query_builder import QueryBuilder
from app.utils.email_sender import EmailSender
from app.utils.prompt_manager import PromptManager
from app.utils.response_handler import ResponseHandler

genai.configure(api_key=os.getenv('GOOGLE_API_KEY'))
model = genai.GenerativeModel('gemini-1.5-pro-latest')

def execute_query_job(query: str, user_email: str):
    """Standalone function for job execution"""
    try:
        query_builder = QueryBuilder()
        email_sender = EmailSender()
        results = query_builder.execute_query(query)
        
        if results:
            email_sender.send_report(user_email, results)
            print(f"Scheduled report sent to {user_email}")
        else:
            email_sender.send_error_notification(
                user_email, 
                "No results found or error executing query"
            )
            print(f"Error notification sent to {user_email}")
            
    except Exception as e:
        print(f"Error executing scheduled query: {str(e)}")
        email_sender = EmailSender()
        email_sender.send_error_notification(
            user_email,
            f"Error executing scheduled query: {str(e)}"
        )

class QueryScheduler:
    def __init__(self):
        self.scheduler = BackgroundScheduler()
        self.scheduler.start()
        self.default_timezone = 'Asia/Kolkata'
        self.query_builder = QueryBuilder()
        self.email_sender = EmailSender()

    def _parse_json_from_response(self, response_text: str) -> dict:
        """Extract and parse JSON from model response"""
        start = response_text.find('{')
        end = response_text.rfind('}') + 1
        
        if start != -1 and end != 0:
            json_str = response_text[start:end]
            return json.loads(json_str)
        else:
            raise ValueError("No JSON object found in response")

    def _get_default_schedule_time(self, current_time: datetime) -> str:
        """Get default schedule time (next day 10 AM)"""
        default_time = current_time.replace(hour=10, minute=0, second=0, microsecond=0)
        if default_time <= current_time:
            default_time += timedelta(days=1)
        return default_time.isoformat()

    def _validate_schedule_time(self, schedule_time: datetime, current_time: datetime) -> datetime:
        """Validate and adjust schedule time if needed"""
        if not schedule_time.tzinfo:
            schedule_time = pytz.timezone(self.default_timezone).localize(schedule_time)
        
        if schedule_time <= current_time:
            schedule_time += timedelta(days=1)
            
        return schedule_time

    def extract_schedule_info(self, user_request: str, current_time: datetime) -> dict:
        """Extract scheduling information from user request"""
        try:
            # Get response from model
            prompt = PromptManager.get_schedule_extraction_prompt(current_time.isoformat())
            response = model.generate_content(prompt + f"\nUser Request: {user_request}")
            
            try:
                # Parse response
                result = self._parse_json_from_response(response.text)
                
                # Validate schedule time
                schedule_time = datetime.fromisoformat(result['schedule_time'])
                schedule_time = self._validate_schedule_time(schedule_time, current_time)
                result['schedule_time'] = schedule_time.isoformat()
                
                return result
                
            except json.JSONDecodeError as je:
                print(f"Failed to parse JSON from response: {response.text}")
                raise
                
        except Exception as e:
            print(f"Error extracting schedule info: {str(e)}")
            return {
                "schedule_time": self._get_default_schedule_time(current_time),
                "email": None,
                "recurring": False,
                "confidence": 0.5
            }

    def _validate_intent(self, intent: str) -> str:
        """Validate and normalize intent"""
        intent = intent.strip().lower()
        return intent if intent in ["run_now", "schedule", "unknown"] else "unknown"

    def classify_intent(self, user_query: str) -> str:
        """Classify user intent as 'run_now', 'schedule', or 'unknown'"""
        try:
            prompt = PromptManager.get_intent_classification_prompt()
            response = model.generate_content(prompt + f"\nUser Request: {user_query}")
            return self._validate_intent(response.text)
            
        except Exception as e:
            print(f"Error classifying intent: {str(e)}")
            return "unknown"

    def _schedule_job(self, query: str, user_email: str, schedule_time: datetime) -> str:
        """Schedule a job and return its ID"""
        job_id = f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        self.scheduler.add_job(
            func=execute_query_job,
            trigger=DateTrigger(
                run_date=schedule_time,
                timezone=self.default_timezone
            ),
            args=[query, user_email],
            id=job_id
        )
        
        return job_id

    def _handle_schedule_request(self, query_info: dict, schedule_info: dict, user_email: str) -> dict:
        """Handle a schedule request and return response"""
        schedule_time = datetime.fromisoformat(schedule_info['schedule_time'])
        job_id = self._schedule_job(query_info['sql_query'], user_email, schedule_time)
        
        return {
            "success": True,
            "requires_scheduling": True,
            "schedule_time": schedule_time.isoformat(),
            "timezone": self.default_timezone,
            "explanation": query_info['explanation'],
            "sql_query": query_info['sql_query'],
            "confidence": schedule_info['confidence'],
            "job_id": job_id
        }

    def _handle_query_results(self, results: list, query: str) -> dict:
        """Handle query results based on size and format"""
        if not results:
            return {
                "success": True,
                "data": [],
                "type": "text",
                "message": "Query returned no results"
            }
        print("Results:", results)
        if len(results) > 10:
            # Convert to DataFrame and then to Excel for large results
            df = pd.DataFrame(results)
            excel_buffer = BytesIO()
            df.to_excel(excel_buffer, index=False, engine='openpyxl')
            excel_buffer.seek(0)
            
            # Convert to base64
            excel_base64 = base64.b64encode(excel_buffer.getvalue()).decode('utf-8')
            
            return {
                "success": True,
                "data": {
                    "excel_data": excel_base64,
                    "filename": f"query_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                    "row_count": len(results)
                },
                "type": "excel",
                "message": f"Query returned {len(results)} rows"
            }
        else:
            print("Results (text):", results)
            return {
                "success": True,
                "data": results,
                "type": "text",
                "message": f"Query returned {len(results)} rows"
            }

    def _handle_immediate_request(self, query_info: dict, user_email: str) -> dict:
        """Handle an immediate execution request with timeout handling"""
        try:
            # Execute query with timeout
            query = query_info['sql_query']
            result, timed_out = self.query_builder.execute_query_with_timeout(query)
            
            if timed_out:
                # Query is taking too long, move to background processing
                room_id = str(uuid.uuid4())
                start_background_task(
                    builder=self.query_builder,
                    query=query,
                    parameters=None,
                    room=room_id,
                    user_email=user_email  # Pass email for notifications
                )
                
                return {
                    "success": True,
                    "requires_scheduling": False,
                    "data": {
                        "room_id": room_id,
                        "status": "processing"
                    },
                    "type": "background_process",
                    "message": "Query moved to background processing. Listen for updates on the WebSocket."
                }
            
            # Query completed within timeout
            result_data = self._handle_query_results(result, query)
            result_data["requires_scheduling"] = False
            result_data["explanation"] = query_info['explanation']
            print("Result data:", result_data)
            return result_data
            
        except Exception as e:
            print(f"Error executing immediate query: {str(e)}")
            return {
                "success": False,
                "requires_scheduling": False,
                "error": str(e),
                "message": "Failed to execute query"
            }

    def analyze_request(self, data: dict) -> dict:
        """Analyze user request and handle scheduling if needed"""
        try:
            # Validate input
            user_request = data.get('request', '')
            user_email = data.get('user_email', '')
            print("user_email", user_email)
            
            if not user_request or not user_email:
                return {
                    "success": False,
                    "error": "Missing required fields"
                }
            
            # Step 1: Classify Intent
            intent = self.classify_intent(user_request)
            print("Intent:", intent)
            
            # Step 2: Generate Query
            query_info = self.query_builder.build_query(user_request)
            if not query_info or not query_info.get('sql_query'):
                return {
                    "success": False,
                    "error": "Could not generate valid query"
                }
            
            # Step 3: Handle based on intent
            if intent == "schedule":
                current_time = datetime.now(pytz.timezone(self.default_timezone))
                schedule_info = self.extract_schedule_info(user_request, current_time)
                print("Schedule Info:", schedule_info)
                print(user_email)
                
                return self._handle_schedule_request(query_info, schedule_info, user_email)
                
            elif intent == "run_now":
                return self._handle_immediate_request(query_info, user_email)
            
            else:  # unknown intent
                return {
                    "success": False,
                    "requires_scheduling": False,
                    "error": "Could not determine intent from request"
                }
            
        except Exception as e:
            print(f"Error analyzing request: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }

    def get_user_jobs(self, user_email: str) -> list:
        """Get all scheduled jobs for a user"""
        try:
            jobs = []
            for job in self.scheduler.get_jobs():
                # Check if this job is for the user
                if job.args and len(job.args) > 1 and job.args[1] == user_email:
                    jobs.append({
                        'id': job.id,
                        'next_run_time': job.next_run_time.isoformat() if job.next_run_time else None,
                        'sql_query': job.args[0] if job.args else None
                    })
            return jobs
        except Exception as e:
            print(f"Error getting user jobs: {str(e)}")
            return []
