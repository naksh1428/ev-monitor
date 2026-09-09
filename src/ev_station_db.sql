CREATE DATABASE IF NOT EXISTS ev_station_db;
USE ev_station_db;

CREATE TABLE operators (
    id          INT PRIMARY KEY,
    title       VARCHAR(255),
    website     VARCHAR(255),
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

CREATE TABLE status_types (
    id              INT PRIMARY KEY,
    title           VARCHAR(100),
    is_operational  BOOLEAN,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

CREATE TABLE addresses (
    id                 INT PRIMARY KEY,
    title              TEXT,
    address_line1      TEXT,
    address_line2      TEXT,
    town               TEXT,
    state_or_province  TEXT,
    postcode           TEXT,
    country_id         INT,
    latitude           DOUBLE,
    longitude          DOUBLE,
    contact_no         VARCHAR(20),
    created_at         TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at         TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_addresses_town (town(100))  -- town is TEXT; MySQL requires a key length to index it
);

CREATE TABLE stations (
    id                       INT PRIMARY KEY,
    uuid                     CHAR(36) UNIQUE,
    operator_id              INT,
    usage_type_id            INT,
    address_id               INT,
    number_of_points         INT,
    status_type_id           INT,
    date_created             TIMESTAMP NULL,   -- OCM's own DateCreated
    date_last_status_update  TIMESTAMP NULL,
    created_at               TIMESTAMP DEFAULT CURRENT_TIMESTAMP,  -- when we first stored this row
    updated_at               TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (operator_id)    REFERENCES operators(id),
    FOREIGN KEY (address_id)     REFERENCES addresses(id),
    FOREIGN KEY (status_type_id) REFERENCES status_types(id)
);

CREATE TABLE connections (
    id                  INT PRIMARY KEY,
    station_id          INT NOT NULL,
    connection_type_id  INT,
    current_type_id     INT,
    level_id            INT,
    power_kw            DECIMAL(8,2),
    amps                INT,
    voltage             INT,
    quantity            INT,
    status_type_id      INT,
    created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (station_id)     REFERENCES stations(id),
    FOREIGN KEY (status_type_id) REFERENCES status_types(id)
);

CREATE TABLE status_snapshots (
    id                 BIGINT AUTO_INCREMENT PRIMARY KEY,
    station_id         INT NOT NULL,
    status_type_id     INT,
    source_updated_at  TIMESTAMP NULL,
    checked_at         TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (station_id)     REFERENCES stations(id),
    FOREIGN KEY (status_type_id) REFERENCES status_types(id),
    INDEX (station_id, checked_at)
);

-- Feature: daily per-connection working/not-working snapshot, used for uptime
-- and down-streak reporting. One row per connection per day; re-running the
-- daily job for the same day upserts via the UNIQUE key instead of duplicating.
CREATE TABLE connection_status_daily (
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