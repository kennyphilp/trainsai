#!/usr/bin/env python3
"""
Enhanced Flask API with enriched cancellation endpoints.

This provides production-ready REST endpoints that expose the enriched 
cancellation data from the live Darwin integration.
"""

import logging
import json
from datetime import datetime
from flask import Flask, jsonify, request, render_template_string
from pathlib import Path

# Import the live integration service
from live_integration import LiveIntegrationService
from config import get_config

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here'

# Global service instance
live_service = None


def initialize_service():
    """Initialize the live integration service."""
    global live_service
    
    if live_service is None:
        try:
            logger.info("🚀 Initializing Live Darwin Integration Service...")
            live_service = LiveIntegrationService()
            logger.info("✅ Live service initialized")
            
            # Don't start the live feed automatically in API mode
            # This allows API to work without Darwin connection
            
        except Exception as e:
            logger.error(f"❌ Failed to initialize service: {e}")
            live_service = None


@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint."""
    if live_service:
        status = live_service.get_status()
        return jsonify({
            'status': 'healthy',
            'service': 'enhanced-cancellations-api',
            'timestamp': datetime.now().isoformat(),
            'enrichment_enabled': status['configuration']['enrichment_enabled'],
            'service_running': status['service_status']['running']
        })
    else:
        return jsonify({
            'status': 'degraded',
            'service': 'enhanced-cancellations-api',
            'timestamp': datetime.now().isoformat(),
            'error': 'Service not initialized'
        }), 503


@app.route('/cancellations', methods=['GET'])
def get_cancellations():
    """Get recent cancellations with enrichment data."""
    try:
        if not live_service:
            return jsonify({'error': 'Service not available'}), 503
        
        limit = request.args.get('limit', default=10, type=int)
        limit = min(max(limit, 1), 100)  # Constrain between 1-100
        
        # Get enriched cancellations
        cancellations = live_service.get_recent_enriched_cancellations(limit)
        
        # Enhanced response with metadata
        response = {
            'status': 'success',
            'count': len(cancellations),
            'limit': limit,
            'timestamp': datetime.now().isoformat(),
            'cancellations': cancellations,
            'enrichment_summary': _get_enrichment_summary(cancellations)
        }
        
        return jsonify(response)
        
    except Exception as e:
        logger.error(f"Error retrieving cancellations: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@app.route('/cancellations/enriched', methods=['GET'])
def get_enriched_cancellations_only():
    """Get only cancellations that have been enriched with Darwin data."""
    try:
        if not live_service:
            return jsonify({'error': 'Service not available'}), 503
        
        limit = request.args.get('limit', default=10, type=int)
        all_cancellations = live_service.get_recent_enriched_cancellations(limit * 2)  # Get more to filter
        
        # Filter only enriched cancellations
        enriched_cancellations = [
            c for c in all_cancellations 
            if c.get('darwin_enriched', False)
        ][:limit]
        
        return jsonify({
            'status': 'success',
            'count': len(enriched_cancellations),
            'limit': limit,
            'timestamp': datetime.now().isoformat(),
            'cancellations': enriched_cancellations,
            'enrichment_summary': _get_enrichment_summary(enriched_cancellations)
        })
        
    except Exception as e:
        logger.error(f"Error retrieving enriched cancellations: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@app.route('/cancellations/stats', methods=['GET'])
def get_cancellation_stats():
    """Get comprehensive service and enrichment statistics."""
    try:
        if not live_service:
            return jsonify({'error': 'Service not available'}), 503
        
        status = live_service.get_status()
        
        # Add enrichment analytics
        recent_cancellations = live_service.get_recent_enriched_cancellations(50)
        enrichment_analysis = _analyze_enrichment_patterns(recent_cancellations)
        
        return jsonify({
            'status': 'success',
            'timestamp': datetime.now().isoformat(),
            'service_status': status['service_status'],
            'processing_stats': status['processing_stats'],
            'darwin_feed': status['darwin_feed'],
            'cancellations_service': status['cancellations_service'],
            'configuration': status['configuration'],
            'enrichment_analysis': enrichment_analysis
        })
        
    except Exception as e:
        logger.error(f"Error retrieving stats: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@app.route('/cancellations/by-route', methods=['GET'])
def get_cancellations_by_route():
    """Get cancellations grouped by route (origin → destination)."""
    try:
        if not live_service:
            return jsonify({'error': 'Service not available'}), 503
        
        cancellations = live_service.get_recent_enriched_cancellations(100)
        
        # Group by route
        routes = {}
        for c in cancellations:
            if c.get('darwin_enriched'):
                origin = c.get('origin_tiploc_darwin', 'Unknown')
                destination = c.get('destination_tiploc_darwin', 'Unknown')
                route = f"{origin} → {destination}"
                
                if route not in routes:
                    routes[route] = {
                        'route': route,
                        'origin': origin,
                        'destination': destination,
                        'cancellation_count': 0,
                        'cancellations': []
                    }
                
                routes[route]['cancellation_count'] += 1
                routes[route]['cancellations'].append({
                    'rid': c.get('rid'),
                    'train_id': c.get('train_service_code'),
                    'reason': c.get('reason_text'),
                    'cancelled_at': c.get('cancelled_at'),
                    'platform_origin': c.get('origin_platform_darwin'),
                    'platform_destination': c.get('destination_platform_darwin')
                })
        
        # Sort by cancellation count
        sorted_routes = sorted(routes.values(), key=lambda x: x['cancellation_count'], reverse=True)
        
        return jsonify({
            'status': 'success',
            'route_count': len(sorted_routes),
            'total_cancellations': sum(r['cancellation_count'] for r in sorted_routes),
            'timestamp': datetime.now().isoformat(),
            'routes': sorted_routes
        })
        
    except Exception as e:
        logger.error(f"Error analyzing routes: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@app.route('/cancellations/dashboard', methods=['GET'])
def cancellations_dashboard():
    """Simple HTML dashboard showing enriched cancellation data."""
    
    dashboard_html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Enhanced Cancellations Dashboard</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 20px; background: #f5f5f5; }
            .container { max-width: 1200px; margin: 0 auto; }
            .header { background: #2c3e50; color: white; padding: 20px; border-radius: 8px; margin-bottom: 20px; }
            .stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px; margin-bottom: 20px; }
            .stat-card { background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); text-align: center; }
            .stat-number { font-size: 2em; font-weight: bold; color: #3498db; }
            .cancellations { background: white; border-radius: 8px; padding: 20px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
            .cancellation { border-left: 4px solid #e74c3c; padding: 15px; margin-bottom: 15px; background: #fafafa; }
            .cancellation.enriched { border-left-color: #27ae60; }
            .route { font-weight: bold; color: #2c3e50; }
            .details { font-size: 0.9em; color: #666; margin-top: 5px; }
            .enriched-badge { background: #27ae60; color: white; padding: 2px 8px; border-radius: 12px; font-size: 0.8em; }
            .basic-badge { background: #95a5a6; color: white; padding: 2px 8px; border-radius: 12px; font-size: 0.8em; }
            .refresh-btn { background: #3498db; color: white; padding: 10px 20px; border: none; border-radius: 5px; cursor: pointer; }
        </style>
        <script>
            function refreshData() {
                location.reload();
            }
            
            // Auto-refresh every 30 seconds
            setInterval(refreshData, 30000);
            
            async function loadStats() {
                try {
                    const response = await fetch('/cancellations/stats');
                    const data = await response.json();
                    
                    document.getElementById('total-cancellations').textContent = data.processing_stats.cancellations_detected;
                    document.getElementById('enriched-cancellations').textContent = data.processing_stats.cancellations_enriched;
                    document.getElementById('enrichment-rate').textContent = data.processing_stats.enrichment_rate + '%';
                    document.getElementById('feed-status').textContent = data.darwin_feed.connected ? 'Connected' : 'Disconnected';
                    
                } catch (error) {
                    console.error('Error loading stats:', error);
                }
            }
            
            async function loadCancellations() {
                try {
                    const response = await fetch('/cancellations?limit=20');
                    const data = await response.json();
                    
                    const container = document.getElementById('cancellations-list');
                    container.innerHTML = '';
                    
                    data.cancellations.forEach(c => {
                        const div = document.createElement('div');
                        div.className = c.darwin_enriched ? 'cancellation enriched' : 'cancellation';
                        
                        const badge = c.darwin_enriched ? '<span class="enriched-badge">ENRICHED</span>' : '<span class="basic-badge">BASIC</span>';
                        const route = c.darwin_enriched ? 
                            `${c.origin_tiploc_darwin || 'Unknown'} → ${c.destination_tiploc_darwin || 'Unknown'}` :
                            'Route information not available';
                        
                        const details = c.darwin_enriched ?
                            `Platform: ${c.origin_platform_darwin || 'TBC'} → ${c.destination_platform_darwin || 'TBC'} | TOC: ${c.toc_darwin || 'Unknown'}` :
                            'No enrichment data available';
                        
                        div.innerHTML = `
                            <div>
                                ${badge}
                                <strong>Train ${c.train_service_code}</strong> - ${c.reason_text}
                                <div class="route">${route}</div>
                                <div class="details">${details}</div>
                                <div class="details">RID: ${c.rid || 'N/A'} | ${new Date(c.cancelled_at).toLocaleString()}</div>
                            </div>
                        `;
                        container.appendChild(div);
                    });
                    
                } catch (error) {
                    console.error('Error loading cancellations:', error);
                }
            }
            
            // Load data when page loads
            document.addEventListener('DOMContentLoaded', function() {
                loadStats();
                loadCancellations();
            });
        </script>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>🚂 Enhanced Cancellations Dashboard</h1>
                <p>Real-time train cancellations with Darwin enrichment data</p>
                <button class="refresh-btn" onclick="refreshData()">Refresh Data</button>
            </div>
            
            <div class="stats">
                <div class="stat-card">
                    <div class="stat-number" id="total-cancellations">-</div>
                    <div>Total Cancellations</div>
                </div>
                <div class="stat-card">
                    <div class="stat-number" id="enriched-cancellations">-</div>
                    <div>Enriched Cancellations</div>
                </div>
                <div class="stat-card">
                    <div class="stat-number" id="enrichment-rate">-</div>
                    <div>Enrichment Rate</div>
                </div>
                <div class="stat-card">
                    <div class="stat-number" id="feed-status">-</div>
                    <div>Darwin Feed</div>
                </div>
            </div>
            
            <div class="cancellations">
                <h2>Recent Cancellations</h2>
                <div id="cancellations-list">
                    Loading...
                </div>
            </div>
        </div>
    </body>
    </html>
    """
    
    return dashboard_html


def _get_enrichment_summary(cancellations):
    """Generate enrichment summary for a list of cancellations."""
    total = len(cancellations)
    if total == 0:
        return {'total': 0, 'enriched': 0, 'basic': 0, 'enrichment_rate': 0}
    
    enriched = sum(1 for c in cancellations if c.get('darwin_enriched', False))
    basic = total - enriched
    rate = round((enriched / total) * 100, 1) if total > 0 else 0
    
    return {
        'total': total,
        'enriched': enriched,
        'basic': basic,
        'enrichment_rate': rate
    }


def _analyze_enrichment_patterns(cancellations):
    """Analyze enrichment patterns in recent cancellations."""
    total = len(cancellations)
    enriched_cancellations = [c for c in cancellations if c.get('darwin_enriched', False)]
    
    # TOC analysis
    toc_counts = {}
    for c in enriched_cancellations:
        toc = c.get('toc_darwin', 'Unknown')
        toc_counts[toc] = toc_counts.get(toc, 0) + 1
    
    # Route analysis
    route_counts = {}
    for c in enriched_cancellations:
        origin = c.get('origin_tiploc_darwin', 'Unknown')
        dest = c.get('destination_tiploc_darwin', 'Unknown')
        route = f"{origin}-{dest}"
        route_counts[route] = route_counts.get(route, 0) + 1
    
    return {
        'total_analyzed': total,
        'enriched_count': len(enriched_cancellations),
        'enrichment_rate': round((len(enriched_cancellations) / total * 100), 1) if total > 0 else 0,
        'top_tocs': sorted(toc_counts.items(), key=lambda x: x[1], reverse=True)[:5],
        'top_routes': sorted(route_counts.items(), key=lambda x: x[1], reverse=True)[:5]
    }


if __name__ == '__main__':
    logger.info("🚀 Starting Enhanced Cancellations API")
    
    # Initialize the service
    initialize_service()
    
    # Get configuration
    config = get_config()
    
    # Create logs directory
    Path("logs").mkdir(exist_ok=True)
    
    logger.info("✅ API server ready")
    logger.info(f"🌐 Enhanced API listening on: http://localhost:{config.flask_port}")
    logger.info(f"📊 Dashboard available at: http://localhost:{config.flask_port}/cancellations/dashboard")
    logger.info("🔗 API endpoints:")
    logger.info("   GET /cancellations - Recent cancellations with enrichment")
    logger.info("   GET /cancellations/enriched - Only enriched cancellations")
    logger.info("   GET /cancellations/stats - Service statistics")
    logger.info("   GET /cancellations/by-route - Cancellations grouped by route")
    
    # Run the app
    app.run(
        host=config.flask_host,
        port=config.flask_port,
        debug=config.flask_debug,
        threaded=True
    )