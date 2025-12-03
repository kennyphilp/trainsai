#!/usr/bin/env python3
"""
End-to-End Application Architecture Review
==========================================

This script performs a comprehensive review of the current application architecture
and identifies specific changes needed to leverage the enhanced database capabilities.
"""

import os
import sqlite3
import json
from datetime import datetime
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

def analyze_current_application_stack():
    """Analyze the current application architecture."""
    print("=== CURRENT APPLICATION ARCHITECTURE ANALYSIS ===\n")
    
    # Check file structure
    files = {
        'app.py': 'Flask web application with chat interface',
        'scotrail_agent.py': 'OpenAI-powered conversational agent',
        'train_tools.py': 'Live data API integration (LDBWS)',
        'timetable_tools.py': 'Schedule database query tools',
        'timetable_database.py': 'Database abstraction layer',
        'improved_station_resolver.py': 'Enhanced station name resolution',
        'config.py': 'Application configuration management'
    }
    
    missing_files = []
    existing_features = []
    
    for filename, description in files.items():
        if os.path.exists(filename):
            existing_features.append(f"✅ {filename}: {description}")
        else:
            missing_files.append(f"❌ {filename}: {description}")
    
    print("Current Application Components:")
    for feature in existing_features:
        print(f"  {feature}")
    
    if missing_files:
        print("\nMissing Components:")
        for missing in missing_files:
            print(f"  {missing}")
    
    return len(missing_files) == 0

def analyze_database_capabilities():
    """Analyze the enhanced database capabilities."""
    print("\n=== ENHANCED DATABASE CAPABILITIES ANALYSIS ===\n")
    
    db = sqlite3.connect('timetable.db')
    cursor = db.cursor()
    
    capabilities = {
        'time_optimization': {
            'description': 'Seconds-based time storage for fast range queries',
            'check': "SELECT COUNT(*) FROM schedule_locations WHERE arrival_seconds IS NOT NULL"
        },
        'geographical_hierarchy': {
            'description': 'Hierarchical geographical areas (country→region→city)',
            'check': "SELECT COUNT(*) FROM geographical_areas"
        },
        'place_name_intelligence': {
            'description': 'Smart station search with geographical context',
            'check': "SELECT name FROM sqlite_master WHERE type='view' AND name='smart_station_search'"
        },
        'optimized_journey_queries': {
            'description': 'Pre-computed journey times view for fast lookup',
            'check': "SELECT name FROM sqlite_master WHERE type='view' AND name='journey_times'"
        },
        'place_based_journeys': {
            'description': 'City-to-city journey planning capabilities',
            'check': "SELECT name FROM sqlite_master WHERE type='view' AND name='place_based_journeys'"
        },
        'enhanced_indexing': {
            'description': 'Comprehensive index coverage for query optimization',
            'check': "SELECT COUNT(*) FROM sqlite_master WHERE type='index' AND name LIKE 'idx_%'"
        }
    }
    
    capability_status = {}
    
    for name, info in capabilities.items():
        try:
            cursor.execute(info['check'])
            result = cursor.fetchone()[0]
            
            if name == 'time_optimization':
                # Check percentage of records with time optimization
                cursor.execute("SELECT COUNT(*) FROM schedule_locations")
                total = cursor.fetchone()[0]
                percentage = (result / total * 100) if total > 0 else 0
                status = f"✅ {percentage:.1f}% optimized ({result:,} records)"
            elif name in ['place_name_intelligence', 'optimized_journey_queries', 'place_based_journeys']:
                status = "✅ Available" if result else "❌ Not implemented"
            else:
                status = f"✅ {result:,} items" if result > 0 else "❌ None found"
            
            capability_status[name] = {'status': status, 'available': result > 0}
            print(f"{info['description']}: {status}")
            
        except Exception as e:
            capability_status[name] = {'status': f"❌ Error: {e}", 'available': False}
            print(f"{info['description']}: ❌ Error: {e}")
    
    db.close()
    return capability_status

def analyze_application_database_integration():
    """Analyze how well the application integrates with database capabilities."""
    print("\n=== APPLICATION-DATABASE INTEGRATION ANALYSIS ===\n")
    
    integration_issues = []
    
    # Check timetable_tools.py for modern capabilities usage
    if os.path.exists('timetable_tools.py'):
        with open('timetable_tools.py', 'r') as f:
            timetable_content = f.read()
            
        # Check for time optimization usage
        if 'arrival_seconds' in timetable_content and 'departure_seconds' in timetable_content:
            print("✅ Timetable tools use optimized seconds-based timing")
        else:
            print("❌ Timetable tools still use text-based time queries")
            integration_issues.append("Update timetable_tools.py to use seconds-based timing")
        
        # Check for geographical hierarchy usage
        if 'geographical_areas' in timetable_content:
            print("✅ Timetable tools leverage geographical hierarchy")
        else:
            print("⚠️ Timetable tools do not use geographical hierarchy")
            integration_issues.append("Integrate geographical hierarchy into journey planning")
        
        # Check for optimized views usage
        if 'journey_times' in timetable_content:
            print("✅ Timetable tools use optimized journey_times view")
        else:
            print("❌ Timetable tools do not use optimized journey_times view")
            integration_issues.append("Update journey queries to use journey_times view")
    
    # Check improved_station_resolver.py
    if os.path.exists('improved_station_resolver.py'):
        with open('improved_station_resolver.py', 'r') as f:
            resolver_content = f.read()
            
        if 'smart_station_search' in resolver_content:
            print("✅ Station resolver uses smart search view")
        else:
            print("❌ Station resolver does not use smart search view")
            integration_issues.append("Update station resolver to use smart_station_search view")
    
    # Check scotrail_agent.py for enhanced capabilities
    if os.path.exists('scotrail_agent.py'):
        with open('scotrail_agent.py', 'r') as f:
            agent_content = f.read()
            
        # Check for place name search capabilities
        if 'place_name' in agent_content.lower():
            print("✅ ScotRail agent has place name search capabilities")
        else:
            print("❌ ScotRail agent lacks place name search capabilities")
            integration_issues.append("Add place name search tools to ScotRail agent")
    
    print(f"\nIntegration issues identified: {len(integration_issues)}")
    for issue in integration_issues:
        print(f"  - {issue}")
    
    return integration_issues

def identify_performance_opportunities():
    """Identify performance optimization opportunities."""
    print("\n=== PERFORMANCE OPTIMIZATION OPPORTUNITIES ===\n")
    
    db = sqlite3.connect('timetable.db')
    cursor = db.cursor()
    
    opportunities = []
    
    # Check query patterns that could be optimized
    cursor.execute("SELECT COUNT(*) FROM schedule_locations")
    total_locations = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM schedule_locations WHERE arrival_seconds IS NOT NULL")
    optimized_locations = cursor.fetchone()[0]
    
    optimization_percentage = (optimized_locations / total_locations * 100) if total_locations > 0 else 0
    
    if optimization_percentage < 100:
        opportunities.append(f"Complete time optimization: {100-optimization_percentage:.1f}% records still need conversion")
    else:
        print("✅ Time data fully optimized")
    
    # Check for materialized view opportunities
    cursor.execute("SELECT COUNT(*) FROM journey_times")
    try:
        journey_count = cursor.fetchone()[0]
        print(f"✅ Journey times view available with {journey_count:,} pre-computed routes")
    except:
        opportunities.append("Create materialized journey_times view for faster route lookups")
    
    # Check index coverage
    cursor.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='index' AND name LIKE 'idx_%'")
    index_count = cursor.fetchone()[0]
    print(f"✅ {index_count} custom indexes available")
    
    # Check for missing popular queries optimization
    cursor.execute("SELECT COUNT(*) FROM popular_destinations")
    popular_destinations = cursor.fetchone()[0]
    if popular_destinations > 0:
        print(f"✅ Popular destinations table with {popular_destinations} entries")
    else:
        opportunities.append("Populate popular_destinations table for faster city-to-city queries")
    
    db.close()
    
    print(f"\nPerformance opportunities identified: {len(opportunities)}")
    for opp in opportunities:
        print(f"  - {opp}")
    
    return opportunities

def generate_architecture_recommendations():
    """Generate comprehensive architecture enhancement recommendations."""
    print("\n" + "="*80)
    print("ARCHITECTURAL ENHANCEMENT RECOMMENDATIONS")
    print("="*80)
    
    recommendations = {
        "Critical Updates (High Impact)": [
            {
                "component": "TimetableTools",
                "change": "Migrate to seconds-based time queries",
                "benefit": "2.9x performance improvement on time range queries",
                "implementation": "Update all time-based queries to use arrival_seconds/departure_seconds columns"
            },
            {
                "component": "StationResolver",
                "change": "Implement smart_station_search view integration",
                "benefit": "Geographical context and fuzzy matching capabilities",
                "implementation": "Replace manual station matching with smart_station_search view queries"
            },
            {
                "component": "ScotRailAgent",
                "change": "Add place-name search tools",
                "benefit": "Natural language journey planning ('London to Birmingham')",
                "implementation": "Create new tools using place_based_journeys view and geographical hierarchy"
            }
        ],
        
        "Performance Enhancements (Medium Impact)": [
            {
                "component": "Journey Planning",
                "change": "Use pre-computed journey_times view",
                "benefit": "Eliminate complex join operations in real-time queries",
                "implementation": "Replace multi-table joins with direct journey_times view queries"
            },
            {
                "component": "Station Search",
                "change": "Implement geographical hierarchy filtering",
                "benefit": "Context-aware search results (city/region disambiguation)",
                "implementation": "Use geographical_areas table for hierarchical station grouping"
            },
            {
                "component": "API Responses",
                "change": "Add structured geographical metadata",
                "benefit": "Enhanced frontend mapping and visualization capabilities",
                "implementation": "Include city/region/country data in all station responses"
            }
        ],
        
        "Feature Extensions (Low Impact)": [
            {
                "component": "Route Planning",
                "change": "Implement city-to-city journey suggestions",
                "benefit": "Simplified journey planning for major destinations",
                "implementation": "Create API endpoints using place_based_journeys view"
            },
            {
                "component": "Data Quality",
                "change": "Add real-time validation against schedule data",
                "benefit": "Identify service disruptions and delays more accurately",
                "implementation": "Compare live API data with scheduled times using time optimization"
            },
            {
                "component": "Caching Strategy",
                "change": "Implement intelligent query result caching",
                "benefit": "Reduced database load for common queries",
                "implementation": "Cache results for popular routes using geographical hierarchy"
            }
        ]
    }
    
    for category, items in recommendations.items():
        print(f"\n{category.upper()}:")
        for i, rec in enumerate(items, 1):
            print(f"  {i}. {rec['component']}: {rec['change']}")
            print(f"     Benefit: {rec['benefit']}")
            print(f"     Implementation: {rec['implementation']}")
            print()
    
    return recommendations

def create_migration_plan():
    """Create a detailed migration plan for implementing enhancements."""
    print("\n" + "="*80)
    print("IMPLEMENTATION MIGRATION PLAN")
    print("="*80)
    
    migration_phases = [
        {
            "phase": "Phase 1: Core Performance (Week 1)",
            "priority": "Critical",
            "tasks": [
                "Update TimetableTools to use seconds-based timing",
                "Implement smart station search in ImprovedStationResolver",
                "Add time-based indexes validation",
                "Performance testing and benchmarking"
            ],
            "expected_benefit": "2-3x performance improvement on time queries"
        },
        {
            "phase": "Phase 2: Enhanced Search (Week 2)",
            "priority": "High",
            "tasks": [
                "Integrate geographical hierarchy in all station queries",
                "Add place-name search tools to ScotRailAgent",
                "Update API responses with geographical metadata",
                "Implement fuzzy matching with geographical context"
            ],
            "expected_benefit": "Natural language search capabilities and better disambiguation"
        },
        {
            "phase": "Phase 3: Advanced Features (Week 3)",
            "priority": "Medium", 
            "tasks": [
                "Implement city-to-city journey planning",
                "Add schedule vs actual comparison tools",
                "Create intelligent caching layer",
                "Optimize popular routes using place_based_journeys view"
            ],
            "expected_benefit": "Enhanced user experience and reduced server load"
        },
        {
            "phase": "Phase 4: Quality & Monitoring (Week 4)",
            "priority": "Low",
            "tasks": [
                "Implement comprehensive query monitoring",
                "Add data quality validation dashboards",
                "Performance optimization based on usage patterns",
                "Documentation and testing completion"
            ],
            "expected_benefit": "Production readiness and operational monitoring"
        }
    ]
    
    for phase_info in migration_phases:
        print(f"\n{phase_info['phase'].upper()} ({phase_info['priority']} Priority)")
        print(f"Expected Benefit: {phase_info['expected_benefit']}")
        print("Tasks:")
        for task in phase_info['tasks']:
            print(f"  - {task}")
    
    return migration_phases

def assess_technical_debt():
    """Assess current technical debt and modernization needs."""
    print(f"\n=== TECHNICAL DEBT ASSESSMENT ===\n")
    
    debt_areas = []
    
    # Check for old vs new patterns
    files_to_check = [
        ('timetable_tools.py', ['arrival_time', 'departure_time'], 'Text-based time queries'),
        ('scotrail_agent.py', ['fuzzy', 'place_name'], 'Missing place-name capabilities'),
        ('improved_station_resolver.py', ['smart_station_search'], 'Not using optimized views')
    ]
    
    for filename, patterns, debt_description in files_to_check:
        if os.path.exists(filename):
            with open(filename, 'r') as f:
                content = f.read()
                
            patterns_found = [p for p in patterns if p in content]
            
            if filename == 'timetable_tools.py' and 'arrival_time' in patterns_found:
                debt_areas.append(f"❌ {filename}: {debt_description} (legacy pattern detected)")
            elif filename != 'timetable_tools.py' and not patterns_found:
                debt_areas.append(f"❌ {filename}: {debt_description} (missing modern features)")
            else:
                print(f"✅ {filename}: Appears to use modern patterns")
    
    # Check database usage patterns
    db = sqlite3.connect('timetable.db')
    cursor = db.cursor()
    
    # Check if place_name_mappings is populated
    cursor.execute("SELECT COUNT(*) FROM place_name_mappings")
    place_mappings = cursor.fetchone()[0]
    if place_mappings == 0:
        debt_areas.append("❌ place_name_mappings table empty (intelligent search not functional)")
    
    db.close()
    
    print(f"Technical debt areas identified: {len(debt_areas)}")
    for debt in debt_areas:
        print(f"  {debt}")
    
    return len(debt_areas)

def main():
    """Run comprehensive application architecture review."""
    print("Railway Application Architecture Review")
    print("=" * 60)
    print(f"Review Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    try:
        # Analyze current state
        app_complete = analyze_current_application_stack()
        db_capabilities = analyze_database_capabilities()
        integration_issues = analyze_application_database_integration()
        performance_opportunities = identify_performance_opportunities()
        
        # Generate recommendations
        recommendations = generate_architecture_recommendations()
        migration_plan = create_migration_plan()
        technical_debt = assess_technical_debt()
        
        # Overall assessment
        print(f"\n" + "="*60)
        print("OVERALL ARCHITECTURAL ASSESSMENT")
        print("="*60)
        
        capability_score = sum(1 for cap in db_capabilities.values() if cap['available'])
        total_capabilities = len(db_capabilities)
        capability_percentage = (capability_score / total_capabilities * 100)
        
        print(f"Application Stack Completeness: {'✅ Complete' if app_complete else '❌ Incomplete'}")
        print(f"Database Capabilities Available: {capability_score}/{total_capabilities} ({capability_percentage:.1f}%)")
        print(f"Integration Issues: {len(integration_issues)}")
        print(f"Performance Opportunities: {len(performance_opportunities)}")
        print(f"Technical Debt Areas: {technical_debt}")
        
        # Architecture maturity assessment
        if capability_percentage >= 80 and len(integration_issues) <= 3 and technical_debt <= 2:
            maturity = "🎯 Ready for Production (Minor optimizations needed)"
        elif capability_percentage >= 60 and len(integration_issues) <= 6:
            maturity = "🔧 Modernization Required (Significant updates needed)"
        else:
            maturity = "⚠️ Major Restructuring Required (Architecture overhaul needed)"
        
        print(f"\nArchitecture Maturity: {maturity}")
        
        print(f"\nArchitectural review completed successfully!")
        
    except Exception as e:
        print(f"Error during review: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main())