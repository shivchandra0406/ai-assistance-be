# AI-Assisted SQL Query Builder

A Flask-based API that uses AI to generate SQL queries from natural language input. The application leverages Google's Gemini model for query generation and provides a vector database for efficient schema retrieval.

## Features

- Natural language to SQL query conversion
- Database schema extraction and storage
- Vector-based schema search
- RESTful API endpoints
- Support for SQL Server
- AI-powered query generation using Google's Gemini model

## Tech Stack

- Python 3.8+
- Flask
- SQLAlchemy
- Google Gemini AI
- SQL Server
- FAISS (Vector Database)
- SQLite (for schema storage)

## Prerequisites

- Python 3.8 or higher
- SQL Server
- SQL Server ODBC Driver
- Git

## Installation

1. Clone the repository:
```bash
git clone https://github.com/shivchandra0406/ai-assistance-be.git
cd ai-assistance-be
```

2. Create a virtual environment:
```bash
python -m venv venv
```

3. Activate the virtual environment:
- Windows:
```bash
venv\Scripts\activate
```
- Unix/MacOS:
```bash
source venv/bin/activate
```

4. Install dependencies:
```bash
pip install -r requirements.txt
```

5. Set up environment variables in `.env`:
```plaintext
FLASK_APP=app.main
FLASK_ENV=development
FLASK_DEBUG=1
SECRET_KEY=your-secret-key-here
SQL_SERVER_CONNECTION=mssql+pyodbc://SERVER/DATABASE?driver=ODBC+Driver+17+for+SQL+Server&trusted_connection=yes&encrypt=no&TrustServerCertificate=yes
GOOGLE_API_KEY=your-google-api-key
```

## Database Setup

1. Initialize the database:
```bash
flask db upgrade
```

2. Extract schemas (after setting up the environment):
```bash
curl -X POST http://localhost:5000/api/schema/schemas/extract
```

## API Endpoints

### Schema Management
- `POST /api/schema/schemas/extract` - Extract and store database schemas
- `POST /api/schema/schemas/search` - Search for relevant schemas

### Query Building
- `POST /api/schema/query/build` - Build SQL query from natural language
- `POST /api/schema/query/execute` - Execute a generated SQL query

## Example Usage

1. Build a query:
```bash
curl --location --request POST 'http://127.0.0.1:5000/api/schema/query/build' \
--header 'Content-Type: application/json' \
--data-raw '{
    "query": "Show me all users in the system"
}'
```

2. Execute a query:
```bash
curl --location --request POST 'http://127.0.0.1:5000/api/schema/query/execute' \
--header 'Content-Type: application/json' \
--data-raw '{
    "query": "SELECT * FROM users",
    "parameters": {}
}'
```

## Development

1. Create a new branch:
```bash
git checkout -b feature/your-feature-name
```

2. Make your changes and commit:
```bash
git add .
git commit -m "Description of changes"
```

3. Push changes:
```bash
git push origin feature/your-feature-name
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details.
