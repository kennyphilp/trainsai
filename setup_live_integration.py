#!/usr/bin/env python3
"""
Setup script to verify and install required packages for live Darwin integration.
"""

import subprocess
import sys
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

REQUIRED_PACKAGES = [
    'stomp.py',
    'pydantic',
    'pydantic-settings',
    'python-dotenv'
]


def check_package(package_name):
    """Check if a package is installed."""
    try:
        __import__(package_name.replace('-', '_').split('.')[0])
        return True
    except ImportError:
        return False


def install_package(package_name):
    """Install a package using pip."""
    try:
        logger.info(f"Installing {package_name}...")
        subprocess.check_call([sys.executable, '-m', 'pip', 'install', package_name])
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to install {package_name}: {e}")
        return False


def main():
    """Main setup function."""
    logger.info("🔧 Setting up Live Darwin Integration Environment")
    
    missing_packages = []
    
    # Check required packages
    for package in REQUIRED_PACKAGES:
        module_name = package.replace('-', '_').split('.')[0]
        if not check_package(module_name):
            missing_packages.append(package)
            logger.warning(f"❌ Missing package: {package}")
        else:
            logger.info(f"✅ Package available: {package}")
    
    # Install missing packages
    if missing_packages:
        logger.info(f"📦 Installing {len(missing_packages)} missing packages...")
        failed_installs = []
        
        for package in missing_packages:
            if not install_package(package):
                failed_installs.append(package)
        
        if failed_installs:
            logger.error(f"❌ Failed to install packages: {failed_installs}")
            logger.error("Please install these packages manually:")
            for package in failed_installs:
                print(f"  pip install {package}")
            return False
        else:
            logger.info("✅ All packages installed successfully!")
    else:
        logger.info("✅ All required packages are already available!")
    
    # Verify critical imports
    logger.info("🧪 Testing critical imports...")
    
    try:
        import stomp
        logger.info("✅ stomp.py import successful")
    except ImportError as e:
        logger.error(f"❌ Failed to import stomp: {e}")
        return False
    
    try:
        from pydantic import Field
        from pydantic_settings import BaseSettings
        logger.info("✅ pydantic imports successful")
    except ImportError as e:
        logger.error(f"❌ Failed to import pydantic: {e}")
        return False
    
    # Check if demo database exists
    import os
    if os.path.exists('demo_detailed.db'):
        logger.info("✅ Demo Darwin database found")
    else:
        logger.warning("⚠️  Demo Darwin database not found - enrichment may not work in tests")
    
    logger.info("🎉 Environment setup completed successfully!")
    logger.info("💡 You can now run: python test_live_integration.py")
    
    return True


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)