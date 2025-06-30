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

### Provider Mappings

- `POST /v1.0/hotels/mapping/add_provider`: Add a provider mapping to a hotel.
- `POST /v1.0/hotels/mapping/add_provider_all_details_with_ittid`: Add a provider mapping for an existing hotel, including all required details.
    - **Request Body Example:**
        ```json
        {
          "ittid": "HOTEL12345",
          "provider_name": "hotelbeds",
          "provider_id": "HB123",
          "vervotech_id": "VERV123",
          "giata_code": "GIATA456"
        }
        ```
    - **Authorization:** Requires `super_user` or `admin_user` role.
    - **Behavior:** Will skip creation if the mapping exists and return a message.
- `DELETE /v1.0/hotels/delete_hotel_by_ittid/{ittid}`: Delete a hotel and all related information by ittid. (Only SUPER_USER)
- `DELETE /v1.0/hotels/delete_a_hotel_mapping?provider_name={provider}&provider_id={id}`: Delete a specific provider mapping for a hotel. (Only SUPER_USER)
- `GET /v1.0/hotels/get_supplier_info?supplier={supplier}`: Get total hotel count for a supplier (super_user and admin_user only).

### Users

- `GET /v1.0/users`: Retrieve a list of users.
- `GET /v1.0/users/{user_id}`: Retrieve details of a specific user.
- `POST /v1.0/users`: Create a new user.
- `PUT /v1.0/users/{user_id}`: Update an existing user.
- `DELETE /v1.0/users/{user_id}`: Delete a user.
- `GET /v1.0/users/super/check/all`: Get details of all users created by the current super_user, including super users.

### Demo

- `POST /v1.0/hotels/demo/input`: Create a new demo hotel.
- `GET /v1.0/hotels/demo/getAll`: List demo hotels.
- `GET /v1.0/hotels/demo/getAHotel/{hotel_id}`: Get a specific demo hotel by ID.

---

**Note:** Many endpoints require authentication (JWT Bearer token). Some operations are restricted to users with specific roles (e.g., super_user, admin_user). See code for additional details and authorization logic.

For more details and updates, refer to the [source code](https://github.com/RoknuzzamanRokon/HITA-with-FASTapi) or open an issue if you need further clarification.


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

## API Examples

### Create a new hotel with all related details

**Endpoint:** `POST /v1.0/hotels/mapping/input_hotel_all_details`

**Request Body:**

```json
{
  "name": "Example Hotel",
  "address_line1": "123 Main St",
  "address_line2": "Apt 4",
  "latitude": 34.0522,
  "longitude": -118.2437,
  "postal_code": "90001",
  "property_type": "Hotel",
  "rating": 4,
  "map_status": "Mapped",
  "content_update_status": "Updated",
  "locations": [
    {
      "city_name": "Los Angeles",
      "city_location_id": "LA123",
      "city_code": "LAX",
      "master_city_name": "Los Angeles",
      "state_name": "California",
      "state_code": "CA",
      "country_name": "United States",
      "country_code": "US"
    }
  ],
  "provider_mappings": [
    {
      "provider_id": "Provider123",
      "provider_name": "ExampleProvider",
      "system_type": "SystemType",
      "vervotech_id": "Vervo123",
      "giata_code": "Giata123"
    }
  ],
  "contacts": [
    {
      "contact_type": "Phone",
      "value": "555-123-4567"
    }
  ],
  "chains": [
    {
      "chain_code": "Chain123",
      "chain_name": "Example Chain"
    }
  ]
}
```

**Response:**

```json
{
  "id": 1,
  "ittid": "unique_hotel_id",
  "name": "Example Hotel",
  "address_line1": "123 Main St",
  "address_line2": "Apt 4",
  "latitude": 34.0522,
  "longitude": -118.2437,
  "postal_code": "90001",
  "property_type": "Hotel",
  "rating": 4,
  "map_status": "Mapped",
  "content_update_status": "Updated",
  "updated_at": "2024-01-01T00:00:00",
  "created_at": "2024-01-01T00:00:00"
}
```

### Get hotel data by provider name and ID

**Endpoint:** `POST /v1.0/content/get_hotel_data_provider_name_and_id`

**Request Body:**

```json
{
  "provider_hotel_identity": [
    {
      "provider_id": "Provider123",
      "provider_name": "ExampleProvider"
    }
  ]
}
```

**Response:**

```json
[
  {
    "hotel": {
      "id": 1,
      "ittid": "unique_hotel_id",
      "latitude": 34.0522,
      "longitude": -118.2437,
      "address_line1": "123 Main St",
      "address_line2": "Apt 4",
      "postal_code": "90001",
      "property_type": "Hotel",
      "name": "Example Hotel",
      "rating": 4,
      "map_status": "Mapped",
      "content_update_status": "Updated",
      "updated_at": "2024-01-01T00:00:00",
      "created_at": "2024-01-01T00:00:00"
    },
    "provider_mappings": [
      {
        "id": 1,
        "provider_id": "Provider123",
        "provider_name": "ExampleProvider",
        "system_type": "SystemType",
        "vervotech_id": "Vervo123",
        "giata_code": "Giata123"
      }
    ],
    "locations": [
      {
        "id": 1,
        "city_name": "Los Angeles",
        "city_location_id": "LA123",
        "city_code": "LAX",
        "master_city_name": "Los Angeles",
        "state_name": "California",
        "state_code": "CA",
        "country_name": "United States",
        "country_code": "US"
      }
    ],
    "contacts": [
      {
        "id": 1,
        "contact_type": "Phone",
        "value": "555-123-4567"
      }
    ]
  }
]











# API Routes Overview

This document summarizes the route files in the `routes/` folder, along with their main endpoints and responsibilities. Use this as a reference for updating the `README.md` or understanding the available API structure.


---

## 1. `routes/auth.py` – **Authentication**
- **POST `/v1.0/auth/token`**: Log in and obtain a JWT access token.
- **POST `/v1.0/auth/register`**: Register a new user.
- **Handles**: User login, registration, and token issuance.

---

## 2. `routes/contents.py` – **Hotel Content APIs**
- **POST `/v1.0/content/get_hotel_data_provider_name_and_id`**: Get hotel data by provider name & ID.
- **POST `/v1.0/content/get_hotel_mapping_data_using_provider_name_and_id`**: Get hotel mapping data by provider.
- **POST `/v1.0/content/get_hotel_with_ittid`**: Get hotels and their mappings by a list of ITTIDs.
- **GET `/v1.0/content/get_hotel_with_ittid/{ittid}`**: Get hotel (and mappings) by ITTID.
- **GET `/v1.0/content/get_all_hotel_info`**: Paginated list of all hotels accessible to the user.
- **GET `/v1.0/content/get_all_hotel_only_supplier/`**: List all hotels for a supplier (with pagination).
- **GET `/v1.0/content/get_update_provider_info`**: Get provider mapping updates within a date range.
- **Handles**: Listing, filtering, and retrieving hotel content, locations, contacts, and provider mappings, with permission checks.

---

## 3. `routes/delete.py` – **Delete Operations**
- **DELETE `/v1.0/delete/delete_user/{user_id}`**: Delete a user (super_user only).
- **DELETE `/v1.0/delete/delete_super_user/{user_id}`**: Delete a super user (super_user only).
- **DELETE `/v1.0/delete/delete_hotel_by_ittid/{ittid}`**: Delete a hotel and related data (super_user only).
- **DELETE `/v1.0/delete/delete_a_hotel_mapping`**: Delete a specific provider mapping (super_user only).
- **Handles**: Deletion of users, hotels, and provider mappings.

---

## 4. `routes/hotelIntegration.py` – **Hotel Integrations & Provider Mapping**
- **POST `/v1.0/hotels/mapping/input_hotel_all_details`**: Create a new hotel with all details (super_user/admin_user).
- **POST `/v1.0/hotels/mapping/add_provider_all_details_with_ittid`**: Add provider mapping for an existing hotel, skip if exists.
- **GET `/v1.0/hotels/get_supplier_info`**: Get total hotel count for a supplier (super_user/admin_user).
- **Handles**: Creating hotels, adding provider mappings, supplier info statistics.

---

## 5. `routes/hotelsDemo.py` – **Demo Hotels**
- **POST `/v1.0/hotels/demo/input`**: Create a demo hotel.
- **GET `/v1.0/hotels/demo/getAll`**: List demo hotels.
- **GET `/v1.0/hotels/demo/getAHotel/{hotel_id}`**: Get a specific demo hotel by ID.
- **Handles**: Demo data endpoints for hotels.

---

## 6. `routes/mapping.py` – **Advanced Hotel Mapping**
- **POST `/v1.0/mapping/add_rate_type_with_ittid_and_pid`**: Add/update provider mapping and rate type info for a hotel.
- **PUT `/v1.0/mapping/update_rate_type`**: Update a rate type for a provider mapping.
- **GET `/v1.0/mapping/get_basic_mapping_with_info`**: Get basic mapping info, filterable by supplier and country.
- **Handles**: Advanced management of provider mappings, rate types, and country/supplier filterable exports.

---

## 7. `routes/permissions.py` – **User Permissions**
- **POST `/v1.0/permissions/active_supplier`**: Grant provider permissions to general users (super_user/admin_user).
- **Handles**: Assigning supplier/provider permissions to general users.

---

## 8. `routes/usersIntegrations.py` – **User Management & Points**
- **GET `/v1.0/user/me`**: Get current user details (with points & active suppliers).
- **POST `/v1.0/user/create_super_user`**: Create a super user (super_user only).
- **POST `/v1.0/user/create_admin_user`**: Create an admin user (super_user only).
- **POST `/v1.0/user/create_general_user`**: Create a general user (super_user/admin_user).
- **POST `/v1.0/user/points/give`**: Give points to another user.
- **GET `/v1.0/user/points/check/me`**: Get current user point details.
- **GET `/v1.0/user/super/check/all`**: Get all users created by a super_user.
- **GET `/v1.0/user/active_my_supplier`**: List active suppliers for the user.
- **GET `/v1.0/user/get_list_of_available_suppliers`**: List all unique suppliers in the system.
- **Handles**: User CRUD, role management, points allocation, supplier assignment, and user statistics.

---
