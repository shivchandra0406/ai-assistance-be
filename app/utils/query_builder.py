import os
from typing import Dict, List, Optional, Tuple
import google.generativeai as genai
from langchain_community.vectorstores import FAISS
from langchain_community.embeddings import HuggingFaceEmbeddings
from app.utils.schema_extractor import SchemaExtractor
from app.utils.prompt_manager import PromptManager
from app.utils.timeout_utils import execute_with_timeout
import json
import re
from dotenv import load_dotenv
from sqlalchemy import text

# Load environment variables
load_dotenv()

class QueryBuilder:
    def __init__(self):
        # Initialize Gemini model
        api_key = os.environ.get('GOOGLE_API_KEY')
        print("Environment variables:", {k: v for k, v in os.environ.items() if 'API' in k.upper()})
        print("API Key available:", bool(api_key))
        if not api_key:
            raise ValueError("Google API Key is not set")
        
        # Configure Gemini
        genai.configure(api_key=api_key)
        
        # Set up the model configuration
        generation_config = {
            "temperature": 0.1,
            "top_p": 1,
            "top_k": 1,
            "max_output_tokens": 2048,
        }
        
        safety_settings = [
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
        ]
        
        self.model = genai.GenerativeModel(
            model_name='gemini-1.5-pro-latest',
            generation_config=generation_config,
            safety_settings=safety_settings
        )
        
        # Initialize embeddings model
        self.embeddings = HuggingFaceEmbeddings(
            model_name="sentence-transformers/all-mpnet-base-v2"
        )
        self.schema_extractor = SchemaExtractor()
        
        # Store schemas in vector database
        print("Storing schemas in vector database...")
        self.schema_extractor.store_schemas_in_vectordb()
        
        self.vector_store = None
        self._initialize_vector_store()
    
    def _initialize_vector_store(self):
        """Initialize FAISS vector store with schema information"""
        try:
            # Get all available schemas
            schemas = self.schema_extractor.get_all_schemas()
            print("Available schemas:", len(schemas))
            
            # Convert schemas to documents
            documents = self.schema_extractor.create_schema_documents(schemas)
            print("Created documents:", len(documents))
            # print("Documents:", documents)
            texts = [doc['content'] for doc in documents]
            metadata = [doc['schema_metadata'] for doc in documents]
            # print("Texts:", texts)
            # print("Metadata:", metadata)
            
            # Create FAISS vector store
            self.vector_store = FAISS.from_texts(
                texts=texts,
                embedding=self.embeddings,
                metadatas=metadata
            )
            print("Vector store initialized successfully")
        except Exception as e:
            print("Error initializing vector store:", str(e))
            raise
    
    def get_relevant_schemas(self, query: str, k: int = 3) -> List[Dict]:
        """Get relevant schema information using vector similarity search."""
        try:
            if not self.vector_store:
                print("Vector store not initialized")
                return []
                
            results = self.vector_store.similarity_search_with_score(query, k=k)
            print(f"Found {len(results)} relevant schemas")
            return [
                {
                    'content': doc.page_content,
                    'schema_metadata': doc.metadata,
                    'similarity': score
                }
                for doc, score in results
            ]
        except Exception as e:
            print("Error in get_relevant_schemas:", str(e))
            return []
    
    def build_query(self, user_query: str) -> Dict:
        """Build a SQL query using Gemini."""
        try:
            # First, get relevant schema information
            print("Processing query:", user_query)
            relevant_schemas = self.get_relevant_schemas(user_query)
            print("Relevant schemas:", len(relevant_schemas))
            
            # Create a context string from the schemas
            schema_context = "\n\n".join([
                f"Table Schema:\n{result['content']}"
                for result in relevant_schemas
            ])
            print("Schema context length:", len(schema_context))
            
            # Get the prompt from PromptManager
            prompt = PromptManager.get_query_generation_prompt(schema_context)
            
            print("Sending request to Gemini...")
            # Generate the response using Gemini
            response = self.model.generate_content(prompt + f"\nUser Request: {user_query}")
            print("Got response from Gemini")
            
            if not response.text:
                raise ValueError("Empty response from Gemini")
            
            raw_response = response.text.strip()
            print("Raw response:", raw_response)
            
            # Clean out triple-backtick blocks
            raw_response = re.sub(r"^```(?:json)?|```$", "", raw_response, flags=re.IGNORECASE).strip()
            print("Cleaned response:", raw_response)
            
            # Parse JSON response
            result = json.loads(raw_response)
            print("Parsed JSON successfully")
            
        except Exception as e:
            print("❌ Error generating query:", str(e))
            print("Error type:", type(e))
            print("Error details:", dir(e))
            result = {
                "sql_query": "SELECT 1",
                "explanation": f"Error: Could not generate valid query. Error: {str(e)}",
                "required_parameters": []
            }

        return {
            'sql_query': result.get('sql_query', "SELECT 1"),
            'explanation': result.get('explanation', "Could not explain due to error."),
            'required_parameters': result.get('required_parameters', [])
        }
    
    def handle_error(self, error_message: str, query: str = None) -> Dict:
        """Handle SQL errors"""
        try:
            # Get the prompt from PromptManager
            prompt = PromptManager.get_error_analysis_prompt(error_message, query)
            
            # Generate analysis
            response = self.model.generate_content(prompt)
            return eval(response.text)
            
        except Exception as e:
            print(f"Error analyzing SQL error: {str(e)}")
            return {
                "error_type": "Unknown",
                "explanation": str(e),
                "solution": "Could not analyze error",
                "corrected_query": query
            }
    
    def execute_query(self, query, parameters=None):
        """Execute the SQL query and return results"""
        try:
            with self.schema_extractor.engine.connect() as conn:
                # Execute the query
                if parameters:
                    result = conn.execute(text(query), parameters)
                else:
                    result = conn.execute(text(query))
                
                # Check if it's a SELECT query
                is_select = query.strip().upper().startswith('SELECT')
                
                if is_select:
                    # For SELECT queries, return the rows as list of dicts
                    try:
                        columns = result.keys()
                        return [dict(zip(columns, row)) for row in result.fetchall()]
                    except Exception as e:
                        print("Error fetching SELECT results:", str(e))
                        return []
                else:
                    # For INSERT/UPDATE/DELETE queries
                    try:
                        conn.commit()  # Commit the transaction
                        return {
                            'success': True,
                            'message': f'Query executed successfully. Rows affected: {result.rowcount}',
                            'rows_affected': result.rowcount
                        }
                    except Exception as e:
                        print("Error in non-SELECT query:", str(e))
                        return {
                            'success': False,
                            'message': f'Error in query: {str(e)}',
                            'rows_affected': 0
                        }
                    
        except Exception as e:
            print("Error executing query:", str(e))
            print("Error type:", type(e))
            return {
                'success': False,
                'message': f'Error executing query: {str(e)}',
                'rows_affected': 0
            }
    
    def execute_query_with_timeout(self, query: str, parameters: dict = None, timeout_seconds: int = 30) -> Tuple[list, bool]:
        """Execute a query with timeout
        
        Args:
            query: SQL query to execute
            parameters: Optional query parameters
            timeout_seconds: Timeout in seconds (default: 30)
            
        Returns:
            Tuple[list, bool]: (results, timed_out)
                - results: Query results or None if timed out
                - timed_out: True if query timed out, False otherwise
        """
        try:
            # Use execute_with_timeout from timeout_utils
            result, timed_out = execute_with_timeout(
                self.execute_query,
                timeout_seconds,
                query,
                parameters
            )
            print("Query executed with timeout:", result, timed_out)
            return result, timed_out
            
        except Exception as e:
            print(f"Error executing query with timeout: {str(e)}")
            raise