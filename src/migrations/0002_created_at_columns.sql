-- Adds a "record inserted" timestamp to every table that didn't already have
-- one (status_snapshots.checked_at and connection_status_daily.created_at
-- already serve this purpose, so they're left as-is).
-- Apply with: mysql -u root -p ev_station_db < 0002_created_at_columns.sql
--
-- MySQL has no "ADD COLUMN IF NOT EXISTS", so each step is guarded with an
-- information_schema check + PREPARE/EXECUTE, making the file safe to rerun.

DROP PROCEDURE IF EXISTS _add_created_at_if_missing;

DELIMITER //
CREATE PROCEDURE _add_created_at_if_missing(IN tbl VARCHAR(64))
BEGIN
    DECLARE col_exists INT;
    SELECT COUNT(*) INTO col_exists FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = tbl AND COLUMN_NAME = 'created_at';

    IF col_exists = 0 THEN
        SET @ddl = CONCAT('ALTER TABLE `', tbl, '` ADD COLUMN created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP');
        PREPARE stmt FROM @ddl;
        EXECUTE stmt;
        DEALLOCATE PREPARE stmt;
    END IF;
END //
DELIMITER ;

CALL _add_created_at_if_missing('operators');
CALL _add_created_at_if_missing('status_types');
CALL _add_created_at_if_missing('addresses');
CALL _add_created_at_if_missing('stations');
CALL _add_created_at_if_missing('connections');

DROP PROCEDURE _add_created_at_if_missing;
