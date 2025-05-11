# Hotel API

## Overview

The Hotel API is a FastAPI-based application designed to manage hotels, users, and related entities. It provides endpoints for authentication, hotel management, and provider mappings. The application uses SQLAlchemy for database interactions and Alembic for migrations.

## Features

- User authentication and role-based access control.
- Hotel management with support for related entities like locations, provider mappings, and contacts.
- Database migrations using Alembic.
- Token-based authentication with JWT.

## Project Structure

```
.
├── alembic/                # Alembic migrations
├── routes/                 # API route definitions
├── static/                 # Static assets
├── utils/                  # Utility scripts and helpers
├── models.py               # SQLAlchemy models
├── schemas.py              # Pydantic schemas
├── database.py             # Database connection setup
├── main.py                 # Application entry point
├── README.md               # Project documentation
```

## Installation

1. Clone the repository:

   ```bash
   git clone <repository-url>
   cd hotel_api
   ```

2. Install dependencies:

   ```bash
   pipenv install
   ```

3. Activate the virtual environment:

   ```bash
   pipenv shell
   ```

4. Apply database migrations:
   ```bash
   alembic upgrade head
   ```

## Running the Application

Start the FastAPI application:

```bash
uvicorn main:app --reload
```

The application will be available at `http://127.0.0.1:8000`.

## API Endpoints

### Authentication

- `POST /v1.0/auth/token`: Login and get an access token.
- `POST /v1.0/auth/register`: Register a new user.

### Hotels

- `GET /v1.0/hotels`: Retrieve a list of hotels.
- `GET /v1.0/hotels/{hotel_id}`: Retrieve details of a specific hotel.
- `POST /v1.0/hotels`: Create a new hotel.
- `PUT /v1.0/hotels/{hotel_id}`: Update an existing hotel.
- `DELETE /v1.0/hotels/{hotel_id}`: Delete a hotel.
- `POST /v1.0/hotels/mapping/add_provider`: Add a provider mapping to a hotel.


### Users

- `GET /v1.0/users`: Retrieve a list of users.
- `GET /v1.0/users/{user_id}`: Retrieve details of a specific user.
- `POST /v1.0/users`: Create a new user.
- `PUT /v1.0/users/{user_id}`: Update an existing user.
- `DELETE /v1.0/users/{user_id}`: Delete a user.

## Database Migrations

To create a new migration:

```bash
alembic revision --autogenerate -m "Migration message"
```

To apply migrations:

```bash
alembic upgrade head
```

## Troubleshooting

### Common Issues

- **Enum Value Mismatch**: Ensure the database schema matches the application models.
- **Import Errors**: Run scripts from the project root or adjust the Python path.

### Debugging

Use the `--reload` flag with `uvicorn` to enable live reloading during development.

## License

This project is licensed under the MIT License.
