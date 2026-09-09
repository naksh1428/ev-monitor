-- Migration for databases created before this change (the docker-entrypoint-initdb.d
-- script in ev_station_db.sql only runs once, against an empty volume).
-- Apply with: mysql -u root -p ev_station_db < 0001_connection_status_daily.sql
--
-- MySQL (unlike MariaDB) has no "ADD COLUMN IF NOT EXISTS", so every DDL step
-- here is guarded with an information_schema check + PREPARE/EXECUTE, making
-- the whole file safe to rerun.

SET @col_exists = (
    SELECT COUNT(*) FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME = 'connections'
      AND COLUMN_NAME = 'status_type_id'
);
SET @ddl = IF(@col_exists = 0,
    'ALTER TABLE connections ADD COLUMN status_type_id INT',
    'SELECT 1'
);
PREPARE stmt FROM @ddl;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- Cannot add a duplicate FK by name if this migration is re-run; guard with a
-- check against information_schema so re-running the file is a no-op.
SET @fk_exists = (
    SELECT COUNT(*) FROM information_schema.TABLE_CONSTRAINTS
    WHERE CONSTRAINT_SCHEMA = DATABASE()
      AND TABLE_NAME = 'connections'
      AND CONSTRAINT_NAME = 'fk_connections_status_type_id'
);
SET @ddl = IF(@fk_exists = 0,
    'ALTER TABLE connections ADD CONSTRAINT fk_connections_status_type_id FOREIGN KEY (status_type_id) REFERENCES status_types(id)',
    'SELECT 1'
);
PREPARE stmt FROM @ddl;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

CREATE TABLE IF NOT EXISTS connection_status_daily (
    id              BIGINT AUTO_INCREMENT PRIMARY KEY,
    snapshot_date   DATE NOT NULL,
    station_id      INT NOT NULL,
    connection_id   INT NOT NULL,
    status_type_id  INT,
    is_working      BOOLEAN NOT NULL,
    town            VARCHAR(255),
    postcode        VARCHAR(16),
    operator_id     INT,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (snapshot_date, connection_id),
    FOREIGN KEY (station_id)     REFERENCES stations(id),
    FOREIGN KEY (connection_id)  REFERENCES connections(id),
    FOREIGN KEY (status_type_id) REFERENCES status_types(id),
    INDEX (connection_id, snapshot_date),
    INDEX (snapshot_date, is_working)
);
