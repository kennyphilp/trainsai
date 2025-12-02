#!/usr/bin/env python3
"""
Production monitoring script for the live Darwin integration deployment.
"""

import time
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

def check_service_status():
    """Check the status of various components."""
    status = {
        'timestamp': datetime.now().isoformat(),
        'components': {},
        'overall_status': 'healthy'
    }
    
    # Check if files exist
    critical_files = [
        'live_integration.py',
        'enhanced_api.py',
        'start_live_service.py',
        'cancellations_service.py',
        'train_movements_client.py'
    ]
    
    missing_files = []
    for file in critical_files:
        if not Path(file).exists():
            missing_files.append(file)
    
    status['components']['files'] = {
        'status': 'healthy' if not missing_files else 'degraded',
        'missing_files': missing_files
    }
    
    # Check database files
    databases = ['demo_detailed.db', 'darwin_schedules.db']
    db_status = {}
    for db in databases:
        if Path(db).exists():
            size_kb = Path(db).stat().st_size / 1024
            db_status[db] = {'exists': True, 'size_kb': round(size_kb, 1)}
        else:
            db_status[db] = {'exists': False}
    
    status['components']['databases'] = db_status
    
    # Check if logs directory exists
    logs_dir = Path('logs')
    status['components']['logging'] = {
        'logs_dir_exists': logs_dir.exists(),
        'log_files': list(logs_dir.glob('*.log')) if logs_dir.exists() else []
    }
    
    # Test service initialization
    try:
        # Import and test basic service creation
        sys.path.append('.')
        from live_integration import LiveIntegrationService
        
        # Quick test - just initialize without starting
        test_service = LiveIntegrationService()
        test_status = test_service.get_status()
        
        status['components']['service'] = {
            'initialization': 'success',
            'enrichment_enabled': test_status['configuration']['enrichment_enabled'],
            'max_stored': test_status['configuration']['max_stored']
        }
        
    except Exception as e:
        status['components']['service'] = {
            'initialization': 'failed',
            'error': str(e)
        }
        status['overall_status'] = 'degraded'
    
    return status


def display_status(status):
    """Display status in a readable format."""
    print(f"🕒 {status['timestamp']}")
    print(f"🎯 Overall Status: {status['overall_status'].upper()}")
    print()
    
    # Files status
    files = status['components']['files']
    file_emoji = "✅" if files['status'] == 'healthy' else "⚠️"
    print(f"{file_emoji} Critical Files: {files['status']}")
    if files['missing_files']:
        print(f"   Missing: {', '.join(files['missing_files'])}")
    
    # Database status
    print("\n🗄️  Databases:")
    for db, info in status['components']['databases'].items():
        db_emoji = "✅" if info['exists'] else "❌"
        if info['exists']:
            print(f"   {db_emoji} {db} ({info['size_kb']} KB)")
        else:
            print(f"   {db_emoji} {db} (missing)")
    
    # Service status
    service = status['components']['service']
    service_emoji = "✅" if service['initialization'] == 'success' else "❌"
    print(f"\n{service_emoji} Service Initialization: {service['initialization']}")
    if service['initialization'] == 'success':
        print(f"   Enrichment: {'Enabled' if service['enrichment_enabled'] else 'Disabled'}")
        print(f"   Max Stored: {service['max_stored']}")
    else:
        print(f"   Error: {service.get('error', 'Unknown')}")
    
    # Logging status
    logging = status['components']['logging']
    log_emoji = "✅" if logging['logs_dir_exists'] else "⚠️"
    print(f"\n{log_emoji} Logging Setup: {'Ready' if logging['logs_dir_exists'] else 'Missing logs directory'}")
    if logging['log_files']:
        print(f"   Log files: {len(logging['log_files'])}")


def production_readiness_check():
    """Comprehensive production readiness assessment."""
    print("🚀 PRODUCTION READINESS ASSESSMENT")
    print("=" * 50)
    
    status = check_service_status()
    display_status(status)
    
    print("\n📋 DEPLOYMENT CHECKLIST:")
    print("-" * 30)
    
    checks = [
        ("Critical files present", status['components']['files']['status'] == 'healthy'),
        ("Demo database available", status['components']['databases']['demo_detailed.db']['exists']),
        ("Service initializes", status['components']['service']['initialization'] == 'success'),
        ("Enrichment enabled", status['components']['service'].get('enrichment_enabled', False)),
        ("Logs directory ready", status['components']['logging']['logs_dir_exists'])
    ]
    
    passed_checks = 0
    for check_name, passed in checks:
        emoji = "✅" if passed else "❌"
        print(f"   {emoji} {check_name}")
        if passed:
            passed_checks += 1
    
    print(f"\n📊 READINESS SCORE: {passed_checks}/{len(checks)} ({(passed_checks/len(checks)*100):.0f}%)")
    
    if passed_checks == len(checks):
        print("\n🎉 SYSTEM IS PRODUCTION READY!")
        print("\nNext steps:")
        print("1. Start live service: python start_live_service.py")
        print("2. Start API server: python enhanced_api.py") 
        print("3. Monitor logs: tail -f logs/darwin_integration.log")
    elif passed_checks >= len(checks) * 0.8:
        print("\n⚠️  SYSTEM IS MOSTLY READY (minor issues)")
        print("Address any ❌ items above before production deployment")
    else:
        print("\n❌ SYSTEM NOT READY FOR PRODUCTION")
        print("Please resolve critical issues before deployment")
    
    return status


def continuous_monitoring():
    """Run continuous monitoring loop."""
    print("🔄 CONTINUOUS MONITORING MODE")
    print("Press Ctrl+C to stop monitoring")
    print("=" * 50)
    
    try:
        while True:
            print("\n" + "="*60)
            status = check_service_status()
            display_status(status)
            
            print("\n💤 Next check in 60 seconds...")
            time.sleep(60)
            
    except KeyboardInterrupt:
        print("\n\n🛑 Monitoring stopped")


def main():
    """Main monitoring function."""
    if len(sys.argv) > 1 and sys.argv[1] == '--continuous':
        continuous_monitoring()
    else:
        production_readiness_check()


if __name__ == "__main__":
    main()