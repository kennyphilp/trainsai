#!/usr/bin/env python3
"""
Production CIF Data Import Script

This script performs a one-time import of CIF timetable data with version tracking
to prevent duplicate imports. It should be run when:

1. Setting up the timetable database for the first time
2. Updating to a new CIF data version
3. Recovering from database corruption

The script includes:
- Automatic version detection from CIF file headers
- Hash-based duplicate prevention
- Progress monitoring and error reporting
- Data validation after import
- Backup creation before import
- Rollback capability on failure

Usage:
    python import_cif_data.py                    # Import all files from ./timetable/
    python import_cif_data.py --force            # Force re-import even if already loaded
    python import_cif_data.py --validate-only    # Just validate existing data
    python import_cif_data.py --status          # Show current import status
"""

import sys
import os
import shutil
import argparse
import logging
from pathlib import Path
from datetime import datetime

# Ensure we can import our modules
sys.path.insert(0, os.getcwd())

from timetable_importer import TimetableImporter


def setup_logging(verbose: bool = False) -> logging.Logger:
    """Configure logging for the import process."""
    log_level = logging.DEBUG if verbose else logging.INFO
    
    # Create logs directory
    Path("logs").mkdir(exist_ok=True)
    
    # Configure logging
    log_file = f"logs/cif_import_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler(sys.stdout)
        ]
    )
    
    logger = logging.getLogger(__name__)
    logger.info(f"Starting CIF import process - log file: {log_file}")
    return logger


def create_backup(db_path: str, logger: logging.Logger) -> str:
    """Create backup of existing database."""
    if not os.path.exists(db_path):
        logger.info("No existing database to backup")
        return None
    
    backup_dir = Path("backups")
    backup_dir.mkdir(exist_ok=True)
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_path = backup_dir / f"timetable_backup_{timestamp}.db"
    
    logger.info(f"Creating database backup: {backup_path}")
    shutil.copy2(db_path, backup_path)
    
    return str(backup_path)


def validate_timetable_directory(directory: str, logger: logging.Logger) -> bool:
    """Validate that the timetable directory contains expected CIF files."""
    timetable_path = Path(directory)
    
    if not timetable_path.exists():
        logger.error(f"Timetable directory not found: {directory}")
        return False
    
    # Look for expected file patterns
    cif_files = list(timetable_path.glob("*.txt")) + list(timetable_path.glob("*.cif"))
    
    if not cif_files:
        logger.error(f"No CIF files found in {directory}")
        return False
    
    logger.info(f"Found {len(cif_files)} CIF files in {directory}")
    
    # Check for expected file types
    has_msn = any("MSN" in f.name.upper() for f in cif_files)
    has_ztr = any("ZTR" in f.name.upper() or "RJTT" in f.name.upper() for f in cif_files)
    has_alf = any("ALF" in f.name.upper() for f in cif_files)
    
    logger.info(f"File types found - MSN: {has_msn}, ZTR: {has_ztr}, ALF: {has_alf}")
    
    if not has_msn:
        logger.warning("No MSN (station names) file found")
    if not has_ztr:
        logger.warning("No ZTR (schedule) files found")
    
    return True


def print_import_summary(results: list, logger: logging.Logger):
    """Print a comprehensive summary of import results."""
    
    print("\n" + "="*80)
    print("CIF DATA IMPORT SUMMARY")
    print("="*80)
    
    total_files = len(results)
    successful = sum(1 for r in results if r.success and not r.skipped_reason)
    skipped = sum(1 for r in results if r.skipped_reason)
    failed = sum(1 for r in results if not r.success)
    total_records = sum(r.records_imported for r in results)
    total_time = sum(r.duration_seconds for r in results)
    
    print(f"Files processed:      {total_files}")
    print(f"Successfully imported: {successful}")
    print(f"Skipped (existing):   {skipped}")
    print(f"Failed:               {failed}")
    print(f"Total records:        {total_records:,}")
    print(f"Total time:           {total_time:.2f}s")
    
    print(f"\nFILE-BY-FILE RESULTS:")
    print(f"{'Type':<4} | {'Status':<25} | {'Records':<10} | {'Time':<8} | {'File Info'}")
    print("-" * 80)
    
    for result in results:
        if result.skipped_reason:
            status = f"SKIPPED ({result.skipped_reason[:15]}...)"
        elif result.success:
            status = "SUCCESS"
        else:
            status = f"FAILED ({len(result.errors)} errors)"
        
        file_info = f"Seq:{result.file_info.sequence} Gen:{result.file_info.generated_date[:10]}"
        
        print(f"{result.file_info.file_type:<4} | {status:<25} | {result.records_imported:>8,} | "
              f"{result.duration_seconds:>6.2f}s | {file_info}")
        
        # Show critical errors
        if not result.success and result.errors:
            for error in result.errors[:2]:  # Show first 2 errors
                print(f"     ❌ {error}")
            if len(result.errors) > 2:
                print(f"     ... and {len(result.errors) - 2} more errors")


def main():
    """Main import process."""
    
    parser = argparse.ArgumentParser(
        description='Import CIF timetable data with version tracking and duplicate prevention',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument('--directory', 
                       default='timetable',
                       help='Directory containing CIF files (default: ./timetable/)')
    parser.add_argument('--database',
                       default='timetable.db', 
                       help='Database file path (default: ./timetable.db)')
    parser.add_argument('--force',
                       action='store_true',
                       help='Force import even if data already exists')
    parser.add_argument('--validate-only',
                       action='store_true',
                       help='Only validate existing data, do not import')
    parser.add_argument('--status',
                       action='store_true', 
                       help='Show current import status and exit')
    parser.add_argument('--verbose', '-v',
                       action='store_true',
                       help='Enable verbose logging')
    parser.add_argument('--no-backup',
                       action='store_true',
                       help='Skip database backup before import')
    
    args = parser.parse_args()
    
    # Setup logging
    logger = setup_logging(args.verbose)
    
    try:
        # Initialize importer
        logger.info(f"Initializing TimetableImporter (DB: {args.database})")
        importer = TimetableImporter(args.database)
        
        # Handle status request
        if args.status:
            logger.info("Retrieving import status...")
            status = importer.get_import_status()
            
            print("\nCURRENT IMPORT STATUS:")
            print("=" * 50)
            
            if status['file_imports']:
                for file_type, stats in status['file_imports'].items():
                    print(f"{file_type}: {stats['total_records']:,} records "
                          f"(last import: {stats['last_import'][:16]})")
            else:
                print("No data has been imported yet")
            
            db_stats = status['database_stats']
            print(f"\nDatabase contains:")
            print(f"  Schedules:   {db_stats['schedules']:,}")
            print(f"  Locations:   {db_stats['locations']:,}")
            print(f"  Connections: {db_stats['connections']:,}")
            
            return 0
        
        # Handle validation request
        if args.validate_only:
            logger.info("Validating existing data...")
            validation = importer.validate_data()
            
            print("\nDATA VALIDATION RESULTS:")
            print("=" * 50)
            
            if validation['is_valid']:
                print("✅ All validation checks passed")
            else:
                print(f"⚠️  Found {validation['issues_found']} issues:")
                for issue in validation['issues']:
                    print(f"   - {issue}")
                
            return 1 if not validation['is_valid'] else 0
        
        # Validate timetable directory
        if not validate_timetable_directory(args.directory, logger):
            return 1
        
        # Create backup unless skipped
        backup_path = None
        if not args.no_backup:
            backup_path = create_backup(args.database, logger)
        
        # Perform import
        logger.info(f"Starting import from {args.directory} (force={args.force})...")
        results = importer.import_directory(args.directory, force=args.force)
        
        # Print results
        print_import_summary(results, logger)
        
        # Get final status
        status = importer.get_import_status()
        db_stats = status['database_stats']
        
        print(f"\nFINAL DATABASE STATE:")
        print(f"{'='*50}")
        print(f"Schedules:   {db_stats['schedules']:,}")
        print(f"Locations:   {db_stats['locations']:,}")
        print(f"Connections: {db_stats['connections']:,}")
        
        # Validate imported data
        print(f"\nDATA VALIDATION:")
        print(f"{'='*50}")
        validation = importer.validate_data()
        
        if validation['is_valid']:
            print("✅ Data validation passed")
            if backup_path:
                print(f"\n💾 Database backup available at: {backup_path}")
                print("   (You can delete this backup once you've confirmed the import is working correctly)")
        else:
            print(f"⚠️  Data validation found {validation['issues_found']} issues:")
            for issue in validation['issues']:
                print(f"   - {issue}")
            
            if backup_path:
                print(f"\n🔄 Database backup available for rollback at: {backup_path}")
                print("   Consider restoring from backup if these issues are critical")
        
        # Determine success
        successful_imports = sum(1 for r in results if r.success and not r.skipped_reason)
        if successful_imports > 0:
            logger.info(f"Import completed successfully - {successful_imports} files imported")
            return 0
        else:
            logger.error("No files were successfully imported")
            return 1
            
    except KeyboardInterrupt:
        logger.warning("Import interrupted by user")
        return 1
    except Exception as e:
        logger.error(f"Import failed with exception: {str(e)}", exc_info=True)
        return 1
    finally:
        if 'importer' in locals():
            importer.close()


if __name__ == "__main__":
    sys.exit(main())