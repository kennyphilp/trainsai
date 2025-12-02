#!/usr/bin/env python3
"""
Passenger Web Portal
Responsive web interface for passengers with real-time updates
"""

from flask import Flask, render_template_string, jsonify, request
from datetime import datetime, timedelta
import requests
import json
import logging
import sys

# Configure detailed logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('passenger_portal.log'),
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)

class PassengerWebPortal:
    """Passenger-facing web portal service"""
    
    def __init__(self):
        logger.info("🔧 Initializing PassengerWebPortal class")
        self.services = {
            'enhanced_api': 'http://localhost:8080',
            'mobile_api': 'http://localhost:5002', 
            'notifications': 'http://localhost:5003',
            'routing': 'http://localhost:5004',
            'displays': 'http://localhost:5005'
        }
        logger.info(f"📋 Configured services: {list(self.services.keys())}")
    
    def get_service_data(self, service: str, endpoint: str):
        """Fetch data from microservices"""
        logger.debug(f"🔍 Requesting data from {service}: {endpoint}")
        try:
            base_url = self.services.get(service)
            if not base_url:
                logger.warning(f"❌ Service {service} not configured")
                return None
                
            full_url = f"{base_url}{endpoint}"
            logger.debug(f"📡 Making GET request to: {full_url}")
            
            response = requests.get(full_url, timeout=2)
            logger.debug(f"📊 Response status: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                logger.debug(f"✅ Successfully retrieved data from {service}")
                return data
            else:
                logger.warning(f"⚠️ Non-200 response from {service}: {response.status_code}")
                return None
                
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ Request failed for {service}{endpoint}: {e}")
            return None
        except Exception as e:
            logger.error(f"💥 Unexpected error getting data from {service}: {e}")
            return None
    
    def post_service_data(self, service: str, endpoint: str, data: dict):
        """Post data to microservices"""
        logger.debug(f"📤 Posting data to {service}: {endpoint}")
        try:
            base_url = self.services.get(service)
            if not base_url:
                logger.warning(f"❌ Service {service} not configured for POST")
                return None
                
            full_url = f"{base_url}{endpoint}"
            logger.debug(f"📡 Making POST request to: {full_url}")
            
            response = requests.post(
                full_url, 
                json=data, 
                timeout=2
            )
            logger.debug(f"📊 POST response status: {response.status_code}")
            
            if response.status_code == 200:
                result = response.json()
                logger.debug(f"✅ Successfully posted data to {service}")
                return result
            else:
                logger.warning(f"⚠️ Non-200 POST response from {service}: {response.status_code}")
                return None
                
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ POST request failed for {service}{endpoint}: {e}")
            return None
        except Exception as e:
            logger.error(f"💥 Unexpected error posting to {service}: {e}")
            return None

logger.info("🚀 Creating PassengerWebPortal instance")
portal = PassengerWebPortal()
logger.info("🌐 Creating Flask app")
app = Flask(__name__)

# Add error handlers
@app.errorhandler(500)
def internal_error(error):
    logger.error(f"💥 Internal server error: {error}")
    return jsonify({'error': 'Internal server error', 'message': str(error)}), 500

@app.errorhandler(404)
def not_found(error):
    logger.warning(f"❓ Page not found: {error}")
    return jsonify({'error': 'Page not found', 'message': str(error)}), 404

@app.errorhandler(Exception)
def handle_exception(e):
    logger.error(f"💥 Unhandled exception: {e}")
    import traceback
    logger.error(f"🔍 Traceback: {traceback.format_exc()}")
    return jsonify({'error': 'Unexpected error', 'message': str(e)}), 500

@app.route('/health')
def health():
    """Simple health check endpoint"""
    logger.debug("🩺 Health check requested")
    response_data = {
        'status': 'healthy', 
        'service': 'passenger_portal', 
        'timestamp': datetime.now().isoformat()
    }
    logger.debug(f"✅ Health check response: {response_data}")
    return jsonify(response_data)

@app.route('/')
def home():
    """Main passenger portal home page"""
    logger.info("🏠 Home page requested")
    
    # Initialize with empty data to prevent hanging on service calls
    cancellations_data = None
    recent_alerts = None
    mobile_status = None
    
    try:
        logger.info("📊 Starting service data collection")
        
        # Get current cancellation summary with short timeout
        logger.debug("📱 Requesting mobile API cancellations")
        cancellations_data = portal.get_service_data('mobile_api', '/mobile/v1/cancellations?limit=5')
        
        logger.debug("🔔 Requesting notifications recent alerts")
        recent_alerts = portal.get_service_data('notifications', '/notifications/v1/recent?limit=3')
        
        logger.debug("📊 Requesting mobile API status")
        mobile_status = portal.get_service_data('mobile_api', '/mobile/v1/status')
        
        logger.info("✅ Service data collection complete")
        
    except Exception as e:
        # Continue with empty data if services unavailable
        logger.error(f"💥 Exception during service data collection: {e}")
        pass
    
    html_template = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ScotRail Live - Passenger Portal</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            line-height: 1.6;
            color: #333;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
        }
        
        .container {
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
        }
        
        .header {
            background: rgba(255, 255, 255, 0.95);
            backdrop-filter: blur(10px);
            border-radius: 15px;
            padding: 20px;
            margin-bottom: 20px;
            text-align: center;
            box-shadow: 0 8px 25px rgba(0,0,0,0.1);
        }
        
        .header h1 {
            color: #2c3e50;
            font-size: 2.5em;
            margin-bottom: 10px;
        }
        
        .header p {
            color: #7f8c8d;
            font-size: 1.1em;
        }
        
        .status-banner {
            background: {{ status_color }};
            color: white;
            padding: 15px;
            border-radius: 10px;
            margin-bottom: 20px;
            text-align: center;
            font-weight: bold;
        }
        
        .card-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }
        
        .card {
            background: rgba(255, 255, 255, 0.95);
            backdrop-filter: blur(10px);
            border-radius: 15px;
            padding: 20px;
            box-shadow: 0 8px 25px rgba(0,0,0,0.1);
            transition: transform 0.3s ease;
        }
        
        .card:hover {
            transform: translateY(-5px);
        }
        
        .card h3 {
            color: #2c3e50;
            margin-bottom: 15px;
            display: flex;
            align-items: center;
            gap: 10px;
        }
        
        .cancellation-item {
            background: #f8f9fa;
            border-left: 4px solid #e74c3c;
            padding: 15px;
            margin: 10px 0;
            border-radius: 5px;
        }
        
        .cancellation-header {
            font-weight: bold;
            color: #e74c3c;
            margin-bottom: 5px;
        }
        
        .cancellation-route {
            color: #7f8c8d;
            font-size: 0.9em;
        }
        
        .alert-item {
            background: #fff3cd;
            border: 1px solid #ffeaa7;
            padding: 10px;
            margin: 5px 0;
            border-radius: 5px;
            color: #856404;
        }
        
        .nav-buttons {
            display: flex;
            flex-wrap: wrap;
            gap: 15px;
            justify-content: center;
            margin-top: 30px;
        }
        
        .nav-button {
            background: linear-gradient(45deg, #667eea, #764ba2);
            color: white;
            padding: 15px 30px;
            border: none;
            border-radius: 25px;
            font-size: 1em;
            font-weight: bold;
            text-decoration: none;
            display: inline-block;
            transition: all 0.3s ease;
            box-shadow: 0 4px 15px rgba(0,0,0,0.2);
        }
        
        .nav-button:hover {
            transform: translateY(-2px);
            box-shadow: 0 6px 20px rgba(0,0,0,0.3);
        }
        
        .footer {
            text-align: center;
            color: rgba(255, 255, 255, 0.8);
            margin-top: 40px;
            padding: 20px;
        }
        
        .status-indicator {
            display: inline-block;
            width: 12px;
            height: 12px;
            border-radius: 50%;
            margin-right: 8px;
        }
        
        .status-healthy { background: #2ecc71; }
        .status-warning { background: #f39c12; }
        .status-error { background: #e74c3c; }
        
        @media (max-width: 768px) {
            .container { padding: 10px; }
            .header h1 { font-size: 2em; }
            .card-grid { grid-template-columns: 1fr; }
            .nav-buttons { flex-direction: column; align-items: center; }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🚂 ScotRail Live</h1>
            <p>Real-time railway information for passengers</p>
            <p><small>Last updated: {{ current_time }}</small></p>
        </div>
        
        {% if service_status %}
        <div class="status-banner">
            <span class="status-indicator {{ status_class }}"></span>
            Service Status: {{ service_status }} | 
            Live Feed: {{ feed_status }} | 
            Enrichment: {{ enrichment_rate }}
        </div>
        {% endif %}
        
        <div class="card-grid">
            <div class="card">
                <h3>🚨 Recent Cancellations</h3>
                {% if cancellations %}
                    {% for cancel in cancellations %}
                    <div class="cancellation-item">
                        <div class="cancellation-header">
                            Service {{ cancel.service }} - {{ cancel.status }}
                        </div>
                        <div class="cancellation-route">
                            {% if cancel.enhanced %}
                                {{ cancel.route.from }} → {{ cancel.route.to }}
                                {% if cancel.route.departure_time %}
                                    ({{ cancel.route.departure_time }})
                                {% endif %}
                                {% if cancel.platforms.departure %}
                                    Platform {{ cancel.platforms.departure }}
                                {% endif %}
                            {% else %}
                                Limited information available
                            {% endif %}
                        </div>
                        <div style="margin-top: 5px; font-size: 0.9em; color: #e74c3c;">
                            {{ cancel.reason }}
                        </div>
                    </div>
                    {% endfor %}
                {% else %}
                <div style="color: #27ae60; text-align: center; padding: 20px;">
                    ✅ No current cancellations reported
                </div>
                {% endif %}
            </div>
            
            <div class="card">
                <h3>📢 Service Alerts</h3>
                {% if alerts %}
                    {% for alert in alerts %}
                    <div class="alert-item">
                        <strong>{{ alert.title }}</strong><br>
                        {{ alert.message }}
                        <div style="font-size: 0.8em; margin-top: 5px;">
                            {{ alert.timestamp }}
                        </div>
                    </div>
                    {% endfor %}
                {% else %}
                <div style="color: #27ae60; text-align: center; padding: 20px;">
                    ✅ No current alerts
                </div>
                {% endif %}
            </div>
            
            <div class="card">
                <h3>🗺️ Journey Planner</h3>
                <p style="margin-bottom: 15px;">Plan your journey with real-time disruption information</p>
                <form id="journey-form" style="display: flex; flex-direction: column; gap: 10px;">
                    <input type="text" placeholder="From (e.g., GLASGOW)" 
                           id="origin" style="padding: 10px; border: 1px solid #ddd; border-radius: 5px;">
                    <input type="text" placeholder="To (e.g., EDINBUR)" 
                           id="destination" style="padding: 10px; border: 1px solid #ddd; border-radius: 5px;">
                    <button type="submit" style="padding: 10px; background: #3498db; color: white; 
                            border: none; border-radius: 5px; cursor: pointer;">
                        Plan Journey
                    </button>
                </form>
                <div id="journey-results" style="margin-top: 15px;"></div>
            </div>
        </div>
        
        <div class="nav-buttons">
            <a href="/mobile" class="nav-button">📱 Mobile API Demo</a>
            <a href="/notifications" class="nav-button">📢 Notifications</a>
            <a href="/station/GLASGOW" class="nav-button">🏢 Station Displays</a>
            <a href="/routing" class="nav-button">🗺️ Route Planning</a>
            <a href="/status" class="nav-button">📊 System Status</a>
        </div>
        
        <div class="footer">
            <p>🚂 ScotRail Live - Powered by Darwin Data Feeds</p>
            <p>Real-time cancellation information with intelligent enrichment</p>
        </div>
    </div>
    
    <script>
        // Auto-refresh every 30 seconds
        setTimeout(() => location.reload(), 30000);
        
        // Journey planning
        document.getElementById('journey-form').addEventListener('submit', async (e) => {
            e.preventDefault();
            
            const origin = document.getElementById('origin').value.trim().toUpperCase();
            const destination = document.getElementById('destination').value.trim().toUpperCase();
            const resultsDiv = document.getElementById('journey-results');
            
            if (!origin || !destination) {
                resultsDiv.innerHTML = '<div style="color: #e74c3c;">Please enter both origin and destination</div>';
                return;
            }
            
            resultsDiv.innerHTML = '<div>Planning route...</div>';
            
            try {
                const response = await fetch('/api/journey-plan', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ origin, destination })
                });
                
                const data = await response.json();
                
                if (data.status === 'success') {
                    const route = data.data;
                    let html = `<div style="background: #e8f5e8; padding: 10px; border-radius: 5px;">`;
                    html += `<strong>${route.journey.origin_name} → ${route.journey.destination_name}</strong><br>`;
                    html += `Disruption Level: <span style="color: ${route.disruption_analysis.level === 'high' ? '#e74c3c' : route.disruption_analysis.level === 'medium' ? '#f39c12' : '#27ae60'}">${route.disruption_analysis.level}</span><br>`;
                    
                    if (route.recommendations.length > 0) {
                        html += `<div style="margin-top: 10px; font-size: 0.9em;">`;
                        route.recommendations.forEach(rec => {
                            html += `• ${rec}<br>`;
                        });
                        html += `</div>`;
                    }
                    html += `</div>`;
                    
                    resultsDiv.innerHTML = html;
                } else {
                    resultsDiv.innerHTML = `<div style="color: #e74c3c;">${data.message || 'Planning failed'}</div>`;
                }
            } catch (error) {
                resultsDiv.innerHTML = '<div style="color: #e74c3c;">Network error - please try again</div>';
            }
        });
    </script>
</body>
</html>
    """
    
    # Determine status colors and classes
    status_color = "#27ae60"  # Green default
    status_class = "status-healthy"
    service_status = "Operational"
    feed_status = "Active"
    enrichment_rate = "Available"
    
    if mobile_status:
        if mobile_status.get('status') != 'healthy':
            status_color = "#f39c12"
            status_class = "status-warning"
            service_status = "Degraded"
        
        services = mobile_status.get('services', {})
        feed_status = services.get('live_feed', 'Unknown')
        enrichment_rate = mobile_status.get('stats', {}).get('enrichment_rate', '0%')
    
    # Process cancellations data
    cancellations = []
    if cancellations_data and cancellations_data.get('status') == 'success':
        cancellations = cancellations_data.get('data', {}).get('cancellations', [])
    
    # Process alerts data  
    alerts = []
    if recent_alerts and recent_alerts.get('status') == 'success':
        alerts = recent_alerts.get('notifications', [])
    
    return render_template_string(html_template,
                                current_time=datetime.now().strftime('%H:%M:%S'),
                                status_color=status_color,
                                status_class=status_class,
                                service_status=service_status,
                                feed_status=feed_status,
                                enrichment_rate=enrichment_rate,
                                cancellations=cancellations,
                                alerts=alerts)

@app.route('/mobile')
def mobile_demo():
    """Mobile API demonstration page"""
    
    mobile_data = portal.get_service_data('mobile_api', '/mobile/v1/cancellations')
    
    html_template = """
<!DOCTYPE html>
<html>
<head>
    <title>Mobile API Demo</title>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; background: #f5f5f5; }
        .container { max-width: 600px; margin: 0 auto; background: white; padding: 20px; border-radius: 10px; }
        .header { text-align: center; margin-bottom: 20px; padding-bottom: 20px; border-bottom: 1px solid #eee; }
        .cancellation { background: #fff5f5; border-left: 4px solid #e74c3c; padding: 15px; margin: 10px 0; border-radius: 5px; }
        .nav { margin-top: 30px; text-align: center; }
        .nav a { display: inline-block; margin: 5px; padding: 10px 20px; background: #3498db; color: white; text-decoration: none; border-radius: 5px; }
        .json-view { background: #f8f9fa; border: 1px solid #dee2e6; padding: 15px; border-radius: 5px; font-family: monospace; font-size: 12px; overflow-x: auto; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>📱 Mobile API Demo</h1>
            <p>Real-time mobile-optimized cancellation data</p>
        </div>
        
        {% if mobile_data and mobile_data.status == 'success' %}
        <h3>Recent Cancellations (Mobile Format)</h3>
        {% for cancel in mobile_data.data.cancellations[:3] %}
        <div class="cancellation">
            <strong>{{ cancel.service }} - {{ cancel.status.upper() }}</strong><br>
            <span style="color: #666;">{{ cancel.reason }}</span><br>
            {% if cancel.enhanced %}
            <div style="margin-top: 10px; font-size: 0.9em;">
                <strong>Route:</strong> {{ cancel.route.from }} → {{ cancel.route.to }}<br>
                <strong>Time:</strong> {{ cancel.route.departure_time }}<br>
                <strong>Platform:</strong> {{ cancel.platforms.departure or 'TBC' }}<br>
                <strong>Operator:</strong> {{ cancel.operator }}
            </div>
            {% endif %}
        </div>
        {% endfor %}
        
        <h3>Raw API Response</h3>
        <div class="json-view">{{ mobile_data | tojson(indent=2) }}</div>
        
        {% else %}
        <div style="color: #e74c3c; text-align: center; padding: 20px;">
            ❌ Mobile API not available
        </div>
        {% endif %}
        
        <div class="nav">
            <a href="/">← Back to Portal</a>
            <a href="/mobile/v1/cancellations" target="_blank">View API Endpoint</a>
        </div>
    </div>
</body>
</html>
    """
    
    return render_template_string(html_template, mobile_data=mobile_data)

@app.route('/notifications')
def notifications_demo():
    """Notifications demonstration page"""
    
    notifications_data = portal.get_service_data('notifications', '/notifications/v1/recent')
    
    html_template = """
<!DOCTYPE html>
<html>
<head>
    <title>Notifications Demo</title>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; background: #f5f5f5; }
        .container { max-width: 800px; margin: 0 auto; background: white; padding: 20px; border-radius: 10px; }
        .notification { background: #f8f9fa; border-left: 4px solid #17a2b8; padding: 15px; margin: 10px 0; border-radius: 5px; }
        .notification.high { border-left-color: #dc3545; background: #fff5f5; }
        .notification.medium { border-left-color: #ffc107; background: #fffdf5; }
        .nav { margin-top: 30px; text-align: center; }
        .nav a { display: inline-block; margin: 5px; padding: 10px 20px; background: #3498db; color: white; text-decoration: none; border-radius: 5px; }
    </style>
</head>
<body>
    <div class="container">
        <h1>📢 Smart Notifications Demo</h1>
        
        {% if notifications_data and notifications_data.status == 'success' %}
        <h3>Recent Notifications ({{ notifications_data.count }} total)</h3>
        
        {% for notification in notifications_data.notifications %}
        <div class="notification {{ notification.priority }}">
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <strong>{{ notification.title }}</strong>
                <span style="background: #{{ 'dc3545' if notification.priority == 'high' else 'ffc107' if notification.priority == 'medium' else '28a745' }}; color: white; padding: 2px 8px; border-radius: 10px; font-size: 0.8em;">
                    {{ notification.priority.upper() }}
                </span>
            </div>
            <p>{{ notification.message }}</p>
            <div style="font-size: 0.8em; color: #666; margin-top: 10px;">
                Type: {{ notification.type }} | Channels: {{ notification.channels | join(', ') }}
            </div>
        </div>
        {% endfor %}
        
        {% else %}
        <div style="color: #e74c3c; text-align: center; padding: 20px;">
            ❌ Notifications service not available
        </div>
        {% endif %}
        
        <div class="nav">
            <a href="/">← Back to Portal</a>
        </div>
    </div>
</body>
</html>
    """
    
    return render_template_string(html_template, notifications_data=notifications_data)

@app.route('/station/<station_code>')
def station_demo(station_code):
    """Station display demonstration"""
    
    station_data = portal.get_service_data('displays', f'/display/v1/station/{station_code}')
    
    return f"""
    <div style="text-align: center; padding: 40px;">
        <h2>Station Display Demo</h2>
        <p>Station: {station_code}</p>
        <div style="margin: 20px;">
            <a href="{portal.services['displays']}/display/v1/station/{station_code}/web" 
               target="_blank" 
               style="display: inline-block; padding: 15px 30px; background: #3498db; color: white; text-decoration: none; border-radius: 10px; margin: 10px;">
               🖥️ View Live Station Display
            </a>
        </div>
        <div>
            <a href="/" style="color: #3498db;">← Back to Portal</a>
        </div>
    </div>
    """

@app.route('/routing')
def routing_demo():
    """Routing demonstration page"""
    
    return """
    <div style="text-align: center; padding: 40px; font-family: Arial, sans-serif;">
        <h2>🗺️ Alternative Routing Demo</h2>
        <p>Intelligent route planning with disruption awareness</p>
        
        <form id="routing-form" style="margin: 30px; max-width: 400px; margin-left: auto; margin-right: auto;">
            <div style="margin: 10px;">
                <input type="text" placeholder="Origin (e.g., GLASGOW)" id="route-origin" 
                       style="width: 100%; padding: 10px; border: 1px solid #ddd; border-radius: 5px;">
            </div>
            <div style="margin: 10px;">
                <input type="text" placeholder="Destination (e.g., EDINBUR)" id="route-destination"
                       style="width: 100%; padding: 10px; border: 1px solid #ddd; border-radius: 5px;">
            </div>
            <button type="submit" style="width: 100%; padding: 15px; background: #3498db; color: white; border: none; border-radius: 5px; cursor: pointer;">
                Plan Route
            </button>
        </form>
        
        <div id="routing-results" style="margin: 20px; text-align: left; max-width: 600px; margin-left: auto; margin-right: auto;"></div>
        
        <div style="margin-top: 30px;">
            <a href="/" style="color: #3498db;">← Back to Portal</a>
        </div>
        
        <script>
            document.getElementById('routing-form').addEventListener('submit', async (e) => {
                e.preventDefault();
                
                const origin = document.getElementById('route-origin').value.trim();
                const destination = document.getElementById('route-destination').value.trim();
                const resultsDiv = document.getElementById('routing-results');
                
                if (!origin || !destination) {
                    resultsDiv.innerHTML = '<div style="color: #e74c3c; padding: 10px;">Please enter both origin and destination</div>';
                    return;
                }
                
                resultsDiv.innerHTML = '<div style="text-align: center; padding: 20px;">🔄 Planning route...</div>';
                
                try {
                    const response = await fetch('/api/journey-plan', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ origin: origin.toUpperCase(), destination: destination.toUpperCase() })
                    });
                    
                    const data = await response.json();
                    
                    if (data.status === 'success') {
                        const route = data.data;
                        let html = '<div style="background: white; padding: 20px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1);">';
                        html += `<h3>${route.journey.origin_name} → ${route.journey.destination_name}</h3>`;
                        html += `<p><strong>Disruption Level:</strong> <span style="color: ${route.disruption_analysis.level === 'high' ? '#e74c3c' : route.disruption_analysis.level === 'medium' ? '#f39c12' : '#27ae60'}">${route.disruption_analysis.level}</span></p>`;
                        
                        if (route.recommendations.length > 0) {
                            html += '<h4>Recommendations:</h4><ul>';
                            route.recommendations.forEach(rec => {
                                html += `<li>${rec}</li>`;
                            });
                            html += '</ul>';
                        }
                        
                        if (route.alternative_transport.length > 0) {
                            html += '<h4>Alternative Transport:</h4>';
                            route.alternative_transport.forEach(alt => {
                                html += `<div style="background: #f8f9fa; padding: 10px; margin: 5px 0; border-radius: 5px;">`;
                                html += `<strong>${alt.mode}</strong> - ${alt.cost} (${alt.duration_minutes} min)<br>`;
                                html += `<small>${alt.description}</small>`;
                                html += `</div>`;
                            });
                        }
                        
                        html += '</div>';
                        resultsDiv.innerHTML = html;
                    } else {
                        resultsDiv.innerHTML = `<div style="color: #e74c3c; padding: 10px;">${data.message || 'Route planning failed'}</div>`;
                    }
                } catch (error) {
                    resultsDiv.innerHTML = '<div style="color: #e74c3c; padding: 10px;">Network error - please try again</div>';
                }
            });
        </script>
    </div>
    """

@app.route('/status')
def system_status():
    """System status page"""
    
    # Check all services
    services_status = {}
    for service_name, base_url in portal.services.items():
        try:
            if service_name == 'enhanced_api':
                endpoint = '/cancellations/stats'
            elif service_name == 'mobile_api':
                endpoint = '/mobile/v1/status'
            elif service_name == 'notifications':
                endpoint = '/notifications/v1/status'
            elif service_name == 'routing':
                endpoint = '/routing/v1/disruptions'
            elif service_name == 'displays':
                endpoint = '/display/v1/status'
            else:
                continue
                
            response = requests.get(f"{base_url}{endpoint}", timeout=5)
            services_status[service_name] = {
                'status': 'healthy' if response.status_code == 200 else 'error',
                'response_time': 'Fast',
                'url': base_url
            }
        except:
            services_status[service_name] = {
                'status': 'unavailable',
                'response_time': 'N/A',
                'url': base_url
            }
    
    html_template = f"""
    <div style="font-family: Arial, sans-serif; max-width: 800px; margin: 40px auto; padding: 20px;">
        <h1>📊 System Status Dashboard</h1>
        <p>Phase 2 Passenger-Facing Integration Services</p>
        
        <div style="margin: 30px 0;">
            <h2>Service Health</h2>
            {''.join([f'''
            <div style="background: {'#d4edda' if status['status'] == 'healthy' else '#f8d7da'}; 
                        border: 1px solid {'#c3e6cb' if status['status'] == 'healthy' else '#f5c6cb'}; 
                        padding: 15px; margin: 10px 0; border-radius: 5px;">
                <strong>{name.replace('_', ' ').title()}</strong> 
                <span style="float: right; color: {'#155724' if status['status'] == 'healthy' else '#721c24'};">
                    {'✅ Healthy' if status['status'] == 'healthy' else '❌ ' + status['status'].title()}
                </span><br>
                <small>URL: {status['url']} | Response: {status['response_time']}</small>
            </div>
            ''' for name, status in services_status.items()])}
        </div>
        
        <div style="margin: 30px 0;">
            <h2>Phase 2 Features</h2>
            <ul>
                <li>✅ Mobile App API Interface</li>
                <li>✅ Smart Notifications System</li>
                <li>✅ Alternative Routing Engine</li>
                <li>✅ Station Display Integration</li>
                <li>✅ Passenger Web Portal</li>
            </ul>
        </div>
        
        <div style="text-align: center; margin-top: 30px;">
            <a href="/" style="display: inline-block; padding: 10px 20px; background: #3498db; color: white; text-decoration: none; border-radius: 5px;">
                ← Back to Portal
            </a>
        </div>
    </div>
    """
    
    return html_template

@app.route('/api/journey-plan', methods=['POST'])
def api_journey_plan():
    """Journey planning API endpoint"""
    
    data = request.get_json() or {}
    origin = data.get('origin', '').upper()
    destination = data.get('destination', '').upper()
    
    if not origin or not destination:
        return jsonify({'status': 'error', 'message': 'Origin and destination required'}), 400
    
    # Call routing service
    routing_data = portal.post_service_data('routing', '/routing/v1/plan', {
        'origin': origin,
        'destination': destination,
        'preferences': {}
    })
    
    if routing_data and routing_data.get('status') == 'success':
        return jsonify({'status': 'success', 'data': routing_data['data']})
    else:
        return jsonify({'status': 'error', 'message': 'Route planning service unavailable'}), 503

if __name__ == '__main__':
    logger.info("🚀 Starting Passenger Web Portal")
    logger.info("🌐 Features:")
    logger.info("   • Real-time cancellation dashboard")
    logger.info("   • Journey planning with disruption awareness") 
    logger.info("   • Mobile API integration")
    logger.info("   • Smart notifications display")
    logger.info("   • Station display access")
    logger.info("   • Alternative routing")
    logger.info("")
    
    # Test Flask app creation
    logger.info("🧪 Testing Flask app configuration")
    logger.info(f"📋 App name: {app.name}")
    logger.info(f"🛡️  Debug mode: {app.debug}")
    
    # Test route registration
    logger.info("🛣️  Checking registered routes:")
    for rule in app.url_map.iter_rules():
        logger.info(f"   {rule.methods} {rule.rule}")
    
    # Test portal initialization
    logger.info("🔧 Testing portal service connections:")
    for service_name, service_url in portal.services.items():
        logger.info(f"   {service_name}: {service_url}")
    
    logger.info("🌐 Passenger Portal listening on: http://localhost:5006")
    logger.info("📊 Web Portal: http://localhost:5006")
    logger.info("🎯 Complete passenger-facing interface ready!")
    
    try:
        logger.info("🚀 Starting Flask development server...")
        app.run(host='0.0.0.0', port=5006, debug=False)
    except Exception as e:
        logger.error(f"💥 Failed to start Flask server: {e}")
        import traceback
        logger.error(f"🔍 Traceback: {traceback.format_exc()}")
        raise