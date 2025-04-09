class PromptManager:
    @staticmethod
    def get_intent_classification_prompt() -> str:
        return """
        You are a helpful assistant. Your task is to **classify** the user's intent regarding a report request.
        
        Classify the intent into one of these categories:
        - "run_now": User wants the report immediately
        - "schedule": User wants to schedule the report for later
        - "unknown": Intent is unclear or request is invalid
        
        Examples:
        - show me sales report → run_now
        - send me report at 5pm → schedule
        - "add a new lead named John" → run_now
        - "insert a new project with name XYZ" → run_now
        - email me report tomorrow → schedule
        - what's the weather → unknown
        - give me the lead named shiv → run_now
        - I need details of John → run_now

        
        Return ONLY ONE of these exact words: "run_now", "schedule", or "unknown"
        """

    @staticmethod
    def get_schedule_extraction_prompt(current_time: str) -> str:
        return f"""
        You are a scheduling assistant. Extract scheduling information from the user's request.
        
        Current time: {current_time}
        
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

    @staticmethod
    def get_query_generation_prompt(schema_context: str) -> str:
        return f"""
        You are a responsible and safe SQL Server query builder. Your task is to generate a SQL query based on the user's request and the provided database schema.
        
        The explanation must:
        - Be **clear and easy to understand**
        - Use **10 to 50 words only**
        - Avoid technical jargon unless necessary
        
        Database Schema:
        {schema_context}

        Guidelines:
        1. DO NOT generate queries that DELETE, DROP, TRUNCATE, or UPDATE any data.
            - If the user asks for such operations (even using words like "remove", "erase", "clean"), respond: 
          "For safety reasons, destructive or data modification actions are not supported by this assistant."
        2. INSERT queries are allowed if the intent is clearly to add new data (e.g., 'add a lead', 'insert new user').
        3. If the user's request is unclear or incomplete, ask politely for more details.
        4. Use only the tables and columns listed in the schema above.
        5. Use SQL Server syntax (T-SQL) for all queries.
        6. Optimize the query for performance and clarity.
        7. If the request involves data from different tables, use proper JOINs:
            - Use **INNER JOIN** when data must exist in both tables to match.
            - Use **LEFT JOIN** when you want to include all rows from the primary table and optionally matching rows from the other.
            - Join conditions must be accurate and based on related keys (e.g., `user_id`, `project_id`).
        8. Include WHERE clauses to filter data accurately.
        9. Use IS NULL / IS NOT NULL to handle NULL values.
        10. Use aliases (e.g., `u` for `users`) for better readability.
        11. Add ORDER BY clauses when relevant.
        12. Use GETDATE(), CONVERT(), or CAST(... AS DATE) for date/time filtering.
        13. If the user asks for a "report", generate a SELECT query that returns all relevant data with proper sorting.
        14. For report queries, include pagination using OFFSET-FETCH to return 50 rows at a time. Assume default values: `page = 1`, `page_size = 50`, unless specified otherwise.
        15. If the user specifies a specific time in the future for delivery (e.g., "at 10 PM", "tomorrow", "every Friday"), and also includes a time filter for the data (e.g., "yesterday", "last 7 days"), treat the query as a **scheduled report**, and:
            - Use only the date/time filters for the data (not the scheduled time).
            - Return a schedule object that includes when to run the query (but do not include this in the WHERE clause).
        16. If you are unsure what the user means, or the question is too vague, respond with a friendly explanation asking for more details.
        17. Always respond strictly in the following JSON format and nothing else:
        18. If the user requests a report or data related to a concept (like "sales") that is not in the schema, do not generate any SQL. Instead, respond with a helpful explanation and set `"sql_query"` to null.

        {{
            "sql_query": "...",
            "explanation": "...",
            "required_parameters": []
        }}
        """
