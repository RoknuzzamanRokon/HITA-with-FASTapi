-- Database Optimization Script for Locations Table
-- Run these commands in your database to dramatically improve performance
-- 1. Add index for country_name queries (for /countries endpoint)
CREATE INDEX IF NOT EXISTS idx_locations_country_name ON locations(country_name);
-- 2. Add index for city_name queries (for /cities endpoint)  
CREATE INDEX IF NOT EXISTS idx_locations_city_name ON locations(city_name);
-- 3. Add index for country_code queries (for /country_codes endpoint)
CREATE INDEX IF NOT EXISTS idx_locations_country_code ON locations(country_code);
-- 4. Add composite index for common search patterns
CREATE INDEX IF NOT EXISTS idx_locations_search ON locations(country_name, city_name, state_name);
-- 5. Add composite index specifically for cities_with_countries endpoint (SUPER FAST!)
CREATE INDEX IF NOT EXISTS idx_locations_country_city ON locations(country_name, city_name)
WHERE country_name IS NOT NULL
    AND country_name != ''
    AND city_name IS NOT NULL
    AND city_name != '';
-- 6. Add index for non-null filtering (improves WHERE clauses)
CREATE INDEX IF NOT EXISTS idx_locations_country_not_null ON locations(country_name)
WHERE country_name IS NOT NULL
    AND country_name != '';
CREATE INDEX IF NOT EXISTS idx_locations_city_not_null ON locations(city_name)
WHERE city_name IS NOT NULL
    AND city_name != '';
-- 7. Analyze table statistics for query optimizer
ANALYZE locations;
-- Expected Performance Improvement:
-- Before: 45+ seconds for any endpoint
-- After:  100-500ms (90x+ faster)
-- Cached: ~1ms (45,000x+ faster)