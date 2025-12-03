# Database Schema Diagram

## Timetable Database Architecture

```mermaid
erDiagram
    schedules {
        INTEGER schedule_id PK "Auto-increment primary key"
        TEXT train_uid UK "Unique train identifier"
        TEXT train_headcode "Train reporting number (e.g. 1A23)"
        TEXT operator_code "Train operating company"
        TEXT service_type "P=passenger, F=freight"
        TEXT start_date "Schedule validity start (YYYY-MM-DD)"
        TEXT end_date "Schedule validity end (YYYY-MM-DD)"
        TEXT days_run "7-char string: 1111100 = Mon-Fri"
        INTEGER speed "Maximum speed in mph"
        TEXT train_class "B=both classes, S=standard only"
        TEXT sleepers "B=berths, S=seats"
        TEXT reservations "A=compulsory, R=recommended"
        TEXT catering "Catering codes"
        TEXT stp_indicator "Schedule type indicator"
        TIMESTAMP created_at "Import timestamp"
    }

    schedule_locations {
        INTEGER location_id PK "Auto-increment primary key"
        INTEGER schedule_id FK "References schedules.schedule_id"
        INTEGER sequence "Stop sequence number"
        TEXT tiploc "TIPLOC station code"
        TEXT location_type "LO=origin, LI=intermediate, LT=terminus"
        TEXT arrival_time "HH:MM format"
        TEXT departure_time "HH:MM format"
        TEXT pass_time "HH:MM for non-stopping"
        TEXT platform "Platform number/letter"
        TEXT activities "Station activities codes"
    }

    stations {
        INTEGER station_id PK "Auto-increment primary key"
        TEXT tiploc UK "Primary TIPLOC identifier"
        TEXT crs_code "3-letter CRS code (e.g. GLC)"
        TEXT station_name "Full station name"
        TEXT short_name "Abbreviated name"
        TEXT country "Scotland, England, Wales"
        TEXT region "Network Rail region"
        TEXT operator_code "Primary operator"
        REAL latitude "GPS coordinates"
        REAL longitude "GPS coordinates"
        BOOLEAN is_active "Is station active"
        TIMESTAMP created_at "Record creation time"
        TIMESTAMP updated_at "Last update time"
    }

    station_aliases {
        INTEGER alias_id PK "Auto-increment primary key"
        INTEGER station_id FK "References stations.station_id"
        TEXT alias_name "Alternative station name"
        TEXT alias_type "common, historical, colloquial, official"
        BOOLEAN is_primary "Is this the preferred name"
    }

    tiploc_mappings {
        INTEGER mapping_id PK "Auto-increment primary key"
        TEXT source_tiploc "TIPLOC as found in external data"
        TEXT canonical_tiploc "Canonical TIPLOC to use"
        TEXT mapping_reason "Why this mapping exists"
        TEXT data_source "Source requiring mapping (MSN, etc)"
        TIMESTAMP created_at "Mapping creation time"
    }

    station_connections {
        INTEGER connection_id PK "Auto-increment primary key"
        TEXT from_station "Origin station TIPLOC"
        TEXT to_station "Destination station TIPLOC"
        TEXT connection_type "Connection type"
        INTEGER duration_minutes "Connection time in minutes"
    }

    metadata {
        TEXT key PK "Metadata key"
        TEXT value "Metadata value"
        TIMESTAMP updated_at "Last update time"
    }

    import_metadata {
        INTEGER import_id PK "Auto-increment primary key"
        TEXT file_type "ALF, CIF, etc"
        TEXT file_path "Source file path"
        TEXT file_hash "File content hash"
        TEXT sequence_number "File sequence number"
        TEXT generated_date "File generation date"
        INTEGER file_size "File size in bytes"
        INTEGER record_count "Total records in file"
        INTEGER records_imported "Successfully imported records"
        TIMESTAMP import_date "Import timestamp"
        REAL import_duration_seconds "Import duration"
        BOOLEAN success "Import success flag"
        TEXT errors "Import error messages"
    }

    %% Relationships
    schedules ||--o{ schedule_locations : "has stops"
    stations ||--o{ station_aliases : "has aliases"
    schedule_locations }o--|| stations : "references via tiploc"
    
    %% Data flow relationships (logical, not FK)
    stations ||--o{ station_connections : "from_station"
    stations ||--o{ station_connections : "to_station"
    tiploc_mappings }o--|| stations : "maps to canonical"
```

## Key Relationships and Data Flow

### Core Timetable Data
- **schedules** ↔ **schedule_locations**: One-to-many relationship defining train routes
- Each schedule has multiple locations (stops) in sequence order
- **schedule_locations.tiploc** references station codes but no formal FK (performance)

### Station Reference System
- **stations**: Master station registry with canonical TIPLOCs
- **station_aliases**: Multiple names per station (official, common, historical)
- **tiploc_mappings**: Handles data source inconsistencies (MSN vs CIF formats)

### Data Quality & Metadata
- **import_metadata**: Tracks all file imports with success/failure details
- **metadata**: System-wide configuration and statistics
- **station_connections**: Future use for journey planning (currently empty)

## Station Resolution Flow

```mermaid
flowchart TD
    A[User Input: 'Glasgow Central'] --> B{Check tiploc_mappings}
    B -->|Found| C[Return canonical_tiploc]
    B -->|Not Found| D{Check stations.tiploc}
    D -->|Found| E[Return tiploc]
    D -->|Not Found| F{Check stations.crs_code}
    F -->|Found| G[Return tiploc]
    F -->|Not Found| H{Check stations.station_name}
    H -->|Found| I[Return tiploc]
    H -->|Not Found| J{Check station_aliases}
    J -->|Found| K[Return station.tiploc]
    J -->|Not Found| L{Fuzzy Search}
    L -->|Found| M[Return best match tiploc]
    L -->|Not Found| N[Return null]
```

## Database Statistics (Current)

| Table | Records | Purpose |
|-------|---------|---------|
| **schedules** | 581,945 | Train service definitions |
| **schedule_locations** | 9,966,849 | Individual train stops |
| **stations** | 33 | Scottish station registry |
| **station_aliases** | 15+ | Alternative station names |
| **tiploc_mappings** | 2 | Data consistency fixes |
| **import_metadata** | 9 | File import tracking |
| **metadata** | 4 | System configuration |

## Index Strategy

**Performance Indexes:**
- `stations.tiploc` - Primary station lookups
- `stations.crs_code` - CRS code resolution  
- `stations.station_name` - Name-based searches
- `station_aliases.alias_name` - Alias resolution
- `tiploc_mappings.source_tiploc` - Data mapping lookups

**Query Optimization:**
- No foreign keys between `schedule_locations` and `stations` for performance
- Logical relationships maintained through application code
- TIPLOC-based lookups optimized for high-frequency operations

## Data Sources Integration

```mermaid
flowchart LR
    A[Network Rail NTROD JSON] --> B[schedules + schedule_locations]
    C[MSN Station File] --> D[stations + aliases]
    E[Manual Curation] --> F[tiploc_mappings]
    G[Import Process] --> H[import_metadata]
    
    B --> I[TimetableTools]
    D --> I
    F --> I
    I --> J[Station Resolution]
    I --> K[Train Queries]
```