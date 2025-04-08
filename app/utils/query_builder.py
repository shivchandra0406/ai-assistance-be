import os
from typing import Dict, List, Optional
import google.generativeai as genai
from langchain_community.vectorstores import FAISS
from langchain_community.embeddings import HuggingFaceEmbeddings
from app.utils.schema_extractor import SchemaExtractor
import json
import re
from dotenv import load_dotenv

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
            print("Texts:", texts)
            print("Metadata:", metadata)
            
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
            
            # Create the prompt
            prompt = f"""You are an expert SQL Server query builder. Your task is to generate a SQL query based on the user's request and the provided database schema.

            Database Schema:
            {schema_context}

            User Request:
            {user_query}

            Guidelines:
            1. Use only the tables and columns listed in the schema above.
            2. Use SQL Server syntax (T-SQL) for all queries.
            3. Optimize the query for performance and clarity.
            4. Use proper JOINs (INNER JOIN, LEFT JOIN, etc.) when multiple tables are involved.
            5. Include WHERE clauses to filter data accurately.
            6. Use IS NULL / IS NOT NULL to handle NULL values.
            7. Use aliases (e.g., `u` for `users`) for better readability.
            8. Add ORDER BY clauses when relevant.
            9. Use `GETDATE()` or `CAST(... AS DATE)` for date-related filters.
            10. Avoid using unsupported SQL constructs for SQL Server.

            Return your response **strictly in the following JSON format**, without any extra commentary:
            {{
            "sql_query": "...",
            "explanation": "...",
            "required_parameters": []
            }}"""
            print("Prompt:", prompt)

            print("Sending request to Gemini...")
            # Generate the response using Gemini
            response = self.model.generate_content(prompt)
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
    
    def execute_query(self, query: str, parameters: Optional[Dict] = None) -> List[Dict]:
        """Execute the SQL query and return results."""
        try:
            with self.schema_extractor.engine.connect() as conn:
                if parameters:
                    result = conn.execute(query, parameters)
                else:
                    result = conn.execute(query)
                
                # Convert result to list of dictionaries
                columns = result.keys()
                return [dict(zip(columns, row)) for row in result.fetchall()]
        except Exception as e:
            print("Error executing query:", str(e))
            return []
