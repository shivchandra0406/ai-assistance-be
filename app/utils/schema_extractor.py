import os
from typing import List, Dict
from sentence_transformers import SentenceTransformer
from sqlalchemy import create_engine, MetaData, inspect, Table, Column, String, Float, JSON
from sqlalchemy.orm import declarative_base
import numpy as np
import json

Base = declarative_base()

class SchemaEmbedding(Base):
    __tablename__ = 'schema_embeddings'
    
    table_name = Column(String, primary_key=True)
    content = Column(String)
    embedding = Column(JSON)
    schema_metadata = Column(JSON)  

class SchemaExtractor:
    def __init__(self):
        self.engine = create_engine(os.getenv('SQL_SERVER_CONNECTION'))
        self.meta = MetaData()  
        self.inspector = inspect(self.engine)
        
        # Initialize the embedding model
        self.model = SentenceTransformer('all-MiniLM-L6-v2')
        
        # Create SQLite database for storing embeddings
        self.vector_engine = create_engine('sqlite:///schema_vectors.db')
        Base.metadata.create_all(self.vector_engine)
    
    def get_table_schema(self, table_name: str) -> Dict:
        """Get schema information for a specific table."""
        columns = self.inspector.get_columns(table_name)
        pk = self.inspector.get_pk_constraint(table_name)
        fk = self.inspector.get_foreign_keys(table_name)
        
        schema_info = {
            'table_name': table_name,
            'columns': [
                {
                    'name': col['name'],
                    'type': str(col['type']),
                    'nullable': col['nullable']
                } for col in columns
            ],
            'primary_key': pk['constrained_columns'] if pk else [],
            'foreign_keys': [
                {
                    'referred_table': fk_['referred_table'],
                    'referred_columns': fk_['referred_columns'],
                    'constrained_columns': fk_['constrained_columns']
                } for fk_ in fk
            ]
        }
        return schema_info
    
    def get_all_schemas(self) -> List[Dict]:
        """Get schema information for all tables."""
        tables = self.inspector.get_table_names()
        return [self.get_table_schema(table) for table in tables]
    
    def create_schema_documents(self, schemas: List[Dict]) -> List[Dict]:
        """Convert schema information into documents."""
        documents = []
        for schema in schemas:
            # Create a detailed text description of the schema
            content = f"Table: {schema['table_name']}\n\n"
            content += "Columns:\n"
            for col in schema['columns']:
                nullable = "NULL" if col['nullable'] else "NOT NULL"
                content += f"- {col['name']} ({col['type']}) {nullable}\n"
            
            if schema['primary_key']:
                content += f"\nPrimary Key: {', '.join(schema['primary_key'])}\n"
            
            if schema['foreign_keys']:
                content += "\nForeign Keys:\n"
                for fk in schema['foreign_keys']:
                    content += f"- {', '.join(fk['constrained_columns'])} -> {fk['referred_table']}({', '.join(fk['referred_columns'])})\n"
            
            documents.append({
                'table_name': schema['table_name'],
                'content': content,
                'schema_metadata': schema  
            })
        return documents
    
    def store_schemas_in_vectordb(self):
        """Extract schemas and store them with embeddings."""
        print("Extracting schemas...")
        schemas = self.get_all_schemas()
        print("Creating documents...")
        documents = self.create_schema_documents(schemas)
        print(f"Processing {len(documents)} documents...")
        
        with self.vector_engine.connect() as conn:
            # First, delete existing records
            conn.execute(SchemaEmbedding.__table__.delete())
            conn.commit()
            
            for doc in documents:
                # Generate embedding
                embedding = self.model.encode(doc['content']).tolist()
                
                # Store in database
                stmt = SchemaEmbedding.__table__.insert().values(
                    table_name=doc['table_name'],
                    content=doc['content'],
                    embedding=json.dumps(embedding),
                    schema_metadata=json.dumps(doc['schema_metadata'])  
                )
                conn.execute(stmt)
                conn.commit()
        
        return len(documents)
    
    def search_schemas(self, query: str, k: int = 3) -> List[Dict]:
        """Search for relevant schema information."""
        # Generate query embedding
        query_embedding = self.model.encode(query)
        
        # Get all embeddings from database
        with self.vector_engine.connect() as conn:
            results = conn.execute(SchemaEmbedding.__table__.select()).fetchall()
        
        # Calculate similarities
        similarities = []
        for result in results:
            embedding = np.array(json.loads(result.embedding))
            similarity = np.dot(query_embedding, embedding) / (np.linalg.norm(query_embedding) * np.linalg.norm(embedding))
            similarities.append((similarity, result))
        
        # Sort by similarity and return top k
        similarities.sort(key=lambda x: x[0], reverse=True)
        return [
            {
                'content': result.content,
                'schema_metadata': json.loads(result.schema_metadata),  
                'similarity': float(sim)
            }
            for sim, result in similarities[:k]
        ]