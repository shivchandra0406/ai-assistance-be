# Flask API Project

A Flask API project with SQL Server integration and proper project structure.

## Project Structure
```
app/
├── __init__.py          # Flask application factory
├── config.py            # Configuration settings
├── main.py             # Application entry point
├── api/                # API routes and views
│   ├── __init__.py
│   └── routes.py
├── models/             # Database models
│   ├── __init__.py
│   └── user.py
└── schemas/           # Marshmallow schemas for serialization
    ├── __init__.py
    └── user.py
```

## Setup Instructions

1. Create a virtual environment:
```bash
python -m venv venv
```

2. Activate the virtual environment:
- Windows:
```bash
venv\Scripts\activate
```
- Unix/MacOS:
```bash
source venv/bin/activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Set up environment variables in `.env`:
```
FLASK_APP=app.main
FLASK_ENV=development
SECRET_KEY=your-secret-key
SQL_SERVER_CONNECTION=your-connection-string
```

5. Initialize the database:
```bash
flask db init
flask db migrate
flask db upgrade
```

6. Run the application:
```bash
flask run
```

## API Endpoints

- `GET /health` - Health check endpoint
- `GET /api/v1/users` - Get all users
- `POST /api/v1/users` - Create a new user
- `GET /api/v1/users/<id>` - Get a specific user
- `PUT /api/v1/users/<id>` - Update a user
- `DELETE /api/v1/users/<id>` - Delete a user
