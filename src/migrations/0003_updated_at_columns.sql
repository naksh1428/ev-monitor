-- Adds an "updated_at" timestamp (refreshed on every write) to the same tables
-- that got created_at in 0002. created_at stays fixed at first insert;
-- updated_at reflects the most recent CRUD write, whether it came through the
-- ORM (which also sends its own onupdate value) or a direct SQL statement.
-- Apply with: mysql -u root -p ev_station_db < 0003_updated_at_columns.sql
--
-- MySQL has no "ADD COLUMN IF NOT EXISTS", so this is guarded with an
-- information_schema check + PREPARE/EXECUTE, making the file safe to rerun.

DROP PROCEDURE IF EXISTS _add_updated_at_if_missing;

DELIMITER //
CREATE PROCEDURE _add_updated_at_if_missing(IN tbl VARCHAR(64))
BEGIN
    DECLARE col_exists INT;
    SELECT COUNT(*) INTO col_exists FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = tbl AND COLUMN_NAME = 'updated_at';

    IF col_exists = 0 THEN
        SET @ddl = CONCAT(
            'ALTER TABLE `', tbl, '` ADD COLUMN updated_at TIMESTAMP ',
            'DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP'
        );
        PREPARE stmt FROM @ddl;
        EXECUTE stmt;
        DEALLOCATE PREPARE stmt;
    END IF;
END //
DELIMITER ;

CALL _add_updated_at_if_missing('operators');
CALL _add_updated_at_if_missing('status_types');
CALL _add_updated_at_if_missing('addresses');
CALL _add_updated_at_if_missing('stations');
CALL _add_updated_at_if_missing('connections');

DROP PROCEDURE _add_updated_at_if_missing;
