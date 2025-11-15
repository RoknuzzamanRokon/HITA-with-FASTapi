---
inclusion: always
---

# Product Overview

HITA (Hotel Integration Technology API) is a hotel aggregation and mapping platform that consolidates hotel data from multiple suppliers/providers into a unified system.

## Core Functionality

- **Hotel Data Aggregation**: Collects and normalizes hotel information from various suppliers (Agoda, Booking, EAN, etc.)
- **Provider Mapping**: Maps hotels across different supplier systems using ITTID (Internal Travel Technology ID) as the universal identifier
- **Location-Based Search**: Geospatial search for hotels within specified radius using lat/lon coordinates
- **Rate Management**: Tracks room rates, rate types, and pricing information across suppliers
- **User Management**: Role-based access control with three tiers (Super User, Admin User, General User)
- **Point System**: Credit-based system for API usage tracking and allocation
- **ML-Assisted Mapping**: Machine learning features for automated hotel matching across suppliers

## Key Business Rules

- **ITTID**: Universal hotel identifier used across all suppliers
- **Supplier Permissions**: General users only access suppliers they have permission for
- **"All" Suppliers**: Special keyword to search all available/permitted suppliers at once
- **API Keys**: Only admin-created users receive API keys; self-registered users don't get API access
- **Point Allocation**: Different packages (admin, yearly, monthly, per-request, guest) control API usage limits

## User Roles

- **Super User**: Full system access, can manage all users and permissions
- **Admin User**: Can create users, manage permissions, access all suppliers
- **General User**: Limited to assigned supplier permissions, cannot create other users
