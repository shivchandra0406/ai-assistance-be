import os
import google.generativeai as genai
from datetime import datetime, timedelta
import json
import pytz
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.date import DateTrigger
from app.utils.query_builder import QueryBuilder
from app.utils.email_sender import EmailSender
from app.utils.schema_extractor import SchemaExtractor

# Initialize Gemini
genai.configure(api_key=os.getenv('GOOGLE_API_KEY'))
model = genai.GenerativeModel('gemini-1.5-pro-latest')

def execute_query_job(query: str, user_email: str):
    """Standalone function for job execution"""
    try:
        query_builder = QueryBuilder()
        email_sender = EmailSender()
        
        # Execute query
        results = query_builder.execute_query(query)
        
        if results:
            # Send email with results
            email_sender.send_report(user_email, results)
            print(f"Scheduled report sent to {user_email}")
        else:
            # Send error notification
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
        # Configure scheduler with SQLAlchemy backend
        self.scheduler = BackgroundScheduler({
            'apscheduler.jobstores.default': {
                'type': 'sqlalchemy',
                'url': os.getenv('SQL_SERVER_CONNECTION')
            },
            'apscheduler.executors.default': {
                'class': 'apscheduler.executors.pool:ThreadPoolExecutor',
                'max_workers': '20'
            },
            'apscheduler.job_defaults.coalesce': True,
            'apscheduler.job_defaults.max_instances': 1
        })
        self.scheduler.start()
        self.default_timezone = 'Asia/Kolkata'
        self.query_builder = QueryBuilder()
        self.email_sender = EmailSender()
        self.schema_extractor = SchemaExtractor()

    def extract_schedule_info(self, user_query: str, current_time: datetime) -> dict:
        """Extract scheduling information from user query"""
        prompt = """
        You are a scheduling assistant. Extract scheduling information from the user's request.
        
        Current time: {current_time}
        User Request: "{user_query}"
        
        Rules:
        1. If a specific time is mentioned, use it
        2. If only time is mentioned (e.g., "10 PM"), use today's date
        3. If the requested time is in the future relative to current time, use today's date. Only move to the next day if the requested time has already passed.
        4. If no time is specified, default to next day 10:00 AM
        5. Extract email address if present
        6. Look for recurring patterns (daily, weekly, monthly) - but for now just return first occurrence
        
        IMPORTANT: You must respond with ONLY a valid JSON object in the following format:
        {{"schedule_time": "YYYY-MM-DDTHH:MM:SS", "email": null, "recurring": false, "confidence": 0.9}}
        
        Do not include any other text, only the JSON object.
        """
        
        try:
            # Format the prompt with current time and user query
            formatted_prompt = prompt.format(
                current_time=current_time.isoformat(),
                user_query=user_query
            )
            
            # Get response from model
            response = model.generate_content(formatted_prompt)
            response_text = response.text.strip()
            
            # Try to find JSON in the response
            try:
                # Look for the first { and last } to extract JSON
                start = response_text.find('{')
                end = response_text.rfind('}') + 1
                if start != -1 and end != 0:
                    json_str = response_text[start:end]
                    result = json.loads(json_str)
                else:
                    raise ValueError("No JSON object found in response")
                
                # Parse and validate schedule time
                schedule_time = datetime.fromisoformat(result['schedule_time'])
                schedule_time = pytz.timezone(self.default_timezone).localize(schedule_time)
                
                # If schedule time is in past, add a day
                if schedule_time <= current_time:
                    schedule_time += timedelta(days=1)
                
                result['schedule_time'] = schedule_time.isoformat()
                return result
                
            except json.JSONDecodeError as je:
                print(f"Failed to parse JSON from response: {response_text}")
                raise
                
        except Exception as e:
            print(f"Error extracting schedule info: {str(e)}")
            # Return default values
            default_time = current_time.replace(hour=10, minute=0, second=0, microsecond=0)
            if default_time <= current_time:
                default_time += timedelta(days=1)
            
            return {
                "schedule_time": default_time.isoformat(),
                "email": None,
                "recurring": False,
                "confidence": 0.5
            }

    def classify_intent(self, user_query: str) -> str:
        """Classify user intent as 'run_now', 'schedule', or 'unknown'"""
        prompt = f"""
        You are a helpful assistant. Your task is to **classify** the user's intent regarding a report request.
        
        Classify the intent into one of these categories:
        - "run_now": User wants the report immediately
        - "schedule": User wants to schedule the report for later
        - "unknown": Intent is unclear or request is invalid
        
        Examples:
        - "show me sales report" -> "run_now"
        - "send me report at 5pm" -> "schedule"
        - "email me report tomorrow" -> "schedule"
        - "what's the weather" -> "unknown"
        
        User Request: "{user_query}"
        
        Return ONLY ONE of these exact words: "run_now", "schedule", or "unknown"
        """
        
        try:
            response = model.generate_content(prompt)
            intent = response.text.strip().lower()
            
            if intent in ["run_now", "schedule", "unknown"]:
                return intent
            return "unknown"
            
        except Exception as e:
            print(f"Error classifying intent: {str(e)}")
            return "unknown"

    def analyze_request(self, data: dict) -> dict:
        """Analyze user request and handle scheduling if needed"""
        try:
            user_request = data.get('request', '')
            user_email = data.get('user_email', '')
            print("user_email", user_email)
            
            if not user_request or not user_email:
                return {
                    "success": False,
                    "error": "Missing required fields: request and user_email"
                }
            
            # Step 1: Classify Intent
            intent = self.classify_intent(user_request)
            print("Intent:", intent)
            
            # Step 2: Generate Query and Schedule Info
            query_info = self.query_builder.build_query(user_request)
            
            if not query_info or not query_info.get('sql_query'):
                return {
                    "success": False,
                    "error": "Could not generate valid query",
                    "message":query_info.get('explanation', 'Failed to generate query')
                }
            
            # Step 3: Handle based on intent
            if intent == "schedule":
                # Get current time in default timezone
                current_time = datetime.now(pytz.timezone(self.default_timezone))
                
                # Extract schedule information
                schedule_info = self.extract_schedule_info(user_request, current_time)
                print("Schedule Info:", schedule_info)
                print(user_email)
                # Use extracted email if available and no email provided
                if not user_email and schedule_info.get('email'):
                    user_email = schedule_info['email']
                
                # Parse schedule time
                schedule_time = datetime.fromisoformat(schedule_info['schedule_time'])
                if not schedule_time.tzinfo:
                    schedule_time = pytz.timezone(self.default_timezone).localize(schedule_time)
                
                # Schedule the job using the standalone function
                self.scheduler.add_job(
                    func=execute_query_job,
                    trigger=DateTrigger(
                        run_date=schedule_time,
                        timezone=self.default_timezone
                    ),
                    args=[query_info['sql_query'], user_email],
                    id=f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                )
                print("Scheduled job added successfully", user_email,query_info['sql_query'],schedule_time)
                
                return {
                    "success": True,
                    "requires_scheduling": True,
                    "schedule_time": schedule_time.isoformat(),
                    "timezone": self.default_timezone,
                    "explanation": query_info['explanation'],
                    "sql_query": query_info['sql_query'],
                    "confidence": schedule_info['confidence']
                }
                
            elif intent == "run_now":
                # Execute immediately using the standalone function
                execute_query_job(query_info['sql_query'], user_email)
                return {
                    "success": True,
                    "requires_scheduling": False,
                    "message": "Report sent successfully",
                    "explanation": query_info['explanation']
                }
            
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
