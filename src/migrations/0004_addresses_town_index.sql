-- Index for the case-insensitive partial town filters used by the new browse
-- endpoints (GET /stations, /connections/not-working, /stations/search).
-- Note: a leading-wildcard LIKE '%town%' can't use a B-tree index for the scan
-- itself, but this still helps the optimizer (and any exact/prefix lookups on
-- town elsewhere) and keeps schema in sync with models.py's Address.__table_args__.
-- Apply with: mysql -u root -p ev_station_db < 0004_addresses_town_index.sql
--
-- MySQL has no "ADD INDEX IF NOT EXISTS", so this is guarded with an
-- information_schema check + PREPARE/EXECUTE, making the file safe to rerun.

SET @idx_exists = (
    SELECT COUNT(*) FROM information_schema.STATISTICS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME = 'addresses'
      AND INDEX_NAME = 'idx_addresses_town'
);
SET @ddl = IF(@idx_exists = 0,
    'ALTER TABLE addresses ADD INDEX idx_addresses_town (town(100))',
    'SELECT 1'
);
PREPARE stmt FROM @ddl;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;
