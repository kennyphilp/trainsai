"""
Timetable data importer for CIF files.

This module provides functionality to:
- Import CIF timetable data files (MSN, ZTR, ALF) into SQLite database
- Track data versions to prevent duplicate imports
- Validate imported data integrity
- Provide CLI interface for data management operations

The importer detects file versions from CIF headers and maintains metadata
to ensure each version is only loaded once.
"""

import os
import sqlite3
import hashlib
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime, date, time

from timetable_database import TimetableDatabase, ScheduledTrain, ScheduleLocation, StationConnection
from timetable_parser import StationResolver, CIFScheduleParser, ALFParser

logger = logging.getLogger(__name__)


@dataclass
class DataFileInfo:
    """Information about a CIF data file."""
    file_type: str  # 'MSN', 'ZTR', 'ALF', etc.
    sequence: str   # Sequence number from header
    generated_date: str  # Generation date from header
    file_hash: str  # SHA256 hash of file content
    file_size: int  # File size in bytes
    record_count: int  # Number of data records
    
    
@dataclass
class ImportResult:
    """Result of data import operation."""
    success: bool
    file_info: DataFileInfo
    records_imported: int
    errors: List[str]
    duration_seconds: float
    skipped_reason: Optional[str] = None


class CIFVersionDetector:
    """Detects CIF file versions and metadata from headers."""
    
    def analyze_file(self, file_path: str) -> DataFileInfo:
        """
        Analyze a CIF file to extract version and metadata.
        
        Args:
            file_path: Path to CIF file
            
        Returns:
            DataFileInfo with file metadata
        """
        path = Path(file_path)
        
        # Calculate file hash and size
        file_hash = self._calculate_file_hash(file_path)
        file_size = path.stat().st_size
        
        # Parse header information
        with open(file_path, 'r', encoding='utf-8') as f:
            header_info = self._parse_header(f)
        
        # Count data records
        record_count = self._count_data_records(file_path, header_info['file_type'])
        
        return DataFileInfo(
            file_type=header_info['file_type'],
            sequence=header_info['sequence'],
            generated_date=header_info['generated_date'],
            file_hash=file_hash,
            file_size=file_size,
            record_count=record_count
        )
    
    def _calculate_file_hash(self, file_path: str) -> str:
        """Calculate SHA256 hash of file content."""
        hash_sha256 = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_sha256.update(chunk)
        return hash_sha256.hexdigest()
    
    def _parse_header(self, file_handle) -> Dict[str, str]:
        """Parse CIF file header to extract metadata."""
        file_type = 'UNKNOWN'
        sequence = '000'
        generated_date = ''
        
        # Reset to beginning and read first few lines
        file_handle.seek(0)
        for i, line in enumerate(file_handle):
            if i > 10:  # Header info should be in first few lines
                break
                
            line = line.strip()
            
            # Look for content type indicator
            if line.startswith('/!! Content type:'):
                content_type = line.split(':', 1)[1].strip()
                if 'msn' in content_type.lower():
                    file_type = 'MSN'
                elif 'alf' in content_type.lower():
                    file_type = 'ALF'
                elif line.startswith('BS') or line.startswith('HD'):
                    file_type = 'ZTR'
                    
            # Look for sequence number
            elif line.startswith('/!! Sequence:'):
                sequence = line.split(':', 1)[1].strip()
                
            # Look for generation date
            elif line.startswith('/!! Generated:'):
                generated_date = line.split(':', 1)[1].strip()
                
            # Alternative: Look for FILE-SPEC line (MSN format)
            elif line.startswith('A') and 'FILE-SPEC=' in line:
                # Format: A FILE-SPEC=05 1.00 25/11/25 18.08.01 668
                parts = line.split()
                if len(parts) >= 5:
                    generated_date = f"{parts[2]} {parts[3]}"
                    sequence = parts[4] if len(parts) > 4 else sequence
                file_type = 'MSN'
        
        # Fallback: Detect from filename
        if file_type == 'UNKNOWN':
            filename = Path(file_handle.name).name.upper()
            if 'MSN' in filename:
                file_type = 'MSN'
            elif 'ZTR' in filename:
                file_type = 'ZTR'
            elif 'ALF' in filename:
                file_type = 'ALF'
        
        return {
            'file_type': file_type,
            'sequence': sequence,
            'generated_date': generated_date
        }
    
    def _count_data_records(self, file_path: str, file_type: str) -> int:
        """Count the number of data records in the file."""
        count = 0
        
        with open(file_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                    
                # Count based on file type
                if file_type == 'MSN' and line.startswith('A '):
                    count += 1
                elif file_type == 'ZTR' and line.startswith('BS'):
                    count += 1  # Count schedule headers
                elif file_type == 'ALF' and line.startswith('M='):
                    count += 1
                    
        return count


class TimetableImporter:
    """Main importer class for CIF timetable data."""
    
    def __init__(self, db_path: str = "timetable.db"):
        """
        Initialize timetable importer.
        
        Args:
            db_path: Path to SQLite timetable database
        """
        self.db_path = db_path
        self.db = TimetableDatabase(db_path)
        self.version_detector = CIFVersionDetector()
        
        # Connect and ensure schema exists
        self.db.connect()
        self._ensure_import_metadata_table()
        
        logger.info(f"TimetableImporter initialized (DB: {db_path})")
    
    def _ensure_import_metadata_table(self):
        """Create import metadata table if it doesn't exist."""
        cursor = self.db.conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS import_metadata (
                import_id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_type TEXT NOT NULL,
                file_path TEXT NOT NULL,
                file_hash TEXT NOT NULL,
                sequence_number TEXT NOT NULL,
                generated_date TEXT NOT NULL,
                file_size INTEGER NOT NULL,
                record_count INTEGER NOT NULL,
                records_imported INTEGER NOT NULL,
                import_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                import_duration_seconds REAL NOT NULL,
                success BOOLEAN NOT NULL,
                errors TEXT,
                
                UNIQUE(file_hash)
            )
        """)
        
        # Create index separately
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_import_metadata_type_seq 
            ON import_metadata(file_type, sequence_number)
        """)
        
        self.db.conn.commit()
    
    def check_file_already_imported(self, file_info: DataFileInfo) -> bool:
        """
        Check if a file with the same hash has already been imported.
        
        Args:
            file_info: File information to check
            
        Returns:
            True if file already imported, False otherwise
        """
        cursor = self.db.conn.cursor()
        cursor.execute("""
            SELECT import_id, import_date, records_imported 
            FROM import_metadata 
            WHERE file_hash = ? AND success = 1
        """, (file_info.file_hash,))
        
        result = cursor.fetchone()
        if result:
            logger.info(f"File already imported: {file_info.file_type} "
                       f"(imported {result['import_date']}, {result['records_imported']} records)")
            return True
        return False
    
    def import_file(self, file_path: str, force: bool = False) -> ImportResult:
        """
        Import a single CIF file into the database.
        
        Args:
            file_path: Path to CIF file
            force: If True, import even if already imported
            
        Returns:
            ImportResult with import details
        """
        start_time = datetime.now()
        
        try:
            # Analyze file
            file_info = self.version_detector.analyze_file(file_path)
            logger.info(f"Analyzing {file_info.file_type} file: {file_path}")
            logger.info(f"  Sequence: {file_info.sequence}, Generated: {file_info.generated_date}")
            logger.info(f"  Size: {file_info.file_size:,} bytes, Records: {file_info.record_count:,}")
            
            # Check if already imported (unless forced)
            if not force and self.check_file_already_imported(file_info):
                duration = (datetime.now() - start_time).total_seconds()
                return ImportResult(
                    success=True,
                    file_info=file_info,
                    records_imported=0,
                    errors=[],
                    duration_seconds=duration,
                    skipped_reason="Already imported (same file hash)"
                )
            
            # Import based on file type
            if file_info.file_type == 'MSN':
                records_imported, errors = self._import_msn_file(file_path)
            elif file_info.file_type == 'ZTR':
                records_imported, errors = self._import_ztr_file(file_path)
            elif file_info.file_type == 'ALF':
                records_imported, errors = self._import_alf_file(file_path)
            else:
                records_imported = 0
                errors = [f"Unknown file type: {file_info.file_type}"]
            
            duration = (datetime.now() - start_time).total_seconds()
            success = len(errors) == 0
            
            # Record import metadata
            self._record_import_metadata(file_path, file_info, records_imported, 
                                       duration, success, errors)
            
            if success:
                logger.info(f"Successfully imported {records_imported:,} records from {file_info.file_type} file")
            else:
                logger.warning(f"Import completed with {len(errors)} errors")
            
            return ImportResult(
                success=success,
                file_info=file_info,
                records_imported=records_imported,
                errors=errors,
                duration_seconds=duration
            )
            
        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds()
            error_msg = f"Import failed: {str(e)}"
            logger.error(error_msg, exc_info=True)
            
            return ImportResult(
                success=False,
                file_info=DataFileInfo('UNKNOWN', '', '', '', 0, 0),
                records_imported=0,
                errors=[error_msg],
                duration_seconds=duration
            )
    
    def _import_msn_file(self, file_path: str) -> Tuple[int, List[str]]:
        """Import MSN (Master Station Names) file."""
        # MSN files are used by StationResolver, not stored in database
        # We just validate the file can be parsed
        try:
            resolver = StationResolver(file_path)
            station_count = len(resolver.stations)
            
            # Store basic station info in metadata for reference
            cursor = self.db.conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO metadata (key, value)
                VALUES ('station_count', ?), ('msn_last_updated', ?)
            """, (str(station_count), datetime.now().isoformat()))
            self.db.conn.commit()
            
            return station_count, []
            
        except Exception as e:
            return 0, [f"MSN parsing error: {str(e)}"]
    
    def _import_ztr_file(self, file_path: str) -> Tuple[int, List[str]]:
        """Import ZTR (Schedule) file."""
        parser = CIFScheduleParser()
        errors = []
        imported_count = 0
        
        try:
            schedules = parser.parse_file(file_path)
            logger.info(f"Parsed {len(schedules)} schedules from ZTR file")
            
            for schedule_data, locations_data in schedules:
                try:
                    # Convert to database objects
                    train = self._convert_to_scheduled_train(schedule_data)
                    locations = self._convert_to_schedule_locations(locations_data, 0)
                    
                    # Insert into database
                    self.db.insert_schedule(train, locations)
                    imported_count += 1
                    
                except Exception as e:
                    errors.append(f"Schedule {schedule_data.get('train_uid', 'UNKNOWN')}: {str(e)}")
                    if len(errors) > 100:  # Limit error collection
                        errors.append("... (truncated, too many errors)")
                        break
            
            return imported_count, errors
            
        except Exception as e:
            return 0, [f"ZTR parsing error: {str(e)}"]
    
    def _import_alf_file(self, file_path: str) -> Tuple[int, List[str]]:
        """Import ALF (Additional Fixed Links) file."""
        # Note: The ALF format appears to be different than expected
        # For now, we'll implement a simple key=value parser
        errors = []
        imported_count = 0
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    if not line or line.startswith('#') or line.startswith('/'):
                        continue
                    
                    try:
                        connection = self._parse_alf_line(line)
                        if connection:
                            self.db.insert_connection(connection)
                            imported_count += 1
                    except Exception as e:
                        errors.append(f"Line {line_num}: {str(e)}")
                        if len(errors) > 100:
                            break
            
            return imported_count, errors
            
        except Exception as e:
            return 0, [f"ALF parsing error: {str(e)}"]
    
    def _parse_alf_line(self, line: str) -> Optional[StationConnection]:
        """Parse ALF line in key=value format."""
        # Format: M=WALK,O=AFK,D=ASI,T=5,S=0001,E=2359,P=4,R=0000001
        try:
            parts = dict(item.split('=', 1) for item in line.split(','))
            
            mode = parts.get('M', 'WALK')
            from_station = parts.get('O', '')
            to_station = parts.get('D', '')
            duration = int(parts.get('T', 5))
            
            if from_station and to_station:
                return StationConnection(
                    connection_id=0,  # Will be auto-assigned
                    from_station=from_station,
                    to_station=to_station,
                    connection_type=mode,
                    duration_minutes=duration
                )
        except (ValueError, KeyError) as e:
            # Skip malformed lines
            pass
        
        return None
    
    def _convert_to_scheduled_train(self, schedule_data: Dict) -> ScheduledTrain:
        """Convert parsed schedule data to ScheduledTrain object."""
        from datetime import date
        
        # Parse dates
        start_date = self._parse_cif_date(schedule_data.get('start_date', ''))
        end_date = self._parse_cif_date(schedule_data.get('end_date', ''))
        
        return ScheduledTrain(
            schedule_id=0,  # Auto-assigned
            train_uid=schedule_data.get('train_uid', ''),
            train_headcode=schedule_data.get('headcode', ''),
            operator_code=schedule_data.get('atoc_code', '') or schedule_data.get('operator_code', ''),
            service_type=schedule_data.get('train_status', 'P'),
            start_date=start_date or date.today(),
            end_date=end_date or date.today(),
            days_run=schedule_data.get('days_run', '1111111'),
            speed=schedule_data.get('speed'),
            train_class=schedule_data.get('train_class'),
            sleepers=schedule_data.get('sleepers'),
            reservations=schedule_data.get('reservations'),
            catering=schedule_data.get('catering')
        )
    
    def _convert_to_schedule_locations(self, locations_data: List[Dict], schedule_id: int) -> List[ScheduleLocation]:
        """Convert parsed location data to ScheduleLocation objects."""
        locations = []
        
        for i, loc_data in enumerate(locations_data):
            from datetime import time
            
            # Parse times - use public times if available, otherwise scheduled
            arrival_time = self._parse_cif_time(loc_data.get('public_arrival') or loc_data.get('scheduled_arrival'))
            departure_time = self._parse_cif_time(loc_data.get('public_departure') or loc_data.get('scheduled_departure'))
            pass_time = self._parse_cif_time(loc_data.get('scheduled_pass'))
            
            # Determine location type
            location_type = loc_data.get('type', 'LI')
            if i == 0:
                location_type = 'LO'  # Origin
            elif i == len(locations_data) - 1:
                location_type = 'LT'  # Terminus
            
            location = ScheduleLocation(
                location_id=0,  # Auto-assigned
                schedule_id=schedule_id,
                sequence=i,
                tiploc=loc_data.get('tiploc', ''),
                location_type=location_type,
                arrival_time=arrival_time,
                departure_time=departure_time,
                pass_time=pass_time,
                platform=loc_data.get('platform'),
                activities=loc_data.get('activity')
            )
            locations.append(location)
        
        return locations
    
    def _parse_cif_date(self, date_str: str) -> Optional[date]:
        """Parse CIF date format to Python date object."""
        if not date_str:
            return None
        
        try:
            from datetime import date
            
            if '-' in date_str:  # Already ISO format (YYYY-MM-DD)
                year, month, day = map(int, date_str.split('-'))
                return date(year, month, day)
            elif len(date_str) >= 6:  # YYMMDD format
                year = int(date_str[0:2])
                month = int(date_str[2:4])
                day = int(date_str[4:6])
                
                # Handle Y2K
                if year < 50:
                    year += 2000
                else:
                    year += 1900
                
                return date(year, month, day)
        except (ValueError, IndexError):
            pass
        
        return None
    
    def _parse_cif_time(self, time_str: str) -> Optional[time]:
        """Parse CIF time format to Python time object."""
        if not time_str:
            return None
        
        try:
            from datetime import time
            
            if ':' in time_str:  # Already HH:MM format
                hour, minute = map(int, time_str.split(':')[:2])
            else:  # HHMM format
                if len(time_str) < 4:
                    return None
                hour = int(time_str[0:2])
                minute = int(time_str[2:4])
            
            return time(hour, minute)
        except (ValueError, IndexError):
            pass
        
        return None
    
    def _record_import_metadata(self, file_path: str, file_info: DataFileInfo, 
                              records_imported: int, duration: float, 
                              success: bool, errors: List[str]):
        """Record import metadata in database."""
        cursor = self.db.conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO import_metadata (
                file_type, file_path, file_hash, sequence_number, generated_date,
                file_size, record_count, records_imported, import_duration_seconds,
                success, errors
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            file_info.file_type, file_path, file_info.file_hash, 
            file_info.sequence, file_info.generated_date,
            file_info.file_size, file_info.record_count, records_imported, 
            duration, success, '\n'.join(errors) if errors else None
        ))
        self.db.conn.commit()
    
    def import_directory(self, directory_path: str, force: bool = False) -> List[ImportResult]:
        """
        Import all CIF files from a directory.
        
        Args:
            directory_path: Path to directory containing CIF files
            force: If True, import even if already imported
            
        Returns:
            List of ImportResult for each file processed
        """
        results = []
        directory = Path(directory_path)
        
        if not directory.exists():
            raise FileNotFoundError(f"Directory not found: {directory_path}")
        
        # Find CIF files
        cif_files = []
        for pattern in ['*.txt', '*.cif', '*.ztr', '*.msn', '*.alf']:
            cif_files.extend(directory.glob(pattern))
        
        logger.info(f"Found {len(cif_files)} potential CIF files in {directory_path}")
        
        # Import each file
        for file_path in sorted(cif_files):
            logger.info(f"Processing {file_path.name}")
            result = self.import_file(str(file_path), force)
            results.append(result)
        
        return results
    
    def get_import_status(self) -> Dict:
        """Get status of all imports."""
        cursor = self.db.conn.cursor()
        
        # Get summary statistics
        cursor.execute("""
            SELECT 
                file_type,
                COUNT(*) as import_count,
                SUM(records_imported) as total_records,
                MAX(import_date) as last_import,
                AVG(import_duration_seconds) as avg_duration
            FROM import_metadata 
            WHERE success = 1
            GROUP BY file_type
        """)
        
        file_stats = {}
        for row in cursor.fetchall():
            file_stats[row['file_type']] = {
                'import_count': row['import_count'],
                'total_records': row['total_records'],
                'last_import': row['last_import'],
                'avg_duration': round(row['avg_duration'], 2)
            }
        
        # Get database statistics
        db_stats = self.db.get_statistics()
        
        return {
            'file_imports': file_stats,
            'database_stats': db_stats,
            'last_updated': datetime.now().isoformat()
        }
    
    def validate_data(self) -> Dict:
        """Validate imported data integrity."""
        issues = []
        
        # Check for orphaned locations
        cursor = self.db.conn.cursor()
        cursor.execute("""
            SELECT COUNT(*) as orphaned_locations
            FROM schedule_locations sl
            LEFT JOIN schedules s ON sl.schedule_id = s.schedule_id
            WHERE s.schedule_id IS NULL
        """)
        orphaned = cursor.fetchone()['orphaned_locations']
        if orphaned > 0:
            issues.append(f"{orphaned} orphaned schedule locations found")
        
        # Check for schedules without locations
        cursor.execute("""
            SELECT COUNT(*) as empty_schedules
            FROM schedules s
            LEFT JOIN schedule_locations sl ON s.schedule_id = sl.schedule_id
            WHERE sl.schedule_id IS NULL
        """)
        empty = cursor.fetchone()['empty_schedules']
        if empty > 0:
            issues.append(f"{empty} schedules have no locations")
        
        # Check for invalid date ranges
        cursor.execute("""
            SELECT COUNT(*) as invalid_dates
            FROM schedules
            WHERE date(start_date) > date(end_date)
        """)
        invalid_dates = cursor.fetchone()['invalid_dates']
        if invalid_dates > 0:
            issues.append(f"{invalid_dates} schedules have invalid date ranges")
        
        return {
            'validation_date': datetime.now().isoformat(),
            'issues_found': len(issues),
            'issues': issues,
            'is_valid': len(issues) == 0
        }
    
    def close(self):
        """Close database connection."""
        if self.db:
            self.db.close()


if __name__ == '__main__':
    import argparse
    import sys
    import json
    
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    parser = argparse.ArgumentParser(description='CIF Timetable Data Importer')
    parser.add_argument('--db', default='timetable.db', help='Database path')
    parser.add_argument('--directory', help='Directory containing CIF files')
    parser.add_argument('--file', help='Single CIF file to import')
    parser.add_argument('--force', action='store_true', help='Force import even if already imported')
    parser.add_argument('--status', action='store_true', help='Show import status')
    parser.add_argument('--validate', action='store_true', help='Validate imported data')
    parser.add_argument('--verbose', '-v', action='store_true', help='Verbose output')
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    try:
        importer = TimetableImporter(args.db)
        
        if args.status:
            status = importer.get_import_status()
            print(json.dumps(status, indent=2))
        
        elif args.validate:
            validation = importer.validate_data()
            print(json.dumps(validation, indent=2))
            sys.exit(0 if validation['is_valid'] else 1)
        
        elif args.directory:
            results = importer.import_directory(args.directory, args.force)
            
            # Print summary
            successful = sum(1 for r in results if r.success)
            total_records = sum(r.records_imported for r in results)
            
            print(f"\nImport Summary:")
            print(f"Files processed: {len(results)}")
            print(f"Successful imports: {successful}")
            print(f"Total records imported: {total_records:,}")
            
            # Print individual results
            for result in results:
                if result.skipped_reason:
                    print(f"SKIPPED: {result.file_info.file_type} - {result.skipped_reason}")
                elif result.success:
                    print(f"SUCCESS: {result.file_info.file_type} - {result.records_imported:,} records")
                else:
                    print(f"FAILED: {result.file_info.file_type} - {len(result.errors)} errors")
                    for error in result.errors[:3]:  # Show first 3 errors
                        print(f"  {error}")
        
        elif args.file:
            result = importer.import_file(args.file, args.force)
            
            if result.skipped_reason:
                print(f"Skipped: {result.skipped_reason}")
            elif result.success:
                print(f"Successfully imported {result.records_imported:,} records from {result.file_info.file_type}")
            else:
                print(f"Import failed with {len(result.errors)} errors:")
                for error in result.errors:
                    print(f"  {error}")
                sys.exit(1)
        
        else:
            parser.print_help()
        
        importer.close()
        
    except Exception as e:
        logger.error(f"Import failed: {str(e)}", exc_info=True)
        sys.exit(1)