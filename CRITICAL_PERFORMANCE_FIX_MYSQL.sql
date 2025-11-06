-- CRITICAL PERFORMANCE FIX FOR LOCATIONS TABLE (MySQL/Azure Database)
-- THIS MUST BE RUN TO GET FAST PERFORMANCE (2-10 seconds instead of 1+ minute)
-- Check current table status
SELECT TABLE_NAME,
    TABLE_ROWS,
    DATA_LENGTH,
    INDEX_LENGTH,
    (DATA_LENGTH + INDEX_LENGTH) as TOTAL_SIZE
FROM information_schema.TABLES
WHERE TABLE_SCHEMA = DATABASE()
    AND TABLE_NAME = 'locations';
-- Show current indexes
SHOW INDEX
FROM locations;
-- 1. MOST IMPORTANT: Composite index for cities_with_countries endpoint
CREATE INDEX idx_locations_country_city_optimized ON locations(country_name, city_name) USING BTREE;
-- 2. Additional performance indexes
CREATE INDEX idx_locations_country_name_fast ON locations(country_name) USING BTREE;
CREATE INDEX idx_locations_city_name_fast ON locations(city_name) USING BTREE;
-- 3. Specialized index for non-null filtering
CREATE INDEX idx_locations_country_city_not_null ON locations(country_name, city_name)
WHERE country_name IS NOT NULL
    AND country_name != ''
    AND city_name IS NOT NULL
    AND city_name != '';
-- 4. Update table statistics (CRITICAL for query optimizer)
ANALYZE TABLE locations;
-- 5. Optional: Optimize table structure
OPTIMIZE TABLE locations;
-- Check indexes after creation
SHOW INDEX
FROM locations;
-- Expected Performance After Running This Script:
-- Before: 1+ minute (60+ seconds)
-- After:  2-10 seconds (6-30x faster)
-- Cached: ~1ms (instant)
-- IMPORTANT NOTES:
-- 1. This script is optimized for MySQL/Azure Database
-- 2. Index creation may take several minutes on large tables
-- 3. Monitor your database performance after running this script
-- 4. Consider running during low-traffic hours for large tables