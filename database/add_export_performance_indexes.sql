-- Performance indexes for export operations
-- This script adds indexes to improve query performance for hotel, mapping, and supplier summary exports
-- MySQL-compatible syntax (handles duplicate index errors gracefully in migration script)
-- Hotels table indexes for export filtering
CREATE INDEX idx_hotels_updated_at ON hotels(updated_at);
CREATE INDEX idx_hotels_created_at ON hotels(created_at);
CREATE INDEX idx_hotels_rating ON hotels(rating);
CREATE INDEX idx_hotels_property_type ON hotels(property_type);
CREATE INDEX idx_hotels_ittid_updated ON hotels(ittid, updated_at);
-- Locations table indexes for country/city filtering
CREATE INDEX idx_locations_country_code ON locations(country_code);
CREATE INDEX idx_locations_ittid_country ON locations(ittid, country_code);
CREATE INDEX idx_locations_city_name ON locations(city_name);
CREATE INDEX idx_locations_state_code ON locations(state_code);
-- Provider mappings table indexes for supplier filtering
CREATE INDEX idx_provider_mappings_provider_name ON provider_mappings(provider_name);
CREATE INDEX idx_provider_mappings_ittid_provider ON provider_mappings(ittid, provider_name);
CREATE INDEX idx_provider_mappings_updated_at ON provider_mappings(updated_at);
CREATE INDEX idx_provider_mappings_created_at ON provider_mappings(created_at);
CREATE INDEX idx_provider_mappings_vervotech ON provider_mappings(vervotech_id);
CREATE INDEX idx_provider_mappings_giata ON provider_mappings(giata_code);
-- Composite indexes for common export query patterns
CREATE INDEX idx_hotels_rating_updated ON hotels(rating, updated_at);
CREATE INDEX idx_provider_mappings_provider_updated ON provider_mappings(provider_name, updated_at);
-- Contacts table indexes for export with contact data
CREATE INDEX idx_contacts_ittid ON contacts(ittid);
CREATE INDEX idx_contacts_type ON contacts(contact_type);
-- Export jobs table indexes (already defined in models.py but ensuring they exist)
-- These are critical for job status queries and cleanup operations
CREATE INDEX idx_export_jobs_user_id ON export_jobs(user_id);
CREATE INDEX idx_export_jobs_status ON export_jobs(status);
CREATE INDEX idx_export_jobs_created_at ON export_jobs(created_at);
CREATE INDEX idx_export_jobs_expires_at ON export_jobs(expires_at);
CREATE INDEX idx_export_jobs_user_status ON export_jobs(user_id, status);
-- Analyze tables to update statistics for query optimizer (MySQL syntax)
ANALYZE TABLE hotels;
ANALYZE TABLE locations;
ANALYZE TABLE provider_mappings;
ANALYZE TABLE contacts;
ANALYZE TABLE export_jobs;
ANALYZE TABLE supplier_summary;