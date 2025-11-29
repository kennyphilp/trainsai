"""
SQLite database for UK rail timetable data (CIF format).

This module provides a database interface for storing and querying:
- Train schedules from CIF files (ZTR format)
- Station connections and interchanges (ALF format)
- Schedule validity dates and days of operation
- Train service details (operator, category, speed)

The database enables:
- Fast querying of scheduled trains between stations
- Journey planning with connections
- Comparison of scheduled vs actual times
- Finding alternative routes when disruptions occur
"""

import sqlite3
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime, date, time, timedelta
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class ScheduledTrain:
    """Represents a scheduled train service."""
    schedule_id: int
    train_uid: str  # Unique train identifier
    train_headcode: str  # Train reporting number (e.g., "1A23")
    operator_code: str  # Train operating company
    service_type: str  # 'P' = passenger, 'F' = freight, etc.
    
    # Schedule validity
    start_date: date
    end_date: date
    days_run: str  # 7-char string: "1111100" = Mon-Fri only
    
    # Service characteristics
    speed: Optional[int] = None  # Maximum speed in mph
    train_class: Optional[str] = None  # 'B' = both classes, 'S' = standard only
    sleepers: Optional[str] = None  # 'B' = berths, 'S' = seats
    reservations: Optional[str] = None  # 'A' = compulsory, 'R' = recommended
    catering: Optional[str] = None  # Catering codes


@dataclass
class ScheduleLocation:
    """Represents a stop/passing point in a train schedule."""
    location_id: int
    schedule_id: int
    sequence: int  # Order in the journey (0, 1, 2, ...)
    
    tiploc: str  # Station TIPLOC code
    location_type: str  # 'LO' = origin, 'LI' = intermediate, 'LT' = terminus
    
    # Timing
    arrival_time: Optional[time] = None  # Public arrival time
    departure_time: Optional[time] = None  # Public departure time
    pass_time: Optional[time] = None  # Passing time (non-stopping)
    
    # Platform
    platform: Optional[str] = None
    
    # Activity codes
    activities: Optional[str] = None  # e.g., "TB" = train begins, "TF" = train finishes


@dataclass
class StationConnection:
    """Represents a connection/interchange between stations or platforms."""
    connection_id: int
    from_station: str  # TIPLOC code
    to_station: str  # TIPLOC code
    connection_type: str  # 'I' = interchange, 'W' = walking link
    duration_minutes: int  # Time required for connection


class TimetableDatabase:
    """
    SQLite database for storing and querying UK rail timetable data.
    
    The database schema is designed to efficiently support:
    - Point-to-point journey queries
    - Multi-leg journey planning with connections
    - Schedule validity checking (dates and days of week)
    - Integration with real-time departure data
    """
    
    def __init__(self, db_path: str = "timetable.db"):
        """
        Initialize database connection and create schema if needed.
        
        Args:
            db_path: Path to SQLite database file (created if doesn't exist)
        """
        self.db_path = db_path
        self.conn: Optional[sqlite3.Connection] = None
        logger.info(f"Initializing timetable database: {db_path}")
        
    def connect(self):
        """Open database connection and create schema if needed."""
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row  # Enable column access by name
        self._create_schema()
        logger.info("Database connected and schema initialized")
        
    def close(self):
        """Close database connection."""
        if self.conn:
            self.conn.close()
            self.conn = None
            logger.info("Database connection closed")
            
    def _create_schema(self):
        """
        Create database schema for timetable data.
        
        Tables:
        - schedules: Train service headers
        - schedule_locations: Stops and timing points for each service
        - station_connections: Interchange and walking links
        - metadata: Database version and last update info
        """
        cursor = self.conn.cursor()
        
        # Main schedules table - one row per train service
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS schedules (
                schedule_id INTEGER PRIMARY KEY AUTOINCREMENT,
                train_uid TEXT NOT NULL,
                train_headcode TEXT,
                operator_code TEXT NOT NULL,
                service_type TEXT NOT NULL,
                
                -- Schedule validity
                start_date TEXT NOT NULL,
                end_date TEXT NOT NULL,
                days_run TEXT NOT NULL,
                
                -- Service characteristics
                speed INTEGER,
                train_class TEXT,
                sleepers TEXT,
                reservations TEXT,
                catering TEXT,
                
                -- STP (Short Term Planning) indicator
                -- C = Cancelled, N = New, O = Overlay, P = Permanent
                stp_indicator TEXT DEFAULT 'P',
                
                -- Timestamps
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                
                -- Indexes for fast queries
                UNIQUE(train_uid, start_date, stp_indicator)
            )
        """)
        
        # Index for finding trains by operator
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_schedules_operator 
            ON schedules(operator_code)
        """)
        
        # Index for date range queries
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_schedules_dates 
            ON schedules(start_date, end_date)
        """)
        
        # Schedule locations table - timing points for each service
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS schedule_locations (
                location_id INTEGER PRIMARY KEY AUTOINCREMENT,
                schedule_id INTEGER NOT NULL,
                sequence INTEGER NOT NULL,
                
                -- Location identification
                tiploc TEXT NOT NULL,
                location_type TEXT NOT NULL,
                
                -- Timing (stored as TEXT in HH:MM format for easy querying)
                arrival_time TEXT,
                departure_time TEXT,
                pass_time TEXT,
                
                -- Platform and activities
                platform TEXT,
                activities TEXT,
                
                FOREIGN KEY (schedule_id) REFERENCES schedules(schedule_id) ON DELETE CASCADE,
                UNIQUE(schedule_id, sequence)
            )
        """)
        
        # Index for finding trains at a specific station
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_locations_tiploc 
            ON schedule_locations(tiploc)
        """)
        
        # Index for finding all locations in a schedule (for route queries)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_locations_schedule 
            ON schedule_locations(schedule_id, sequence)
        """)
        
        # Station connections table - for journey planning with changes
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS station_connections (
                connection_id INTEGER PRIMARY KEY AUTOINCREMENT,
                from_station TEXT NOT NULL,
                to_station TEXT NOT NULL,
                connection_type TEXT NOT NULL,
                duration_minutes INTEGER NOT NULL,
                
                UNIQUE(from_station, to_station, connection_type)
            )
        """)
        
        # Index for finding connections from a station
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_connections_from 
            ON station_connections(from_station)
        """)
        
        # Metadata table - track database version and updates
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS metadata (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        self.conn.commit()
        logger.info("Database schema created/verified")
        
    def insert_schedule(self, train: ScheduledTrain, locations: List[ScheduleLocation]) -> int:
        """
        Insert a complete train schedule with all its locations.
        
        Args:
            train: Schedule header information
            locations: List of stops/timing points for this service
            
        Returns:
            schedule_id of the inserted schedule
        """
        cursor = self.conn.cursor()
        
        cursor.execute("""
            INSERT INTO schedules (
                train_uid, train_headcode, operator_code, service_type,
                start_date, end_date, days_run,
                speed, train_class, sleepers, reservations, catering
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            train.train_uid, train.train_headcode, train.operator_code, train.service_type,
            train.start_date.isoformat(), train.end_date.isoformat(), train.days_run,
            train.speed, train.train_class, train.sleepers, train.reservations, train.catering
        ))
        
        schedule_id = cursor.lastrowid
        
        # Insert all locations
        for loc in locations:
            cursor.execute("""
                INSERT INTO schedule_locations (
                    schedule_id, sequence, tiploc, location_type,
                    arrival_time, departure_time, pass_time,
                    platform, activities
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                schedule_id, loc.sequence, loc.tiploc, loc.location_type,
                loc.arrival_time.strftime("%H:%M") if loc.arrival_time else None,
                loc.departure_time.strftime("%H:%M") if loc.departure_time else None,
                loc.pass_time.strftime("%H:%M") if loc.pass_time else None,
                loc.platform, loc.activities
            ))
        
        self.conn.commit()
        logger.debug(f"Inserted schedule {train.train_uid} with {len(locations)} locations")
        return schedule_id
        
    def find_trains_between_stations(
        self, 
        from_tiploc: str, 
        to_tiploc: str, 
        travel_date: date,
        departure_time: Optional[time] = None
    ) -> List[Dict[str, Any]]:
        """
        Find all direct trains between two stations on a specific date.
        
        Args:
            from_tiploc: Departure station TIPLOC code
            to_tiploc: Arrival station TIPLOC code
            travel_date: Date of travel
            departure_time: Optional minimum departure time
            
        Returns:
            List of train services with departure/arrival times
        """
        cursor = self.conn.cursor()
        
        # Convert date to day of week (0=Monday, 6=Sunday)
        day_index = travel_date.weekday()
        
        # Build query
        query = """
            SELECT 
                s.train_uid,
                s.train_headcode,
                s.operator_code,
                s.train_class,
                s.reservations,
                s.catering,
                dep.departure_time as dep_time,
                arr.arrival_time as arr_time,
                dep.platform as dep_platform,
                arr.platform as arr_platform,
                dep.sequence as dep_seq,
                arr.sequence as arr_seq
            FROM schedules s
            JOIN schedule_locations dep ON s.schedule_id = dep.schedule_id
            JOIN schedule_locations arr ON s.schedule_id = arr.schedule_id
            WHERE dep.tiploc = ?
              AND arr.tiploc = ?
              AND dep.sequence < arr.sequence
              AND date(s.start_date) <= date(?)
              AND date(s.end_date) >= date(?)
              AND substr(s.days_run, ? + 1, 1) = '1'
        """
        
        params = [from_tiploc, to_tiploc, travel_date.isoformat(), 
                 travel_date.isoformat(), day_index]
        
        if departure_time:
            query += " AND dep.departure_time >= ?"
            params.append(departure_time.strftime("%H:%M"))
            
        query += " ORDER BY dep.departure_time"
        
        cursor.execute(query, params)
        
        results = []
        for row in cursor.fetchall():
            results.append({
                'train_uid': row['train_uid'],
                'headcode': row['train_headcode'],
                'operator': row['operator_code'],
                'class': row['train_class'],
                'reservations': row['reservations'],
                'catering': row['catering'],
                'departure_time': row['dep_time'],
                'arrival_time': row['arr_time'],
                'departure_platform': row['dep_platform'],
                'arrival_platform': row['arr_platform'],
                'duration_minutes': self._calculate_duration(row['dep_time'], row['arr_time'])
            })
            
        logger.info(f"Found {len(results)} trains from {from_tiploc} to {to_tiploc} on {travel_date}")
        return results
        
    def _calculate_duration(self, dep_time: str, arr_time: str) -> int:
        """
        Calculate journey duration in minutes.
        Handles overnight journeys (e.g., 23:50 to 01:15).
        
        Args:
            dep_time: Departure time in HH:MM format
            arr_time: Arrival time in HH:MM format
            
        Returns:
            Duration in minutes
        """
        dep_h, dep_m = map(int, dep_time.split(':'))
        arr_h, arr_m = map(int, arr_time.split(':'))
        
        dep_minutes = dep_h * 60 + dep_m
        arr_minutes = arr_h * 60 + arr_m
        
        # Handle overnight journeys
        if arr_minutes < dep_minutes:
            arr_minutes += 24 * 60
            
        return arr_minutes - dep_minutes
        
    def get_schedule_route(self, train_uid: str, travel_date: date) -> List[Dict[str, Any]]:
        """
        Get complete route for a train service on a specific date.
        
        Args:
            train_uid: Train unique identifier
            travel_date: Date of travel
            
        Returns:
            List of stops in sequence with timing information
        """
        cursor = self.conn.cursor()
        
        day_index = travel_date.weekday()
        
        cursor.execute("""
            SELECT 
                loc.tiploc,
                loc.location_type,
                loc.arrival_time,
                loc.departure_time,
                loc.pass_time,
                loc.platform,
                loc.activities,
                loc.sequence
            FROM schedules s
            JOIN schedule_locations loc ON s.schedule_id = loc.schedule_id
            WHERE s.train_uid = ?
              AND date(s.start_date) <= date(?)
              AND date(s.end_date) >= date(?)
              AND substr(s.days_run, ? + 1, 1) = '1'
            ORDER BY loc.sequence
        """, (train_uid, travel_date.isoformat(), travel_date.isoformat(), day_index))
        
        results = []
        for row in cursor.fetchall():
            results.append({
                'tiploc': row['tiploc'],
                'type': row['location_type'],
                'arrival': row['arrival_time'],
                'departure': row['departure_time'],
                'pass': row['pass_time'],
                'platform': row['platform'],
                'activities': row['activities'],
                'sequence': row['sequence']
            })
            
        return results
        
    def insert_connection(self, conn_data: StationConnection):
        """
        Insert a station connection/interchange.
        
        Args:
            conn_data: Connection information
        """
        cursor = self.conn.cursor()
        
        cursor.execute("""
            INSERT OR REPLACE INTO station_connections (
                from_station, to_station, connection_type, duration_minutes
            ) VALUES (?, ?, ?, ?)
        """, (
            conn_data.from_station, conn_data.to_station,
            conn_data.connection_type, conn_data.duration_minutes
        ))
        
        self.conn.commit()
        
    def get_connections_from_station(self, tiploc: str) -> List[StationConnection]:
        """
        Get all possible connections from a station.
        
        Args:
            tiploc: Station TIPLOC code
            
        Returns:
            List of available connections
        """
        cursor = self.conn.cursor()
        
        cursor.execute("""
            SELECT connection_id, from_station, to_station, connection_type, duration_minutes
            FROM station_connections
            WHERE from_station = ?
        """, (tiploc,))
        
        return [
            StationConnection(
                connection_id=row['connection_id'],
                from_station=row['from_station'],
                to_station=row['to_station'],
                connection_type=row['connection_type'],
                duration_minutes=row['duration_minutes']
            )
            for row in cursor.fetchall()
        ]
        
    def get_statistics(self) -> Dict[str, int]:
        """Get database statistics (number of schedules, locations, etc.)."""
        cursor = self.conn.cursor()
        
        cursor.execute("SELECT COUNT(*) as count FROM schedules")
        schedule_count = cursor.fetchone()['count']
        
        cursor.execute("SELECT COUNT(*) as count FROM schedule_locations")
        location_count = cursor.fetchone()['count']
        
        cursor.execute("SELECT COUNT(*) as count FROM station_connections")
        connection_count = cursor.fetchone()['count']
        
        return {
            'schedules': schedule_count,
            'locations': location_count,
            'connections': connection_count
        }
