import os
from typing import Dict, List, Optional
import google.generativeai as genai
from app.utils.schema_extractor import SchemaExtractor
import json
import re

class QueryBuilder:
    def __init__(self):
        # Configure the Gemini API
        genai.configure(api_key=os.getenv('GOOGLE_API_KEY'))
        # Use Gemini 1.5 Flash model
        self.model = genai.GenerativeModel('gemini-1.5-pro-latest')
        self.schema_extractor = SchemaExtractor()
        
    def get_relevant_schemas(self, query: str, k: int = 3) -> List[Dict]:
        """Get relevant schema information for the query."""
        return self.schema_extractor.search_schemas(query, k=k)
    
    def build_query(self, user_query: str) -> Dict:
        """Build a SQL query from natural language input."""
        # First, get relevant schema information
        relevant_schemas = self.get_relevant_schemas(user_query)
        print(relevant_schemas)
        # Create a context string from the schemas
        schema_context = "\n\n".join([
            f"Table Schema:\n{result['content']}"
            for result in relevant_schemas
        ])
        print(schema_context)
        # Create the prompt
        prompt = f"""
You are an expert SQL query builder. Your task is to create a SQL query based on the user's request and the available database schema information.

Database Schema Information:
{schema_context}

User Request: {user_query}

Important Rules:
1. Use only the tables and columns shown in the schema information
2. Make sure the query is optimized and follows SQL best practices
3. Use appropriate JOINs when needed
4. Include WHERE clauses to filter data appropriately
5. Handle NULL values
6. Use aliases for better readability
7. Include ORDER BY when relevant

Respond ONLY in the following JSON format, without any extra text:

{{
  "sql_query": "...",
  "explanation": "...",
  "required_parameters": ["..."]
}}
"""

        print(prompt)
        # Generate the response
        response = self.model.generate_content(prompt)
        print(response)
        try:
            # Step 1: Get and print raw response
            raw_response = response.text.strip()
            print("Raw response from Gemini:\n", raw_response)

            # Step 2: Clean out triple-backtick blocks like ```json or ```
            raw_response = re.sub(r"^```(?:json)?|```$", "", raw_response, flags=re.IGNORECASE).strip()

            # Step 3: Attempt to parse cleaned JSON
            result = json.loads(raw_response)

        except (json.JSONDecodeError, AttributeError) as e:
            print("❌ JSON parsing error:", e)
            print("❌ Final raw response that caused the issue:\n", raw_response)

            # Safe fallback
            result = {
                "sql_query": "SELECT 1",
                "explanation": "Error: Could not generate valid query",
                "required_parameters": []
            }

        # Step 4: Return the cleaned-up structure
        return {
            'sql_query': result.get('sql_query', "SELECT 1"),
            'explanation': result.get('explanation', "Could not explain due to error."),
            'required_parameters': result.get('required_parameters', [])
            # 'relevant_schemas': [
            #     {
            #         'content': schema['content'],
            #         'schema_info': schema['schema_metadata'],
            #         'similarity': schema['similarity']
            #     }
            #     for schema in relevant_schemas
            # ]
        }
    
    def execute_query(self, query: str, parameters: Optional[Dict] = None) -> List[Dict]:
        """Execute the SQL query and return results."""
        with self.schema_extractor.engine.connect() as conn:
            if parameters:
                result = conn.execute(query, parameters)
            else:
                result = conn.execute(query)
            
            # Convert result to list of dictionaries
            columns = result.keys()
            return [dict(zip(columns, row)) for row in result.fetchall()]
