-- IMPROVED STATION REFERENCE ARCHITECTURE
-- This schema addresses the fundamental station naming and resolution issues

-- 1. Core station information table
CREATE TABLE stations (
    station_id INTEGER PRIMARY KEY AUTOINCREMENT,
    tiploc TEXT UNIQUE NOT NULL,            -- Primary TIPLOC identifier
    crs_code TEXT,                          -- 3-letter CRS code (e.g., GLC, EDI)
    station_name TEXT NOT NULL,             -- Full station name
    short_name TEXT,                        -- Abbreviated name
    country TEXT,                           -- Scotland, England, Wales
    region TEXT,                            -- Network Rail region
    operator_code TEXT,                     -- Primary operator
    latitude REAL,                          -- GPS coordinates
    longitude REAL,
    is_active BOOLEAN DEFAULT 1,            -- Is station still in use
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 2. Station aliases and alternative names
CREATE TABLE station_aliases (
    alias_id INTEGER PRIMARY KEY AUTOINCREMENT,
    station_id INTEGER NOT NULL,
    alias_name TEXT NOT NULL,               -- Alternative name
    alias_type TEXT NOT NULL,               -- 'common', 'historical', 'colloquial'
    is_primary BOOLEAN DEFAULT 0,           -- Is this the preferred name
    FOREIGN KEY (station_id) REFERENCES stations(station_id),
    UNIQUE(station_id, alias_name)
);

-- 3. TIPLOC mappings for data inconsistencies
CREATE TABLE tiploc_mappings (
    mapping_id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_tiploc TEXT NOT NULL,            -- TIPLOC as found in external data
    canonical_tiploc TEXT NOT NULL,         -- Canonical TIPLOC to use
    mapping_reason TEXT,                    -- Why this mapping exists
    data_source TEXT,                       -- Source that required this mapping
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(source_tiploc, data_source)
);

-- 4. Indexes for performance
CREATE INDEX idx_stations_crs ON stations(crs_code);
CREATE INDEX idx_stations_name ON stations(station_name);
CREATE INDEX idx_stations_tiploc ON stations(tiploc);
CREATE INDEX idx_stations_country ON stations(country);
CREATE INDEX idx_aliases_name ON station_aliases(alias_name);
CREATE INDEX idx_aliases_station ON station_aliases(station_id);
CREATE INDEX idx_tiploc_mappings_source ON tiploc_mappings(source_tiploc);

-- 5. Views for easy querying
CREATE VIEW station_search AS
SELECT 
    s.station_id,
    s.tiploc,
    s.crs_code,
    s.station_name,
    s.country,
    s.region,
    GROUP_CONCAT(sa.alias_name, '|') as all_names
FROM stations s
LEFT JOIN station_aliases sa ON s.station_id = sa.station_id
GROUP BY s.station_id;

-- 6. Function to populate station data from existing schedule data
-- This would extract unique TIPLOCs and attempt to identify them

-- Example data for Scottish stations (to be populated properly)
INSERT INTO stations (tiploc, crs_code, station_name, country, region) VALUES
('GLGC', 'GLC', 'Glasgow Central', 'Scotland', 'Scotland'),
('EDINBUR', 'EDB', 'Edinburgh Waverley', 'Scotland', 'Scotland'), 
('STIRLNG', 'STG', 'Stirling', 'Scotland', 'Scotland'),
('LARGS', 'LAR', 'Largs', 'Scotland', 'Scotland');

-- Add aliases
INSERT INTO station_aliases (station_id, alias_name, alias_type, is_primary) 
SELECT s.station_id, 'Glasgow Central', 'common', 1 
FROM stations s WHERE s.tiploc = 'GLGC';

INSERT INTO station_aliases (station_id, alias_name, alias_type, is_primary)
SELECT s.station_id, 'Edinburgh', 'common', 0
FROM stations s WHERE s.tiploc = 'EDINBUR';

INSERT INTO station_aliases (station_id, alias_name, alias_type, is_primary)
SELECT s.station_id, 'Edinburgh Waverley', 'official', 1
FROM stations s WHERE s.tiploc = 'EDINBUR';

-- Add known TIPLOC mappings
INSERT INTO tiploc_mappings (source_tiploc, canonical_tiploc, mapping_reason, data_source) VALUES
('EDINBURE', 'EDINBUR', 'MSN file inconsistency', 'MSN'),
('GLGC   G', 'GLGC', 'MSN file whitespace issue', 'MSN');