#!/usr/bin/env python3
"""
Enhanced Flask app demonstrating the integrated cancellations service with Darwin enrichment.
"""

import sys
import os
import logging
from datetime import datetime
from flask import Flask, jsonify, request
from pathlib import Path

# Add current directory to path for imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Import enhanced service and config
from cancellations_service import CancellationsService
from config import get_config

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)

# Global service instance
cancellations_service = None


def initialize_service():
    """Initialize the cancellations service with Darwin enrichment."""
    global cancellations_service
    
    if cancellations_service is None:
        try:
            config = get_config()
            
            # Initialize with demo database for this demonstration
            cancellations_service = CancellationsService(
                max_stored=config.cancellation_max_stored,
                darwin_db_path="demo_detailed.db",  # Use demo database
                enable_enrichment=config.darwin_enrichment_enabled
            )
            
            logger.info("✅ Cancellations service initialized with Darwin enrichment")
            
        except Exception as e:
            logger.error(f"❌ Failed to initialize service: {e}")
            # Fallback to basic service
            cancellations_service = CancellationsService(
                max_stored=50,
                enable_enrichment=False
            )
            logger.info("⚪ Fallback to basic service without Darwin enrichment")


@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint."""
    return jsonify({
        'status': 'healthy',
        'service': 'cancellations-service',
        'timestamp': datetime.now().isoformat(),
        'darwin_enrichment': cancellations_service.enable_enrichment if cancellations_service else False
    })


@app.route('/cancellations', methods=['GET'])
def get_cancellations():
    """Get recent cancellations with enrichment data."""
    try:
        if not cancellations_service:
            return jsonify({'error': 'Service not initialized'}), 500
        
        limit = request.args.get('limit', default=10, type=int)
        limit = min(max(limit, 1), 100)  # Constrain between 1-100
        
        cancellations = cancellations_service.get_recent_cancellations(limit=limit)
        
        return jsonify({
            'status': 'success',
            'count': len(cancellations),
            'limit': limit,
            'cancellations': cancellations,
            'enrichment_enabled': cancellations_service.enable_enrichment
        })
        
    except Exception as e:
        logger.error(f"Error retrieving cancellations: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@app.route('/cancellations/stats', methods=['GET'])
def get_cancellation_stats():
    """Get service statistics including enrichment data."""
    try:
        if not cancellations_service:
            return jsonify({'error': 'Service not initialized'}), 500
        
        stats = cancellations_service.get_stats()
        
        return jsonify({
            'status': 'success',
            'statistics': stats,
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Error retrieving stats: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@app.route('/cancellations', methods=['POST'])
def add_cancellation():
    """Add a new cancellation (for testing purposes)."""
    try:
        if not cancellations_service:
            return jsonify({'error': 'Service not initialized'}), 500
        
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'No JSON data provided'}), 400
        
        # Validate required fields
        required_fields = ['train_service_code', 'reason_text']
        missing_fields = [field for field in required_fields if not data.get(field)]
        
        if missing_fields:
            return jsonify({
                'error': 'Missing required fields',
                'missing': missing_fields
            }), 400
        
        # Add timestamp if not provided
        if 'cancelled_at' not in data:
            data['cancelled_at'] = datetime.now().isoformat()
        
        # Add the cancellation
        cancellations_service.add_cancellation(data)
        
        return jsonify({
            'status': 'success',
            'message': 'Cancellation added successfully',
            'enrichment_enabled': cancellations_service.enable_enrichment
        }), 201
        
    except Exception as e:
        logger.error(f"Error adding cancellation: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@app.route('/cancellations/demo', methods=['POST'])
def add_demo_cancellations():
    """Add demo cancellations for testing (includes one with valid RID for enrichment)."""
    try:
        if not cancellations_service:
            return jsonify({'error': 'Service not initialized'}), 500
        
        demo_cancellations = [
            {
                "rid": "DEMO202512011800001",  # Valid RID for enrichment
                "train_service_code": "1A23",
                "train_id": "1A23",
                "reason_code": "104",
                "reason_text": "Train cancelled due to a fault on this train",
                "location": "Edinburgh",
                "cancelled_at": datetime.now().isoformat()
            },
            {
                "rid": "nonexistent_rid",  # Invalid RID - no enrichment
                "train_service_code": "2B45",
                "train_id": "2B45",
                "reason_code": "105",
                "reason_text": "Train cancelled due to severe weather conditions",
                "location": "Glasgow",
                "cancelled_at": datetime.now().isoformat()
            },
            {
                "train_service_code": "3C67",  # No RID - no enrichment
                "train_id": "3C67",
                "reason_code": "106",
                "reason_text": "Train cancelled due to signal failure",
                "location": "Aberdeen",
                "cancelled_at": datetime.now().isoformat()
            }
        ]
        
        # Add all demo cancellations
        for cancellation in demo_cancellations:
            cancellations_service.add_cancellation(cancellation.copy())
        
        # Get updated statistics
        stats = cancellations_service.get_stats()
        
        return jsonify({
            'status': 'success',
            'message': f'Added {len(demo_cancellations)} demo cancellations',
            'statistics': stats
        }), 201
        
    except Exception as e:
        logger.error(f"Error adding demo cancellations: {e}")
        return jsonify({'error': 'Internal server error'}), 500


if __name__ == '__main__':
    logger.info("🚀 Starting Enhanced Cancellations Service API")
    
    # Initialize the service
    initialize_service()
    
    # Get configuration
    config = get_config()
    
    # Run the app
    app.run(
        host=config.flask_host,
        port=config.flask_port,
        debug=config.flask_debug
    )