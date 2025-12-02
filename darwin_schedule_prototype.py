#!/usr/bin/env python3
"""
Darwin Schedule Storage Prototype (Option 1)

This prototype implements schedule-based enrichment for Darwin cancellations:
1. Captures and stores Darwin schedule messages in SQLite database
2. Enriches cancellation messages with stored schedule data
3. Provides detailed cancellation logging with full train information

Architecture:
- Schedule Storage: SQLite database with train schedules indexed by RID
- Real-time Processing: Enriches cancellations using stored schedule data
- Data Persistence: Maintains schedule data across sessions
- Cleanup: Automatic removal of old schedule data

Usage: python darwin_schedule_prototype.py
"""

import gzip
import json
import logging
import sqlite3
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import stomp
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('darwin_schedule_prototype.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)


class DarwinScheduleDatabase:
    """
    SQLite database for storing and retrieving Darwin schedule data.
    """
    
    def __init__(self, db_path: str = "darwin_schedules.db"):
        self.db_path = db_path
        self.conn = None
        self._init_database()
    
    def _init_database(self):
        """Initialize database schema."""
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.conn.execute("PRAGMA foreign_keys = ON")
        
        # Create schedules table
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS schedules (
                rid TEXT PRIMARY KEY,
                uid TEXT,
                train_id TEXT,
                headcode TEXT,
                toc TEXT,
                status TEXT,
                category TEXT,
                origin_tiploc TEXT,
                origin_time TEXT,
                origin_platform TEXT,
                destination_tiploc TEXT,
                destination_time TEXT,
                destination_platform TEXT,
                start_date TEXT,
                end_date TEXT,
                days_run TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Create calling points table
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS calling_points (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                rid TEXT,
                tiploc TEXT,
                location_type TEXT,
                platform TEXT,
                arrival_time TEXT,
                departure_time TEXT,
                pass_time TEXT,
                activities TEXT,
                sequence INTEGER,
                FOREIGN KEY (rid) REFERENCES schedules(rid) ON DELETE CASCADE
            )
        """)
        
        # Create indexes for performance
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_schedules_rid ON schedules(rid)")
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_schedules_uid ON schedules(uid)")
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_schedules_toc ON schedules(toc)")
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_calling_points_rid ON calling_points(rid)")
        
        self.conn.commit()
        logger.info("✅ Darwin schedule database initialized")
    
    def store_schedule(self, schedule_data: Dict) -> bool:
        """Store a complete schedule in the database."""
        try:
            # Insert or update main schedule
            self.conn.execute("""
                INSERT OR REPLACE INTO schedules (
                    rid, uid, train_id, headcode, toc, status, category,
                    origin_tiploc, origin_time, origin_platform,
                    destination_tiploc, destination_time, destination_platform,
                    start_date, end_date, days_run, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """, (
                schedule_data['rid'],
                schedule_data.get('uid'),
                schedule_data.get('train_id'),
                schedule_data.get('headcode'),
                schedule_data.get('toc'),
                schedule_data.get('status'),
                schedule_data.get('category'),
                schedule_data.get('origin_tiploc'),
                schedule_data.get('origin_time'),
                schedule_data.get('origin_platform'),
                schedule_data.get('destination_tiploc'),
                schedule_data.get('destination_time'),
                schedule_data.get('destination_platform'),
                schedule_data.get('start_date'),
                schedule_data.get('end_date'),
                schedule_data.get('days_run')
            ))
            
            # Clear existing calling points and insert new ones
            self.conn.execute("DELETE FROM calling_points WHERE rid = ?", (schedule_data['rid'],))
            
            for point in schedule_data.get('calling_points', []):
                self.conn.execute("""
                    INSERT INTO calling_points (
                        rid, tiploc, location_type, platform,
                        arrival_time, departure_time, pass_time,
                        activities, sequence
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    schedule_data['rid'],
                    point.get('tiploc'),
                    point.get('type'),
                    point.get('platform'),
                    point.get('arrival_time'),
                    point.get('departure_time'),
                    point.get('pass_time'),
                    point.get('activities'),
                    point.get('sequence')
                ))
            
            self.conn.commit()
            return True
            
        except Exception as e:
            logger.error(f"Error storing schedule {schedule_data.get('rid', 'unknown')}: {e}")
            return False
    
    def get_schedule(self, rid: str) -> Optional[Dict]:
        """Retrieve schedule data by RID."""
        try:
            cursor = self.conn.cursor()
            
            # Get main schedule data
            cursor.execute("""
                SELECT * FROM schedules WHERE rid = ?
            """, (rid,))
            
            row = cursor.fetchone()
            if not row:
                return None
            
            columns = [desc[0] for desc in cursor.description]
            schedule = dict(zip(columns, row))
            
            # Get calling points
            cursor.execute("""
                SELECT * FROM calling_points WHERE rid = ? ORDER BY sequence
            """, (rid,))
            
            points = []
            for point_row in cursor.fetchall():
                point_columns = [desc[0] for desc in cursor.description]
                point = dict(zip(point_columns, point_row))
                points.append(point)
            
            schedule['calling_points'] = points
            return schedule
            
        except Exception as e:
            logger.error(f"Error retrieving schedule {rid}: {e}")
            return None
    
    def cleanup_old_schedules(self, days_old: int = 7):
        """Remove schedules older than specified days."""
        try:
            cutoff = datetime.now() - timedelta(days=days_old)
            
            cursor = self.conn.cursor()
            cursor.execute("""
                DELETE FROM schedules WHERE created_at < ?
            """, (cutoff.isoformat(),))
            
            deleted_count = cursor.rowcount
            self.conn.commit()
            
            logger.info(f"🧹 Cleaned up {deleted_count} old schedules (older than {days_old} days)")
            return deleted_count
            
        except Exception as e:
            logger.error(f"Error cleaning up old schedules: {e}")
            return 0
    
    def get_statistics(self) -> Dict:
        """Get database statistics."""
        try:
            cursor = self.conn.cursor()
            
            # Count schedules
            cursor.execute("SELECT COUNT(*) FROM schedules")
            schedule_count = cursor.fetchone()[0]
            
            # Count calling points
            cursor.execute("SELECT COUNT(*) FROM calling_points")
            points_count = cursor.fetchone()[0]
            
            # Count unique TOCs
            cursor.execute("SELECT COUNT(DISTINCT toc) FROM schedules WHERE toc IS NOT NULL")
            toc_count = cursor.fetchone()[0]
            
            # Database file size
            db_size = Path(self.db_path).stat().st_size if Path(self.db_path).exists() else 0
            
            return {
                'schedule_count': schedule_count,
                'calling_points_count': points_count,
                'unique_tocs': toc_count,
                'database_size_mb': round(db_size / (1024 * 1024), 2)
            }
            
        except Exception as e:
            logger.error(f"Error getting database statistics: {e}")
            return {}
    
    def close(self):
        """Close database connection."""
        if self.conn:
            self.conn.close()


class DarwinScheduleProcessor:
    """
    Processes Darwin messages for schedule storage and cancellation enrichment.
    """
    
    def __init__(self, database: DarwinScheduleDatabase):
        self.database = database
        self.stats = {
            'messages_processed': 0,
            'schedules_stored': 0,
            'cancellations_detected': 0,
            'cancellations_enriched': 0,
            'errors': 0
        }
    
    def process_darwin_message(self, xml_content: str) -> Dict:
        """Process a single Darwin XML message."""
        try:
            self.stats['messages_processed'] += 1
            root = ET.fromstring(xml_content)
            
            result = {
                'schedules_processed': 0,
                'cancellations_processed': 0,
                'errors': []
            }
            
            # Define namespace
            ns = {'ns': 'http://www.thalesgroup.com/rtti/PushPort/v16'}
            
            # Process schedule messages
            schedules = root.findall('.//ns:schedule', ns)
            for schedule in schedules:
                if self._process_schedule(schedule, ns):
                    result['schedules_processed'] += 1
                    self.stats['schedules_stored'] += 1
            
            # Process cancellations (deactivated elements)
            deactivated = root.findall('.//ns:deactivated', ns)
            for cancel in deactivated:
                cancellation_result = self._process_cancellation(cancel, root, ns)
                if cancellation_result:
                    result['cancellations_processed'] += 1
                    self.stats['cancellations_detected'] += 1
                    
                    if cancellation_result.get('enriched'):
                        self.stats['cancellations_enriched'] += 1
            
            return result
            
        except Exception as e:
            self.stats['errors'] += 1
            logger.error(f"Error processing Darwin message: {e}")
            return {'error': str(e)}
    
    def _process_schedule(self, schedule_elem, ns: Dict) -> bool:
        """Process a schedule element and store in database."""
        try:
            schedule_data = {
                'rid': schedule_elem.get('rid'),
                'uid': schedule_elem.get('uid'),
                'train_id': schedule_elem.get('trainId'),
                'headcode': schedule_elem.get('headcode'),
                'toc': schedule_elem.get('toc'),
                'status': schedule_elem.get('status'),
                'category': schedule_elem.get('trainCat'),
                'start_date': schedule_elem.get('ssd'),
                'end_date': schedule_elem.get('endDate'),
                'days_run': schedule_elem.get('daysRun'),
                'calling_points': []
            }
            
            # Detailed field logging
            logger.info(f"📦 Processing Schedule: RID={schedule_data['rid']}")
            logger.info(f"   🚂 Train: {schedule_data['train_id']} | Headcode: {schedule_data['headcode']}")
            logger.info(f"   🏢 TOC: {schedule_data['toc']} | Category: {schedule_data['category']}")
            logger.info(f"   📅 Period: {schedule_data['start_date']} to {schedule_data['end_date']}")
            logger.info(f"   🗓️  Days: {schedule_data['days_run']} | Status: {schedule_data['status']}")
            
            # Extract origin (OR element)
            origin = schedule_elem.find('.//ns:OR', ns)
            if origin is not None:
                origin_data = {
                    'origin_tiploc': origin.get('tpl'),
                    'origin_time': origin.get('wtd') or origin.get('wd'),
                    'origin_platform': origin.get('plat')
                }
                schedule_data.update(origin_data)
                logger.info(f"   🚀 Origin: {origin_data['origin_tiploc']} at {origin_data['origin_time']}")
                if origin_data['origin_platform']:
                    logger.info(f"      Platform: {origin_data['origin_platform']}")
            
            # Extract destination (DT element) 
            destination = schedule_elem.find('.//ns:DT', ns)
            if destination is not None:
                dest_data = {
                    'destination_tiploc': destination.get('tpl'),
                    'destination_time': destination.get('wta') or destination.get('pta'),
                    'destination_platform': destination.get('plat')
                }
                schedule_data.update(dest_data)
                logger.info(f"   🏁 Destination: {dest_data['destination_tiploc']} at {dest_data['destination_time']}")
                if dest_data['destination_platform']:
                    logger.info(f"      Platform: {dest_data['destination_platform']}")
            
            # Extract calling points (IP elements)
            calling_points = schedule_elem.findall('.//ns:IP', ns)
            logger.info(f"   📍 Processing {len(calling_points)} calling points:")
            
            for i, cp in enumerate(calling_points, 1):
                calling_point = {
                    'tiploc': cp.get('tpl'),
                    'arrival': cp.get('wta') or cp.get('pta'),
                    'departure': cp.get('wtd') or cp.get('ptd'),
                    'platform': cp.get('plat'),
                    'activity': cp.get('act')
                }
                schedule_data['calling_points'].append(calling_point)
                
                # Log first few and last few calling points for visibility
                if i <= 3 or i > len(calling_points) - 3:
                    times = []
                    if calling_point['arrival']:
                        times.append(f"arr: {calling_point['arrival']}")
                    if calling_point['departure']:
                        times.append(f"dep: {calling_point['departure']}")
                    time_str = " | ".join(times) if times else "pass"
                    
                    platform_str = f" (P{calling_point['platform']})" if calling_point['platform'] else ""
                    activity_str = f" [{calling_point['activity']}]" if calling_point['activity'] else ""
                    
                    logger.info(f"      {i:2d}. {calling_point['tiploc']}{platform_str}: {time_str}{activity_str}")
                elif i == 4 and len(calling_points) > 6:
                    logger.info(f"      ... ({len(calling_points) - 6} more calling points) ...")
            
            # Store in database
            success = self.database.store_schedule(schedule_data)
            if success:
                self.stats['schedules_stored'] += 1
                logger.info(f"   ✅ Schedule stored successfully with {len(schedule_data['calling_points'])} calling points")
                return True
            else:
                logger.error(f"   ❌ Failed to store schedule: {schedule_data['rid']}")
                return False
            
        except Exception as e:
            logger.error(f"Error processing schedule: {e}")
            return False
    
    def _process_cancellation(self, cancel_elem, root_elem, ns: Dict) -> Optional[Dict]:
        """Process a cancellation and enrich with schedule data."""
        try:
            rid = cancel_elem.get('rid')
            if not rid:
                return None
            
            logger.info(f"🚨 ========== CANCELLATION DETECTED ===========")
            logger.info(f"🚫 RID: {rid}")
            
            # Get all available cancellation fields
            cancellation = {
                'rid': rid,
                'uid': cancel_elem.get('uid'),
                'train_id': cancel_elem.get('trainId'),
                'headcode': cancel_elem.get('headcode'),
                'toc': cancel_elem.get('toc'),
                'status': cancel_elem.get('status'),
                'category': cancel_elem.get('trainCat'),
                'timestamp': datetime.now().isoformat(),
                'enriched': False
            }
            
            # Log basic cancellation fields
            logger.info(f"📋 Basic Cancellation Data:")
            for key, value in cancellation.items():
                if value and key not in ['timestamp', 'enriched']:
                    logger.info(f"   {key}: {value}")
            logger.info(f"   timestamp: {cancellation['timestamp']}")
            
            # Try to enrich with stored schedule data
            logger.info(f"🔍 Searching for schedule data in database...")
            schedule = self.database.get_schedule(rid)
            
            if schedule:
                logger.info(f"✅ SCHEDULE FOUND! Enriching cancellation data...")
                logger.info(f"📊 Schedule Data Retrieved:")
                
                # Show comparison between basic and enriched data
                enrichment_data = {
                    'train_id': schedule.get('train_id'),
                    'headcode': schedule.get('headcode'),
                    'toc': schedule.get('toc'),
                    'origin_tiploc': schedule.get('origin_tiploc'),
                    'origin_time': schedule.get('origin_time'),
                    'origin_platform': schedule.get('origin_platform'),
                    'destination_tiploc': schedule.get('destination_tiploc'),
                    'destination_time': schedule.get('destination_time'),
                    'destination_platform': schedule.get('destination_platform'),
                    'category': schedule.get('category'),
                    'status': schedule.get('status'),
                    'start_date': schedule.get('start_date'),
                    'calling_points_count': len(schedule.get('calling_points', []))
                }
                
                cancellation.update(enrichment_data)
                cancellation['enriched'] = True
                
                # Show enrichment details
                logger.info(f"🎯 ENRICHMENT SUCCESSFUL:")
                logger.info(f"   🚂 Train: {enrichment_data['train_id']} ({enrichment_data['headcode']})")
                logger.info(f"   🏢 Operator: {enrichment_data['toc']}")
                logger.info(f"   📅 Service Date: {enrichment_data['start_date']}")
                logger.info(f"   🚀 Origin: {enrichment_data['origin_tiploc']} at {enrichment_data['origin_time']}")
                if enrichment_data['origin_platform']:
                    logger.info(f"      Platform: {enrichment_data['origin_platform']}")
                logger.info(f"   🏁 Destination: {enrichment_data['destination_tiploc']} at {enrichment_data['destination_time']}")
                if enrichment_data['destination_platform']:
                    logger.info(f"      Platform: {enrichment_data['destination_platform']}")
                logger.info(f"   📍 Journey: {enrichment_data['calling_points_count']} calling points")
                logger.info(f"   📋 Category: {enrichment_data['category']} | Status: {enrichment_data['status']}")
                
                # Log enriched cancellation
                self._log_enriched_cancellation(cancellation, schedule)
            else:
                logger.warning(f"❌ NO SCHEDULE DATA FOUND for RID: {rid}")
                logger.warning(f"   This cancellation cannot be enriched")
                logger.warning(f"   Only basic cancellation data available")
                # Log basic cancellation
                self._log_basic_cancellation(cancellation)
            
            logger.info(f"===============================================")
            return cancellation
            
        except Exception as e:
            logger.error(f"Error processing cancellation: {e}")
            return None
    
    def _log_enriched_cancellation(self, cancellation: Dict, schedule: Dict):
        """Log detailed cancellation with full schedule data."""
        # Enhanced pipe-delimited format with all available data
        log_entry = (
            f"ENRICHED_CANCELLATION|{cancellation['rid']}|{cancellation.get('uid', 'N/A')}|"
            f"{cancellation.get('train_id', 'N/A')}|{cancellation.get('headcode', 'N/A')}|"
            f"{cancellation.get('toc', 'N/A')}|{cancellation.get('category', 'N/A')}|"
            f"{cancellation.get('origin_tiploc', 'N/A')}|{cancellation.get('origin_time', 'N/A')}|"
            f"{cancellation.get('origin_platform', 'N/A')}|"
            f"{cancellation.get('destination_tiploc', 'N/A')}|{cancellation.get('destination_time', 'N/A')}|"
            f"{cancellation.get('destination_platform', 'N/A')}|"
            f"{cancellation.get('calling_points_count', 0)}|{cancellation['timestamp']}"
        )
        
        logger.info(log_entry)
        
        # Also log to separate enriched cancellations file
        with open('enriched_cancellations.log', 'a') as f:
            f.write(log_entry + '\n')
        
        # Console output with rich formatting
        print(f"\n🚫 ENRICHED CANCELLATION:")
        print(f"   RID: {cancellation['rid']}")
        print(f"   Train: {cancellation.get('headcode', 'N/A')} ({cancellation.get('train_id', 'N/A')})")
        print(f"   Operator: {cancellation.get('toc', 'N/A')} - {cancellation.get('category', 'N/A')}")
        print(f"   Route: {cancellation.get('origin_tiploc', 'N/A')} → {cancellation.get('destination_tiploc', 'N/A')}")
        print(f"   Timing: {cancellation.get('origin_time', 'N/A')} - {cancellation.get('destination_time', 'N/A')}")
        print(f"   Platforms: {cancellation.get('origin_platform', 'N/A')} → {cancellation.get('destination_platform', 'N/A')}")
        print(f"   Stops: {cancellation.get('calling_points_count', 0)} calling points")
        print(f"   Detected: {cancellation['timestamp']}")
        print("   🎯 FULL ENRICHMENT SUCCESS")
        print("-" * 70)
    
    def _log_basic_cancellation(self, cancellation: Dict):
        """Log basic cancellation without schedule enrichment."""
        log_entry = (
            f"BASIC_CANCELLATION|{cancellation['rid']}|{cancellation.get('uid', 'N/A')}|"
            f"NO_SCHEDULE_DATA|{cancellation['timestamp']}"
        )
        
        logger.info(log_entry)
        
        print(f"\n🚫 BASIC CANCELLATION:")
        print(f"   RID: {cancellation['rid']}")
        print(f"   UID: {cancellation.get('uid', 'N/A')}")
        print(f"   Detected: {cancellation['timestamp']}")
        print("   ⚠️  No schedule data available for enrichment")
        print("-" * 50)
    
    def get_statistics(self) -> Dict:
        """Get processing statistics."""
        enrichment_rate = 0
        if self.stats['cancellations_detected'] > 0:
            enrichment_rate = (self.stats['cancellations_enriched'] / self.stats['cancellations_detected']) * 100
        
        return {
            **self.stats,
            'enrichment_rate': round(enrichment_rate, 1)
        }
    
    def get_detailed_statistics(self) -> Dict:
        """Get detailed processing statistics with database info."""
        basic_stats = self.get_statistics()
        db_stats = self.database.get_statistics()
        
        return {
            **basic_stats,
            'database': {
                'total_schedules': db_stats['schedule_count'],
                'total_calling_points': db_stats['calling_points_count'],
                'unique_operators': db_stats['unique_tocs'],
                'database_size_mb': db_stats['database_size_mb']
            },
            'processing_efficiency': {
                'schedules_per_message': round(basic_stats['schedules_stored'] / max(basic_stats['messages_processed'], 1), 2),
                'cancellations_per_message': round(basic_stats['cancellations_detected'] / max(basic_stats['messages_processed'], 1), 4),
                'success_rate': f"{basic_stats['enrichment_rate']}%"
            }
        }


class DarwinScheduleListener(stomp.ConnectionListener):
    """
    STOMP listener for Darwin Push Port with schedule storage capability.
    """
    
    def __init__(self, processor: DarwinScheduleProcessor, max_messages: int = None):
        self.processor = processor
        self.max_messages = max_messages
        self.message_count = 0
    
    def on_connected(self, frame):
        logger.info("✅ Connected to Darwin Push Port - Schedule Storage Active")
        print("🔄 Darwin Schedule Processor running...")
        print("   📦 Storing schedule messages for enrichment")
        print("   🚫 Detecting and enriching cancellations")
        print("   📊 Statistics available in real-time")
        print()
    
    def on_disconnected(self):
        logger.warning("⚠️  Disconnected from Darwin Push Port")
    
    def on_error(self, frame):
        logger.error(f"STOMP error: {frame.body}")
    
    def on_message(self, frame):
        if self.max_messages and self.message_count >= self.max_messages:
            logger.info(f"Reached message limit of {self.max_messages}")
            return
        
        try:
            self.message_count += 1
            
            # Decompress message
            body = frame.body
            if isinstance(body, str):
                body = body.encode('utf-8')
            
            try:
                # Handle different message formats
                if body.startswith(b'\x1f\x8b'):  # Valid gzip header
                    decompressed = gzip.decompress(body)
                elif body.startswith(b'<?xml'):  # Already XML
                    decompressed = body
                else:
                    # Try to decode and check if it's XML
                    try:
                        text = body.decode('utf-8')
                        if text.strip().startswith('<?xml'):
                            decompressed = body
                        else:
                            logger.debug(f"Skipping message #{self.message_count}: Not XML format")
                            return
                    except:
                        logger.debug(f"Skipping message #{self.message_count}: Cannot decode")
                        return
                        
            except Exception as e:
                # Skip non-gzipped or corrupted messages
                logger.debug(f"Skipping message #{self.message_count}: {e}")
                return
            
            # Process the message
            result = self.processor.process_darwin_message(decompressed.decode('utf-8'))
            
            # Show detailed progress every 25 messages
            if self.message_count % 25 == 0:
                detailed_stats = self.processor.get_detailed_statistics()
                
                print(f"\n📊 ========== PROGRESS UPDATE (Message #{self.message_count}) ===========")
                print(f"📨 Messages processed: {detailed_stats['messages_processed']}")
                print(f"📦 Schedules stored: {detailed_stats['schedules_stored']}")
                print(f"🚫 Cancellations detected: {detailed_stats['cancellations_detected']}")
                print(f"🎯 Cancellations enriched: {detailed_stats['cancellations_enriched']}")
                print(f"📈 Enrichment success rate: {detailed_stats['enrichment_rate']}%")
                print(f"❌ Processing errors: {detailed_stats['errors']}")
                print(f"")
                print(f"💾 DATABASE STATUS:")
                db = detailed_stats['database']
                print(f"   📋 Total schedules: {db['total_schedules']}")
                print(f"   📍 Calling points: {db['total_calling_points']}")
                print(f"   🚂 Unique operators: {db['unique_operators']}")
                print(f"   💽 Database size: {db['database_size_mb']} MB")
                print(f"")
                print(f"⚡ PROCESSING EFFICIENCY:")
                eff = detailed_stats['processing_efficiency']
                print(f"   📦 Schedules per message: {eff['schedules_per_message']}")
                print(f"   🚫 Cancellations per message: {eff['cancellations_per_message']}")
                print(f"   ✅ Overall success rate: {eff['success_rate']}")
                print(f"================================================================")
        
        except Exception as e:
            logger.error(f"Error processing message #{self.message_count}: {e}")


async def main():
    """Main execution function."""
    print("="*80)
    print("🚂 Darwin Schedule Storage Prototype (Option 1)")
    print("="*80)
    print("Features:")
    print("• 📦 Real-time schedule message capture and storage")
    print("• 🚫 Cancellation detection with schedule-based enrichment")
    print("• 💾 SQLite database for persistent schedule data")
    print("• 📊 Comprehensive logging and statistics")
    print("• 🧹 Automatic cleanup of old schedule data")
    print()
    print("This prototype demonstrates full Option 1 functionality.")
    print("Press Ctrl+C to stop and view final statistics.")
    print("="*80)
    
    # Initialize components
    database = DarwinScheduleDatabase()
    processor = DarwinScheduleProcessor(database)
    listener = DarwinScheduleListener(processor)
    
    # Clean up old data on startup
    database.cleanup_old_schedules(days_old=7)
    
    # Darwin connection setup
    host = "darwin-dist-44ae45.nationalrail.co.uk"
    port = 61613
    username = "DARWINc7af8eb3-ad92-4869-8682-af701f2ce953"
    password = "022d5ca4-c7b3-4190-a64e-a679c211f3eb"
    topic = "/topic/darwin.pushport-v16"
    
    # Connect to Darwin
    conn = stomp.Connection([(host, port)])
    conn.set_listener('', listener)
    
    try:
        conn.connect(username, password, wait=True)
        conn.subscribe(destination=topic, id=1, ack='auto')
        
        # Keep running until interrupted
        import asyncio
        while True:
            await asyncio.sleep(1)
    
    except KeyboardInterrupt:
        print(f"\n⏹️  Stopped by user after {listener.message_count} messages")
    
    except Exception as e:
        print(f"\n❌ Error: {e}")
    
    finally:
        # Disconnect and show final statistics
        if 'conn' in locals():
            conn.disconnect()
        
        # Final statistics
        stats = processor.get_statistics()
        db_stats = database.get_statistics()
        
        print("\n" + "="*80)
        print("📈 FINAL STATISTICS")
        print("="*80)
        print(f"📨 Messages processed: {stats['messages_processed']}")
        print(f"📦 Schedules stored: {stats['schedules_stored']}")
        print(f"🚫 Cancellations detected: {stats['cancellations_detected']}")
        print(f"🎯 Cancellations enriched: {stats['cancellations_enriched']}")
        print(f"📊 Enrichment success rate: {stats['enrichment_rate']}%")
        print(f"❌ Processing errors: {stats['errors']}")
        print()
        print("💾 DATABASE STATISTICS:")
        print(f"   📋 Total schedules: {db_stats['schedule_count']}")
        print(f"   📍 Calling points: {db_stats['calling_points_count']}")
        print(f"   🚂 Unique operators: {db_stats['unique_tocs']}")
        print(f"   💽 Database size: {db_stats['database_size_mb']} MB")
        print()
        print("📁 Output Files:")
        print("   • darwin_schedule_prototype.log - Detailed processing log")
        print("   • enriched_cancellations.log - Enriched cancellation data")
        print("   • darwin_schedules.db - Schedule database")
        print("="*80)
        
        # Close database
        database.close()
        
        print("🎯 Option 1 Prototype Complete!")
        print("Schedule-based enrichment demonstrates full functionality.")


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())