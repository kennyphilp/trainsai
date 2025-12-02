#!/usr/bin/env python3
"""
Station Display Integration
Enhanced station displays with Darwin enrichment data
"""

from flask import Flask, jsonify, request, render_template_string
from datetime import datetime, timedelta
import requests
import json
from typing import List, Dict, Optional

class StationDisplayService:
    """Service for enhanced station display information"""
    
    def __init__(self, base_api_url="http://localhost:8080"):
        self.base_api_url = base_api_url
        
        # Station display configuration
        self.display_config = {
            'max_departures': 10,
            'update_interval': 30,  # seconds
            'alert_duration': 300,  # 5 minutes
            'priority_services': ['express', 'intercity'],
        }
        
        # Station-specific settings
        self.station_settings = {
            'GLASGOW': {'name': 'Glasgow Central', 'platforms': 15, 'type': 'major'},
            'EDINBUR': {'name': 'Edinburgh Waverley', 'platforms': 20, 'type': 'major'},
            'WATRLOO': {'name': 'London Waterloo', 'platforms': 24, 'type': 'major'},
            'GUILDFD': {'name': 'Guildford', 'platforms': 4, 'type': 'regional'},
            'STIRLNG': {'name': 'Stirling', 'platforms': 6, 'type': 'regional'},
        }
    
    def get_enhanced_cancellations(self) -> List[Dict]:
        """Fetch enhanced cancellations from API"""
        try:
            response = requests.get(f"{self.base_api_url}/cancellations", timeout=5)
            if response.status_code == 200:
                return response.json()
            return []
        except requests.exceptions.RequestException:
            return []
    
    def get_station_departures(self, station_code: str, platform: str = None) -> Dict:
        """Get departure information for station display"""
        
        # Get all cancellations
        cancellations = self.get_enhanced_cancellations()
        
        # Filter for this station
        station_cancellations = []
        for cancel in cancellations:
            if cancel.get('darwin_enriched'):
                origin = cancel.get('origin_tiploc_darwin', '')
                if origin == station_code:
                    # Filter by platform if specified
                    if platform is None or cancel.get('origin_platform_darwin') == platform:
                        station_cancellations.append(cancel)
        
        # Format for station display
        display_data = {
            'station': {
                'code': station_code,
                'name': self.station_settings.get(station_code, {}).get('name', station_code),
                'last_updated': datetime.now().strftime('%H:%M:%S'),
                'platform_filter': platform
            },
            'departures': [],
            'alerts': [],
            'service_updates': []
        }
        
        # Process cancellations into departure format
        for cancel in station_cancellations[:self.display_config['max_departures']]:
            departure = {
                'service': cancel.get('train_service_code', 'Unknown'),
                'destination': cancel.get('destination_tiploc_darwin', ''),
                'scheduled_time': cancel.get('origin_time_darwin', ''),
                'platform': cancel.get('origin_platform_darwin', 'TBC'),
                'status': 'CANCELLED',
                'reason': self._format_cancellation_reason(cancel.get('reason_text', '')),
                'operator': cancel.get('toc_darwin', ''),
                'calling_points': self._format_calling_points_display(
                    cancel.get('calling_points_darwin', [])
                ),
                'severity': self._assess_cancellation_severity(cancel),
                'alternative_info': self._generate_alternative_info(cancel)
            }
            display_data['departures'].append(departure)
        
        # Generate station alerts
        display_data['alerts'] = self._generate_station_alerts(station_cancellations, station_code)
        
        # Generate service updates
        display_data['service_updates'] = self._generate_service_updates(station_cancellations)
        
        return display_data
    
    def _format_cancellation_reason(self, reason_text: str) -> str:
        """Format cancellation reason for station display"""
        if not reason_text:
            return "Service cancelled - see station staff"
        
        # Extract reason code if present
        if "Reason code:" in reason_text:
            return reason_text.split("Reason code:")[0].strip()
        
        return reason_text[:50] + "..." if len(reason_text) > 50 else reason_text
    
    def _format_calling_points_display(self, calling_points: List[Dict]) -> List[str]:
        """Format calling points for station display"""
        if not calling_points:
            return []
        
        # Show first few calling points for display
        display_points = []
        for point in calling_points[:5]:
            station = point.get('tiploc', '')
            time = point.get('scheduled_time', '')
            if station and time:
                display_points.append(f"{station} ({time})")
        
        if len(calling_points) > 5:
            display_points.append("...")
        
        return display_points
    
    def _assess_cancellation_severity(self, cancellation: Dict) -> str:
        """Assess severity for station display priority"""
        current_time = datetime.now()
        
        # Check timing
        scheduled_time = cancellation.get('origin_time_darwin', '')
        if scheduled_time:
            try:
                # Assume today's date for simplicity
                scheduled_datetime = datetime.strptime(
                    f"{current_time.date()} {scheduled_time}", 
                    "%Y-%m-%d %H:%M"
                )
                
                # High severity if departure is soon
                time_diff = abs((scheduled_datetime - current_time).total_seconds() / 60)
                if time_diff <= 30:  # 30 minutes
                    return 'high'
                elif time_diff <= 60:  # 1 hour
                    return 'medium'
            except ValueError:
                pass
        
        # Check service importance
        service_code = cancellation.get('train_service_code', '')
        if any(priority in service_code.lower() for priority in self.display_config['priority_services']):
            return 'high'
        
        return 'medium'
    
    def _generate_alternative_info(self, cancellation: Dict) -> str:
        """Generate alternative travel information"""
        
        destination = cancellation.get('destination_tiploc_darwin', '')
        
        # Basic alternative suggestions
        alternatives = [
            "Next service to same destination",
            "Alternative routes available", 
            "Bus replacement service may be available"
        ]
        
        # More specific suggestions based on route
        if destination in ['GLASGOW', 'EDINBUR']:
            alternatives.insert(0, "Frequent services available on this route")
        
        return " | ".join(alternatives[:2])  # Limit for display space
    
    def _generate_station_alerts(self, cancellations: List[Dict], station_code: str) -> List[Dict]:
        """Generate station-wide alerts"""
        alerts = []
        
        if not cancellations:
            return alerts
        
        # Platform alerts
        platform_impacts = {}
        for cancel in cancellations:
            platform = cancel.get('origin_platform_darwin', '')
            if platform:
                platform_impacts[platform] = platform_impacts.get(platform, 0) + 1
        
        # Alert for platforms with multiple cancellations
        for platform, count in platform_impacts.items():
            if count >= 2:
                alerts.append({
                    'type': 'platform_disruption',
                    'level': 'warning',
                    'message': f"Multiple cancellations on Platform {platform}",
                    'duration': 300  # 5 minutes
                })
        
        # General disruption alert
        if len(cancellations) >= 3:
            alerts.append({
                'type': 'general_disruption',
                'level': 'notice',
                'message': f"Service disruptions affecting {len(cancellations)} departures",
                'duration': 600  # 10 minutes
            })
        
        return alerts
    
    def _generate_service_updates(self, cancellations: List[Dict]) -> List[str]:
        """Generate service update messages"""
        updates = []
        
        if not cancellations:
            updates.append("All services operating normally")
            return updates
        
        # Operator-specific updates
        operators = {}
        for cancel in cancellations:
            op = cancel.get('toc_darwin', 'Unknown')
            operators[op] = operators.get(op, 0) + 1
        
        for operator, count in operators.items():
            if count >= 2:
                updates.append(f"{operator} services: Multiple cancellations reported")
        
        # General updates
        updates.extend([
            "Passengers advised to check before traveling",
            "Station staff available for assistance",
            "Live departure boards updated continuously"
        ])
        
        return updates[:3]  # Limit for display space
    
    def get_platform_specific_info(self, station_code: str, platform: str) -> Dict:
        """Get platform-specific display information"""
        
        platform_data = self.get_station_departures(station_code, platform)
        
        # Add platform-specific details
        platform_info = {
            'platform': {
                'number': platform,
                'station': platform_data['station']['name'],
                'facilities': self._get_platform_facilities(station_code, platform),
                'accessibility': self._get_accessibility_info(station_code, platform)
            },
            'current_departures': platform_data['departures'],
            'next_24_hours': self._get_future_departures(station_code, platform),
            'safety_messages': [
                "Stand back from platform edge",
                "Keep personal belongings secure",
                "Report unattended items to staff"
            ],
            'last_updated': datetime.now().strftime('%H:%M:%S')
        }
        
        return platform_info
    
    def _get_platform_facilities(self, station_code: str, platform: str) -> List[str]:
        """Get platform facilities information"""
        # Basic facilities - would be expanded with real data
        return [
            "Waiting room",
            "Help point",
            "CCTV monitored"
        ]
    
    def _get_accessibility_info(self, station_code: str, platform: str) -> Dict:
        """Get accessibility information for platform"""
        return {
            'step_free_access': True,  # Would be real data
            'accessible_toilet': True,
            'hearing_loop': True,
            'assistance_available': "Contact station staff"
        }
    
    def _get_future_departures(self, station_code: str, platform: str) -> List[Dict]:
        """Get future scheduled departures (placeholder)"""
        # In real implementation, would fetch scheduled services
        return [
            {
                'time': '14:30',
                'service': '1A45',
                'destination': 'Edinburgh',
                'status': 'On time'
            },
            {
                'time': '15:00',
                'service': '1B23',
                'destination': 'Glasgow',
                'status': 'Expected'
            }
        ]

# Flask app for station displays
app = Flask(__name__)
station_service = StationDisplayService()

@app.route('/display/v1/station/<station_code>')
def station_display(station_code):
    """Main station display endpoint"""
    platform = request.args.get('platform')
    
    try:
        display_data = station_service.get_station_departures(station_code.upper(), platform)
        return jsonify({
            'status': 'success',
            'data': display_data,
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500

@app.route('/display/v1/platform/<station_code>/<platform>')
def platform_display(station_code, platform):
    """Platform-specific display endpoint"""
    
    try:
        platform_data = station_service.get_platform_specific_info(
            station_code.upper(), platform
        )
        return jsonify({
            'status': 'success',
            'data': platform_data,
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({
            'status': 'error', 
            'message': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500

@app.route('/display/v1/station/<station_code>/web')
def station_web_display(station_code):
    """Web-based station display"""
    
    platform = request.args.get('platform')
    display_data = station_service.get_station_departures(station_code.upper(), platform)
    
    # HTML template for station display
    html_template = """
<!DOCTYPE html>
<html>
<head>
    <title>{{ station_name }} - Live Departures</title>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        body { 
            font-family: 'Courier New', monospace; 
            background: #000; 
            color: #ffff00; 
            margin: 0; 
            padding: 20px;
        }
        .header { 
            text-align: center; 
            border-bottom: 2px solid #ffff00; 
            padding-bottom: 10px; 
            margin-bottom: 20px;
        }
        .station-name { font-size: 2em; margin: 0; }
        .last-updated { font-size: 1em; margin: 5px 0; }
        .departures { margin: 20px 0; }
        .departure { 
            display: flex; 
            justify-content: space-between; 
            padding: 10px; 
            border-bottom: 1px solid #666;
            background: #111;
        }
        .departure.cancelled { background: #330000; color: #ff6666; }
        .service { font-weight: bold; }
        .destination { flex-grow: 1; margin-left: 20px; }
        .time { min-width: 60px; }
        .platform { min-width: 80px; text-align: center; }
        .status { min-width: 100px; text-align: right; }
        .alerts { margin: 20px 0; }
        .alert { 
            padding: 10px; 
            margin: 5px 0; 
            background: #663300; 
            border: 1px solid #ff9900; 
            color: #ff9900;
        }
        .calling-points { font-size: 0.8em; color: #cccccc; margin-top: 5px; }
        .footer { 
            margin-top: 30px; 
            text-align: center; 
            border-top: 1px solid #666; 
            padding-top: 10px; 
            font-size: 0.9em;
        }
    </style>
    <script>
        setTimeout(function(){ location.reload(); }, 30000); // Auto-refresh every 30 seconds
    </script>
</head>
<body>
    <div class="header">
        <h1 class="station-name">{{ station_name }}</h1>
        <div class="last-updated">Last Updated: {{ last_updated }}</div>
        {% if platform_filter %}
        <div>Platform {{ platform_filter }} Only</div>
        {% endif %}
    </div>
    
    {% if alerts %}
    <div class="alerts">
        {% for alert in alerts %}
        <div class="alert">⚠️ {{ alert.message }}</div>
        {% endfor %}
    </div>
    {% endif %}
    
    <div class="departures">
        <div class="departure" style="background: #333; font-weight: bold;">
            <div class="service">Service</div>
            <div class="destination">Destination</div>
            <div class="time">Time</div>
            <div class="platform">Platform</div>
            <div class="status">Status</div>
        </div>
        
        {% for departure in departures %}
        <div class="departure cancelled">
            <div class="service">{{ departure.service }}</div>
            <div class="destination">
                {{ departure.destination }}
                {% if departure.calling_points %}
                <div class="calling-points">
                    Calling at: {{ departure.calling_points | join(', ') }}
                </div>
                {% endif %}
            </div>
            <div class="time">{{ departure.scheduled_time }}</div>
            <div class="platform">{{ departure.platform }}</div>
            <div class="status">{{ departure.status }}</div>
        </div>
        <div style="font-size: 0.8em; color: #ff9999; padding: 5px 10px;">
            {{ departure.reason }}
            {% if departure.alternative_info %}
            <br>💡 {{ departure.alternative_info }}
            {% endif %}
        </div>
        {% endfor %}
        
        {% if not departures %}
        <div class="departure">
            <div style="text-align: center; width: 100%; color: #00ff00;">
                ✅ No current cancellations - All services on time
            </div>
        </div>
        {% endif %}
    </div>
    
    <div class="footer">
        <div>🚂 Live departure information | Updates every 30 seconds</div>
        <div>For assistance, please contact station staff</div>
    </div>
</body>
</html>
    """
    
    return render_template_string(html_template, 
                                station_name=display_data['station']['name'],
                                last_updated=display_data['station']['last_updated'],
                                platform_filter=display_data['station']['platform_filter'],
                                departures=display_data['departures'],
                                alerts=display_data['alerts'])

@app.route('/display/v1/status')
def display_service_status():
    """Display service status"""
    try:
        # Test connection to enhanced API
        response = requests.get(f"{station_service.base_api_url}/cancellations/stats", timeout=5)
        api_healthy = response.status_code == 200
        
        return jsonify({
            'status': 'operational' if api_healthy else 'degraded',
            'services': {
                'enhanced_api': 'available' if api_healthy else 'unavailable',
                'station_displays': 'operational',
                'auto_refresh': 'active'
            },
            'update_interval': station_service.display_config['update_interval'],
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500

if __name__ == '__main__':
    print("🚀 Starting Station Display Service")
    print("📺 Display endpoints:")
    print("   GET /display/v1/station/{code} - Station departures JSON")
    print("   GET /display/v1/station/{code}/web - Web display")
    print("   GET /display/v1/platform/{code}/{platform} - Platform info")
    print("   GET /display/v1/status - Service status")
    print()
    print("🌐 Station Displays listening on: http://localhost:5005")
    print("📊 Station displays: http://localhost:5005")
    print("📋 Example: http://localhost:5005/display/v1/station/GLASGOW/web")
    
    app.run(host='0.0.0.0', port=5005, debug=True)