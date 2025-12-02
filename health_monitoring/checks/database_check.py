"""Database health check implementation."""

import os
import sqlite3
import time
from datetime import datetime
from pathlib import Path

from .base_check import BaseHealthCheck
from ..models import HealthResult, HealthStatus


class DatabaseHealthCheck(BaseHealthCheck):
    """Check database connectivity and health."""
    
    def __init__(self, db_path: str):
        """Initialize database health check.
        
        Args:
            db_path: Path to the SQLite database file
        """
        super().__init__("database", timeout=5.0)
        self.db_path = db_path
    
    async def check(self) -> HealthResult:
        """Check database health."""
        start_time = time.time()
        details = {}
        
        try:
            # Check if database file exists
            db_file = Path(self.db_path)
            details['db_path'] = self.db_path
            details['db_exists'] = db_file.exists()
            
            if not db_file.exists():
                return HealthResult(
                    name=self.name,
                    status=HealthStatus.UNHEALTHY,
                    message=f"Database file not found: {self.db_path}",
                    details=details,
                    duration_ms=round((time.time() - start_time) * 1000, 2),
                    timestamp=datetime.now()
                )
            
            # Check file size and permissions
            details['db_size_mb'] = round(db_file.stat().st_size / (1024 * 1024), 2)
            details['db_readable'] = os.access(self.db_path, os.R_OK)
            details['db_writable'] = os.access(self.db_path, os.W_OK)
            
            # Test database connectivity
            with sqlite3.connect(self.db_path, timeout=3.0) as conn:
                cursor = conn.cursor()
                
                # Test basic query
                cursor.execute("SELECT sqlite_version()")
                sqlite_version = cursor.fetchone()[0]
                details['sqlite_version'] = sqlite_version
                
                # Check if main tables exist
                cursor.execute("""
                    SELECT name FROM sqlite_master 
                    WHERE type='table' AND name NOT LIKE 'sqlite_%'
                """)
                tables = [row[0] for row in cursor.fetchall()]
                details['tables'] = tables
                details['table_count'] = len(tables)
                
                # Check if we have the expected timetable tables
                expected_tables = ['schedules', 'schedule_stops', 'stations']
                missing_tables = [t for t in expected_tables if t not in tables]
                details['missing_tables'] = missing_tables
                details['schema_complete'] = len(missing_tables) == 0
                
                # Get row counts for key tables
                if 'schedules' in tables:
                    cursor.execute("SELECT COUNT(*) FROM schedules")
                    details['schedules_count'] = cursor.fetchone()[0]
                
                if 'stations' in tables:
                    cursor.execute("SELECT COUNT(*) FROM stations")
                    details['stations_count'] = cursor.fetchone()[0]
            
            # Determine status
            status = HealthStatus.HEALTHY
            message = f"Database healthy with {details['table_count']} tables"
            
            if not details['db_readable'] or not details['db_writable']:
                status = HealthStatus.DEGRADED
                message = "Database has permission issues"
            elif missing_tables:
                status = HealthStatus.DEGRADED
                message = f"Missing tables: {', '.join(missing_tables)}"
            elif details.get('schedules_count', 0) == 0:
                status = HealthStatus.DEGRADED
                message = "No schedule data found in database"
            
            return HealthResult(
                name=self.name,
                status=status,
                message=message,
                details=details,
                duration_ms=round((time.time() - start_time) * 1000, 2),
                timestamp=datetime.now()
            )
            
        except sqlite3.Error as e:
            return HealthResult(
                name=self.name,
                status=HealthStatus.UNHEALTHY,
                message=f"Database error: {str(e)}",
                details={**details, 'error': str(e), 'error_type': 'sqlite3.Error'},
                duration_ms=round((time.time() - start_time) * 1000, 2),
                timestamp=datetime.now()
            )
        except Exception as e:
            return HealthResult(
                name=self.name,
                status=HealthStatus.UNHEALTHY,
                message=f"Database health check failed: {str(e)}",
                details={**details, 'error': str(e), 'error_type': type(e).__name__},
                duration_ms=round((time.time() - start_time) * 1000, 2),
                timestamp=datetime.now()
            )