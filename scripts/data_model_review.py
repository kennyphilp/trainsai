#!/usr/bin/env python3
"""
Comprehensive Data Model Quality Review
=====================================

This script analyzes the current railway timetable database structure,
identifies strengths and weaknesses, and provides recommendations for improvements.
"""

import sqlite3
import json
from collections import defaultdict

def connect_db():
    """Connect to the SQLite database."""
    return sqlite3.connect('timetable.db')

def analyze_table_relationships():
    """Analyze foreign key relationships and referential integrity."""
    db = sqlite3.connect('timetable.db')
    cursor = db.cursor()
    
    print("=== FOREIGN KEY RELATIONSHIPS ANALYSIS ===\n")
    
    # Check all foreign key constraints
    cursor.execute("PRAGMA foreign_keys = ON")
    
    # Get all tables with foreign keys
    tables_with_fk = [
        'schedule_locations',
        'station_aliases', 
        'tiploc_mappings',
        'place_name_mappings'
    ]
    
    integrity_issues = 0
    
    for table in tables_with_fk:
        cursor.execute(f"PRAGMA foreign_key_check({table})")
        violations = cursor.fetchall()
        if violations:
            print(f"❌ Foreign key violations in {table}: {len(violations)}")
            integrity_issues += violations.__len__()
        else:
            print(f"✅ {table}: No foreign key violations")
    
    # Check orphaned records
    print("\n--- Orphaned Records Check ---")
    
    # Check schedule_locations without schedules
    cursor.execute("""
        SELECT COUNT(*) 
        FROM schedule_locations sl 
        LEFT JOIN schedules s ON sl.schedule_id = s.schedule_id 
        WHERE s.schedule_id IS NULL
    """)
    orphaned_locations = cursor.fetchone()[0]
    print(f"Orphaned schedule locations: {orphaned_locations}")
    
    # Check station_aliases without stations
    cursor.execute("""
        SELECT COUNT(*) 
        FROM station_aliases sa 
        LEFT JOIN stations s ON sa.station_id = s.station_id 
        WHERE s.station_id IS NULL
    """)
    orphaned_aliases = cursor.fetchone()[0]
    print(f"Orphaned station aliases: {orphaned_aliases}")
    
    db.close()
    return integrity_issues + orphaned_locations + orphaned_aliases

def analyze_data_consistency():
    """Check for data consistency issues across tables."""
    db = sqlite3.connect('timetable.db')
    cursor = db.cursor()
    
    print("\n=== DATA CONSISTENCY ANALYSIS ===\n")
    
    consistency_issues = 0
    
    # Check TIPLOC consistency between stations and schedule_locations
    cursor.execute("""
        SELECT DISTINCT sl.tiploc 
        FROM schedule_locations sl 
        LEFT JOIN stations s ON sl.tiploc = s.tiploc 
        WHERE s.tiploc IS NULL
    """)
    missing_tiplocs = cursor.fetchall()
    print(f"TIPLOCs in schedule_locations but not in stations: {len(missing_tiplocs)}")
    if missing_tiplocs and len(missing_tiplocs) < 10:
        for tiploc in missing_tiplocs[:5]:
            print(f"  - {tiploc[0]}")
    consistency_issues += len(missing_tiplocs)
    
    # Check time data consistency
    cursor.execute("""
        SELECT COUNT(*) 
        FROM schedule_locations 
        WHERE arrival_seconds < 0 OR departure_seconds < 0 OR pass_seconds < 0
    """)
    invalid_times = cursor.fetchone()[0]
    print(f"Invalid negative time values: {invalid_times}")
    consistency_issues += invalid_times
    
    # Check for impossible time sequences (arrival > departure)
    cursor.execute("""
        SELECT COUNT(*) 
        FROM schedule_locations 
        WHERE arrival_seconds IS NOT NULL 
        AND departure_seconds IS NOT NULL 
        AND arrival_seconds > departure_seconds
    """)
    impossible_times = cursor.fetchone()[0]
    print(f"Impossible time sequences (arrival > departure): {impossible_times}")
    consistency_issues += impossible_times
    
    # Check duplicate schedules
    cursor.execute("""
        SELECT train_uid, start_date, stp_indicator, COUNT(*) 
        FROM schedules 
        GROUP BY train_uid, start_date, stp_indicator 
        HAVING COUNT(*) > 1
    """)
    duplicate_schedules = cursor.fetchall()
    print(f"Duplicate schedule entries: {len(duplicate_schedules)}")
    consistency_issues += len(duplicate_schedules)
    
    db.close()
    return consistency_issues

def analyze_normalization():
    """Evaluate database normalization and design principles."""
    db = sqlite3.connect('timetable.db')
    cursor = db.cursor()
    
    print("\n=== NORMALIZATION ANALYSIS ===\n")
    
    normalization_issues = []
    
    # Check for denormalized data in stations table
    cursor.execute("""
        SELECT country, region, COUNT(DISTINCT operator_code) as operators
        FROM stations 
        WHERE country IS NOT NULL AND region IS NOT NULL
        GROUP BY country, region
        HAVING operators > 1
    """)
    mixed_operators = cursor.fetchall()
    if mixed_operators:
        normalization_issues.append(f"Mixed operators in regions: {len(mixed_operators)}")
    
    # Check for repeated data in schedule_locations
    cursor.execute("""
        SELECT activities, COUNT(*) as frequency
        FROM schedule_locations 
        WHERE activities IS NOT NULL
        GROUP BY activities
        ORDER BY frequency DESC
        LIMIT 10
    """)
    activities_data = cursor.fetchall()
    print("Most common activity patterns (denormalized text):")
    for activity, count in activities_data:
        print(f"  {activity}: {count:,} occurrences")
    
    # Check place_name_mappings usage
    cursor.execute("SELECT COUNT(*) FROM place_name_mappings")
    place_mappings_count = cursor.fetchone()[0]
    if place_mappings_count == 0:
        normalization_issues.append("place_name_mappings table is empty")
    
    print(f"\nNormalization issues identified: {len(normalization_issues)}")
    for issue in normalization_issues:
        print(f"  - {issue}")
    
    db.close()
    return len(normalization_issues)

def analyze_indexing_performance():
    """Analyze index coverage and potential performance issues."""
    db = sqlite3.connect('timetable.db')
    cursor = db.cursor()
    
    print("\n=== INDEXING AND PERFORMANCE ANALYSIS ===\n")
    
    # Count total indexes
    cursor.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='index' AND name LIKE 'idx_%'")
    index_count = cursor.fetchone()[0]
    print(f"Custom indexes: {index_count}")
    
    # Check table sizes vs index coverage
    cursor.execute("SELECT COUNT(*) FROM schedule_locations")
    large_table_size = cursor.fetchone()[0]
    print(f"Largest table (schedule_locations): {large_table_size:,} records")
    
    # Performance recommendations
    performance_issues = []
    
    # Check if critical query patterns are covered
    critical_patterns = [
        ("tiploc + time range queries", "idx_arrival_time_search, idx_departure_time_search"),
        ("operator + date range", "idx_operator_date_range"),
        ("schedule lookup", "idx_service_lookup"),
        ("geographical hierarchy", "idx_geo_hierarchy")
    ]
    
    print("\nCritical query patterns coverage:")
    for pattern, indexes in critical_patterns:
        print(f"✅ {pattern}: {indexes}")
    
    # Check for missing indexes on commonly queried columns
    cursor.execute("""
        SELECT DISTINCT location_type, COUNT(*) as frequency
        FROM schedule_locations 
        GROUP BY location_type
        ORDER BY frequency DESC
    """)
    location_types = cursor.fetchall()
    if location_types:
        # Check if location_type has an index
        cursor.execute("SELECT name FROM sqlite_master WHERE type='index' AND sql LIKE '%location_type%'")
        location_type_index = cursor.fetchone()
        if not location_type_index:
            performance_issues.append("Missing index on schedule_locations.location_type")
    
    print(f"\nPerformance issues identified: {len(performance_issues)}")
    for issue in performance_issues:
        print(f"  - {issue}")
    
    db.close()
    return len(performance_issues)

def analyze_data_types_and_constraints():
    """Review data types and constraint usage."""
    db = sqlite3.connect('timetable.db')
    cursor = db.cursor()
    
    print("\n=== DATA TYPES AND CONSTRAINTS ANALYSIS ===\n")
    
    constraint_issues = []
    
    # Check for missing NOT NULL constraints on important fields
    cursor.execute("PRAGMA table_info(stations)")
    stations_columns = cursor.fetchall()
    
    nullable_important_fields = []
    for col_info in stations_columns:
        col_name = col_info[1]
        is_nullable = col_info[3] == 0  # notnull is 1 if NOT NULL
        if col_name in ['station_name', 'tiploc'] and is_nullable:
            nullable_important_fields.append(col_name)
    
    if nullable_important_fields:
        constraint_issues.append(f"Important fields allow NULL: {nullable_important_fields}")
    
    # Check for inappropriate data types
    print("Data type usage review:")
    
    # Time storage analysis
    cursor.execute("""
        SELECT 
            COUNT(*) as total_locations,
            SUM(CASE WHEN arrival_seconds IS NOT NULL THEN 1 ELSE 0 END) as with_seconds,
            SUM(CASE WHEN arrival_time IS NOT NULL THEN 1 ELSE 0 END) as with_text_time
        FROM schedule_locations
    """)
    time_data = cursor.fetchone()
    seconds_coverage = (time_data[1] / time_data[0]) * 100 if time_data[0] > 0 else 0
    print(f"✅ Time storage: {seconds_coverage:.1f}% using optimized seconds-based format")
    
    # Coordinate data types
    cursor.execute("SELECT COUNT(*) FROM stations WHERE latitude IS NOT NULL AND longitude IS NOT NULL")
    geo_coverage = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM stations")
    total_stations = cursor.fetchone()[0]
    geo_percentage = (geo_coverage / total_stations) * 100
    print(f"📍 Geographical data: {geo_percentage:.1f}% stations have coordinates")
    
    # Check for missing unique constraints
    cursor.execute("""
        SELECT train_uid, start_date, stp_indicator, COUNT(*) 
        FROM schedules 
        GROUP BY train_uid, start_date, stp_indicator 
        HAVING COUNT(*) > 1
        LIMIT 1
    """)
    duplicate_check = cursor.fetchone()
    if duplicate_check:
        constraint_issues.append("Possible missing unique constraint on schedules")
    
    print(f"\nConstraint issues identified: {len(constraint_issues)}")
    for issue in constraint_issues:
        print(f"  - {issue}")
    
    db.close()
    return len(constraint_issues)

def analyze_scalability():
    """Assess database scalability and growth patterns."""
    db = sqlite3.connect('timetable.db')
    cursor = db.cursor()
    
    print("\n=== SCALABILITY ANALYSIS ===\n")
    
    # Calculate database size
    cursor.execute("SELECT page_count * page_size as size FROM pragma_page_count(), pragma_page_size()")
    db_size = cursor.fetchone()[0]
    db_size_mb = db_size / (1024 * 1024)
    print(f"Database size: {db_size_mb:.1f} MB")
    
    # Analyze growth patterns
    cursor.execute("SELECT COUNT(*) FROM schedules")
    total_schedules = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM schedule_locations")
    total_locations = cursor.fetchone()[0]
    
    locations_per_schedule = total_locations / total_schedules if total_schedules > 0 else 0
    print(f"Average locations per schedule: {locations_per_schedule:.1f}")
    
    # Check for potential bottlenecks
    cursor.execute("""
        SELECT 
            MAX(sequence) as max_stops,
            AVG(sequence) as avg_stops
        FROM schedule_locations
        GROUP BY schedule_id
        ORDER BY max_stops DESC
        LIMIT 1
    """)
    route_complexity = cursor.fetchone()
    if route_complexity:
        print(f"Most complex route: {route_complexity[0]} stops")
        print(f"Average route complexity: {route_complexity[1]:.1f} stops")
    
    # Storage efficiency
    estimated_row_size = 200  # bytes per schedule_location row
    storage_efficiency = (total_locations * estimated_row_size) / db_size
    print(f"Storage efficiency: {storage_efficiency:.1%}")
    
    scalability_score = "Good" if db_size_mb < 500 and storage_efficiency > 0.3 else "Needs attention"
    print(f"Scalability assessment: {scalability_score}")
    
    db.close()
    return db_size_mb

def generate_recommendations():
    """Generate comprehensive recommendations for model improvements."""
    print("\n" + "="*80)
    print("COMPREHENSIVE DATA MODEL RECOMMENDATIONS")
    print("="*80)
    
    recommendations = {
        "High Priority": [
            "Implement proper foreign key constraints with ON DELETE CASCADE",
            "Add CHECK constraints for time validation (e.g., arrival_seconds >= 0)",
            "Create location_type index for schedule_locations table",
            "Normalize activity codes into separate reference table",
            "Add unique constraints to prevent duplicate schedules"
        ],
        "Medium Priority": [
            "Consider partitioning schedule_locations by date for better performance",
            "Implement audit trail tables for critical data changes",
            "Add materialized views for common aggregations",
            "Create proper lookup tables for categorical data",
            "Implement data archival strategy for historical records"
        ],
        "Low Priority": [
            "Consider migrating to PostgreSQL for better geospatial support",
            "Add full-text search capabilities for station names",
            "Implement data validation triggers",
            "Add compression for large text fields",
            "Consider column store indexes for analytical queries"
        ],
        "Data Quality": [
            "Populate place_name_mappings table for enhanced search",
            "Validate and clean geographical coordinates",
            "Standardize operator codes and station categories",
            "Implement data quality monitoring dashboards",
            "Add automated consistency checking procedures"
        ]
    }
    
    for category, items in recommendations.items():
        print(f"\n{category.upper()} RECOMMENDATIONS:")
        for i, item in enumerate(items, 1):
            print(f"  {i}. {item}")
    
    return recommendations

def main():
    """Run comprehensive data model review."""
    print("Railway Timetable Database - Data Model Quality Review")
    print("=" * 60)
    
    try:
        # Run all analyses
        integrity_issues = analyze_table_relationships()
        consistency_issues = analyze_data_consistency()
        normalization_issues = analyze_normalization()
        performance_issues = analyze_indexing_performance()
        constraint_issues = analyze_data_types_and_constraints()
        db_size = analyze_scalability()
        
        # Generate overall quality score
        total_issues = (integrity_issues + consistency_issues + 
                       normalization_issues + performance_issues + constraint_issues)
        
        print(f"\n" + "="*60)
        print("OVERALL DATA MODEL QUALITY ASSESSMENT")
        print("="*60)
        
        print(f"Database Size: {db_size:.1f} MB")
        print(f"Total Issues Identified: {total_issues}")
        print(f"Referential Integrity: {'✅ Good' if integrity_issues == 0 else f'❌ {integrity_issues} issues'}")
        print(f"Data Consistency: {'✅ Good' if consistency_issues == 0 else f'❌ {consistency_issues} issues'}")
        print(f"Normalization: {'✅ Good' if normalization_issues <= 2 else f'⚠️ {normalization_issues} issues'}")
        print(f"Performance Optimization: {'✅ Good' if performance_issues == 0 else f'⚠️ {performance_issues} issues'}")
        print(f"Constraints & Types: {'✅ Good' if constraint_issues == 0 else f'⚠️ {constraint_issues} issues'}")
        
        # Overall grade
        if total_issues == 0:
            grade = "A+ (Excellent)"
        elif total_issues <= 5:
            grade = "A- (Very Good)"
        elif total_issues <= 10:
            grade = "B+ (Good)"
        elif total_issues <= 20:
            grade = "B- (Fair)"
        else:
            grade = "C (Needs Improvement)"
        
        print(f"\nOverall Model Quality Grade: {grade}")
        
        # Generate recommendations
        recommendations = generate_recommendations()
        
        print(f"\nReview completed successfully!")
        
    except Exception as e:
        print(f"Error during analysis: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main())