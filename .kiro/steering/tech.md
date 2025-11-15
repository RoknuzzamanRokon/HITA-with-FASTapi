---
inclusion: always
---

# Technology Stack

## Framework & Runtime

- **Framework**: FastAPI (Python web framework)
- **Python Version**: 3.12
- **ASGI Server**: Uvicorn
- **Package Manager**: Pipenv

## Database

- **ORM**: SQLAlchemy
- **Database**: SQLite (development), MySQL/MariaDB (production via PyMySQL)
- **Migrations**: Alembic
- **Connection Pooling**: Configured with pool_size=5, max_overflow=10, pool_recycle=3600

## Authentication & Security

- **JWT**: python-jose with cryptography
- **Password Hashing**: Passlib with bcrypt (version 3.2.2)
- **Token Storage**: Redis for blacklisting and session management
- **Input Sanitization**: bleach library
- **Validation**: Pydantic with email-validator

## Caching

- **Cache Backend**: Redis (via fastapi-cache2)
- **Cache Prefix**: "fastapi-cache"
- **Connection**: redis.asyncio (aioredis)

## Key Libraries

- **HTTP Client**: httpx, aiohttp, requests
- **Data Processing**: pandas
- **XML Parsing**: xmltodict
- **Fuzzy Matching**: rapidfuzz (for ML mapping)
- **Image Processing**: Pillow
- **System Monitoring**: psutil
- **Schema Validation**: jsonschema

## Common Commands

### Development

```bash
# Install dependencies
pipenv install

# Activate virtual environment
pipenv shell

# Run development server
uvicorn main:app --reload

# Run on specific port
uvicorn main:app --host 0.0.0.0 --port 8000
```

### Database

```bash
# Run migrations
alembic upgrade head

# Create new migration
alembic revision --autogenerate -m "description"

# Run custom migration scripts
python migrations/add_security_tables.py
python migrations/add_user_indexes.py
```

### Testing

```bash
# Run tests
pytest

# Run with coverage
pytest --cov

# Run specific test file
pytest test_all_suppliers_feature.py
```

### Utilities

```bash
# Create super user
python utils/create_super_user.py

# Update user roles
python utils/update_user_roles.py

# Run mapping operations
python run_mapping.py

# Performance optimization
python run_performance_fix.py
```

## Environment Configuration

Required environment variables in `.env`:

- `DB_CONNECTION`: Database connection string
- `SECRET_KEY`: JWT secret key for token signing
- Redis connection (default: localhost:6379)

## API Documentation

- **Swagger UI**: Available at `/docs` (custom styled)
- **OpenAPI Schema**: Custom implementation in `custom_openapi.py`
- **Postman Collection**: Available in `postManColection/` directory
