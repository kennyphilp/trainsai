#!/usr/bin/env python3
"""
Simple Passenger Portal for testing
"""

from flask import Flask, jsonify
from datetime import datetime

app = Flask(__name__)

@app.route('/')
def home():
    """Simple home page"""
    return """
<!DOCTYPE html>
<html>
<head>
    <title>ScotRail Passenger Portal</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 40px; background: #f5f5f5; }
        .container { max-width: 800px; margin: 0 auto; background: white; padding: 30px; border-radius: 10px; }
        h1 { color: #0066cc; }
        .service-links { margin: 20px 0; }
        .service-links a { display: block; margin: 10px 0; padding: 10px; background: #e8f4fd; border-radius: 5px; text-decoration: none; color: #0066cc; }
    </style>
</head>
<body>
    <div class="container">
        <h1>🚊 ScotRail Passenger Portal</h1>
        <p>Welcome to the Darwin Rail AI System passenger interface.</p>
        
        <div class="service-links">
            <h3>Available Services:</h3>
            <a href="http://localhost:8080/cancellations/dashboard">📊 Enhanced API Dashboard (Port 8080)</a>
            <a href="http://localhost:5002/mobile/v1/status">📱 Mobile API Status (Port 5002)</a>
            <a href="http://localhost:5003/notifications/v1/status">🔔 Smart Notifications (Port 5003)</a>
            <a href="http://localhost:5005/display/v1/status">📺 Station Displays (Port 5005)</a>
        </div>
        
        <div style="margin-top: 30px; padding: 20px; background: #f0f8ff; border-radius: 5px;">
            <h3>System Status</h3>
            <p>✅ Passenger Portal: Active</p>
            <p>🔗 <a href="/health">Health Check</a> | <a href="/api/status">API Status</a></p>
        </div>
    </div>
</body>
</html>
    """

@app.route('/health')
def health():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'service': 'passenger_portal',
        'port': 5006,
        'timestamp': datetime.now().isoformat()
    })

@app.route('/api/status')
def api_status():
    """API status endpoint"""
    return jsonify({
        'service': 'passenger_portal',
        'status': 'running',
        'features': [
            'Simple web interface',
            'Service navigation',
            'Health monitoring'
        ],
        'timestamp': datetime.now().isoformat()
    })

if __name__ == '__main__':
    print("🚀 Starting Simple Passenger Portal")
    print("🌐 Simple Portal listening on: http://localhost:5006")
    print("📊 Web Portal: http://localhost:5006")
    print("✅ Basic passenger interface ready!")
    
    app.run(host='0.0.0.0', port=5006, debug=False)