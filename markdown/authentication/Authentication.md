# Authentication API Documentation

## Overview

This document provides comprehensive information about the authentication system for the ITT Hotel API (HITA). The authentication system supports JWT-based token authentication with role-based access control.

## Base URL

```
{{host}}/v1.0/auth/
```

## Authentication Endpoints

### 1. User Registration

**Endpoint:** `POST /v1.0/auth/register/`

Register a new user in the system.

**Request Body:**

```json
{
  "username": "alif1234",
  "email": "alif1234@gmail.com",
  "password": "alif1234"
}
```

**Headers:**

```
Content-Type: application/json
```

---

### 2. User Login

**Endpoint:** `POST /v1.0/auth/token/`

Authenticate user and receive access tokens.

**Request Body (Form Data):**

```
username: roman
password: roman123
```

**Response:**
Returns JWT access token and refresh token.

**Available Test Users:**

- **Super User:** `ursamroko` / `ursamroko123`
- **Admin User:** `ron123` / `ron123`
- **General User:** `roman` / `roman123`
- **Super User:** `rokon` / `rokon123`

**Auto-Token Storage:**
The login endpoint includes a test script that automatically saves the access token to the environment variable `token` for subsequent requests.

---

### 3. Health Check

**Endpoint:** `GET /v1.0/auth/health/`

Check the health status of the authentication service.

**Headers:**

```
Content-Type: application/json
Authorization: Bearer {{token}}
```

---

### 4. User Profile

**Endpoint:** `GET /v1.0/user/me/`

Get current authenticated user information.

**Headers:**

```
Content-Type: application/json
Authorization: Bearer {{token}}
```

---

### 5. Token Refresh

**Endpoint:** `POST /v1.0/auth/refresh/`

Refresh the access token using a valid refresh token.

**Request Body:**

```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

**Headers:**

```
Content-Type: application/json
Authorization: Bearer {{token}}
```

---

### 6. API Key Regeneration

**Endpoint:** `POST /v1.0/auth/regenerate_api_key/`

Generate a new API key for the authenticated user.

**Headers:**

```
Content-Type: application/json
Authorization: Bearer {{token}}
```

---

### 7. Logout

**Endpoint:** `POST /v1.0/auth/logout/`

Logout from the current session.

**Headers:**

```
Content-Type: application/json
Authorization: Bearer {{token}}
```

---

### 8. Logout from All Sessions

**Endpoint:** `POST /v1.0/auth/logout_all/`

Logout from all active sessions across all devices.

**Headers:**

```
Content-Type: application/json
Authorization: Bearer {{token}}
```

## User Management Endpoints

### Create Super User

**Endpoint:** `POST /v1.0/user/create_super_user/`

Create a new super admin user (requires super admin privileges).

**Request Body:**

```json
{
  "username": "roman123",
  "email": "roman123@gmail.com",
  "password": "roman123"
}
```

### Create Admin User

**Endpoint:** `POST /v1.0/user/create_admin_user/`

Create a new admin user (requires super admin privileges).

**Request Body:**

```json
{
  "username": "salauddin123",
  "email": "salauddin123@gmail.com",
  "business_id": "salauddin123",
  "password": "salauddin123"
}
```

### Create General User

**Endpoint:** `POST /v1.0/user/create_general_user/`

Create a new general user (requires admin privileges).

**Request Body:**

```json
{
  "username": "salauddin123",
  "email": "salauddin123@gmail.com",
  "password": "salauddin123"
}
```

## Authentication Flow

1. **Registration:** Create a new user account using `/auth/register/`
2. **Login:** Authenticate with credentials to receive JWT tokens via `/auth/token/`
3. **Access Protected Resources:** Include the Bearer token in the Authorization header
4. **Token Refresh:** Use the refresh token to get new access tokens when they expire
5. **Logout:** Invalidate tokens using `/auth/logout/` or `/auth/logout_all/`

## User Roles

The system supports three user roles:

- **Super User:** Full system access, can create admin users
- **Admin User:** Can manage general users and access admin features
- **General User:** Standard user access to hotel content and search features

## Security Notes

- All protected endpoints require a valid JWT token in the Authorization header
- Tokens have expiration times and should be refreshed as needed
- Use HTTPS in production environments
- Store tokens securely on the client side
- Implement proper token rotation and logout mechanisms

## Environment Variables

The Postman collection uses the following environment variables:

- `{{host}}` - Base API URL
- `{{token}}` - JWT access token (auto-populated after login)

## Error Handling

The API returns appropriate HTTP status codes:

- `200` - Success
- `401` - Unauthorized (invalid or expired token)
- `403` - Forbidden (insufficient permissions)
- `422` - Validation errors
- `500` - Internal server error

## Testing

Use the provided Postman collection to test all authentication endpoints. The collection includes pre-configured test users and automatic token management for seamless testing.
