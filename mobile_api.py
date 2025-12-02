#!/usr/bin/env python3
"""
Mobile App API Interface
Simplified, mobile-friendly API endpoints for passenger applications
"""

from flask import Flask, jsonify, request
from datetime import datetime, timedelta
import requests
import json
import time

app = Flask(__name__)

# Configuration
BASE_API_URL = "http://localhost:8080"  # Enhanced API server
APP_VERSION = "1.0.0"

class MobileAPIService:
    """Mobile-optimized API service for passenger applications"""
    
    def __init__(self):
        self.app_name = "ScotRail Live"
        self.last_update = datetime.now()
    
    def get_enhanced_data(self, endpoint):
        """Fetch data from enhanced API server"""
        try:
            response = requests.get(f"{BASE_API_URL}{endpoint}", timeout=5)
            if response.status_code == 200:
                return response.json()
            return None
        except requests.exceptions.RequestException:
            return None
    
    def format_for_mobile(self, cancellations):
        """Format cancellation data for mobile consumption"""
        mobile_data = []
        
        for cancel in cancellations[:20]:  # Limit to 20 most recent
            # Basic mobile format
            mobile_item = {
                "id": cancel.get("rid", "unknown"),
                "service": cancel.get("train_service_code", "Unknown"),
                "status": "cancelled",
                "reason": self.simplify_reason(cancel.get("reason_text", "")),
                "timestamp": cancel.get("timestamp", ""),
                "severity": self.calculate_severity(cancel)
            }
            
            # Add enriched data if available
            if cancel.get("darwin_enriched"):
                mobile_item.update({
                    "enhanced": True,
                    "route": {
                        "from": cancel.get("origin_tiploc_darwin", ""),
                        "to": cancel.get("destination_tiploc_darwin", ""),
                        "departure_time": cancel.get("origin_time_darwin", ""),
                        "arrival_time": cancel.get("destination_time_darwin", "")
                    },
                    "platforms": {
                        "departure": cancel.get("origin_platform_darwin", ""),
                        "arrival": cancel.get("destination_platform_darwin", "")
                    },
                    "operator": cancel.get("toc_darwin", ""),
                    "stops_count": cancel.get("calling_points_count", 0)
                })
                
                # Add calling points for journey planning
                if cancel.get("calling_points_darwin"):
                    mobile_item["calling_points"] = [
                        {
                            "station": point.get("tiploc", ""),
                            "scheduled_time": point.get("scheduled_time", ""),
                            "platform": point.get("platform", "")
                        }
                        for point in cancel.get("calling_points_darwin", [])[:10]  # Limit stops
                    ]
            else:
                mobile_item["enhanced"] = False
            
            mobile_data.append(mobile_item)
        
        return mobile_data
    
    def simplify_reason(self, reason_text):
        """Simplify cancellation reason for mobile display"""
        if not reason_text:
            return "Service cancelled"
        
        # Extract key reasons
        reason_lower = reason_text.lower()
        if "weather" in reason_lower:
            return "Weather conditions"
        elif "strike" in reason_lower or "industrial action" in reason_lower:
            return "Industrial action"
        elif "technical" in reason_lower or "fault" in reason_lower:
            return "Technical issue"
        elif "staff" in reason_lower:
            return "Staff shortage"
        elif "infrastructure" in reason_lower:
            return "Infrastructure work"
        else:
            return "Service disruption"
    
    def calculate_severity(self, cancellation):
        """Calculate severity level for mobile alerts"""
        # High severity for rush hours or peak services
        timestamp = cancellation.get("timestamp", "")
        try:
            cancel_time = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
            hour = cancel_time.hour
            
            if 7 <= hour <= 9 or 17 <= hour <= 19:  # Peak hours
                return "high"
            elif 6 <= hour <= 22:  # Daytime
                return "medium"
            else:  # Late night/early morning
                return "low"
        except:
            return "medium"

mobile_service = MobileAPIService()

@app.route('/mobile/v1/cancellations', methods=['GET'])
def get_mobile_cancellations():
    """Mobile-optimized cancellations endpoint"""
    
    # Get query parameters
    limit = request.args.get('limit', 20, type=int)
    include_enriched_only = request.args.get('enriched_only', 'false').lower() == 'true'
    
    # Fetch from enhanced API
    endpoint = '/cancellations/enriched' if include_enriched_only else '/cancellations'
    data = mobile_service.get_enhanced_data(endpoint)
    
    if not data:
        return jsonify({
            "status": "error",
            "message": "Unable to fetch cancellation data",
            "timestamp": datetime.now().isoformat()
        }), 503
    
    # Format for mobile
    mobile_cancellations = mobile_service.format_for_mobile(data)
    
    return jsonify({
        "status": "success",
        "data": {
            "cancellations": mobile_cancellations[:limit],
            "total_count": len(mobile_cancellations),
            "last_updated": datetime.now().isoformat(),
            "enriched_only": include_enriched_only
        },
        "meta": {
            "app_version": APP_VERSION,
            "api_version": "1.0"
        }
    })

@app.route('/mobile/v1/alerts', methods=['GET'])
def get_mobile_alerts():
    """Push notification formatted alerts"""
    
    # Fetch recent cancellations
    data = mobile_service.get_enhanced_data('/cancellations')
    if not data:
        return jsonify({"status": "error", "alerts": []}), 503
    
    # Format as push notifications
    alerts = []
    for cancel in data[:5]:  # Only most recent 5 for alerts
        alert = {
            "id": f"cancel_{cancel.get('rid', '')}",
            "type": "cancellation",
            "title": f"Service {cancel.get('train_service_code', 'Unknown')} Cancelled",
            "message": mobile_service.simplify_reason(cancel.get('reason_text', '')),
            "severity": mobile_service.calculate_severity(cancel),
            "timestamp": cancel.get('timestamp', ''),
            "action_url": f"/mobile/v1/cancellation/{cancel.get('rid', '')}"
        }
        
        # Add route info if enriched
        if cancel.get('darwin_enriched'):
            route = f"{cancel.get('origin_tiploc_darwin', '')} → {cancel.get('destination_tiploc_darwin', '')}"
            alert["message"] += f" ({route})"
        
        alerts.append(alert)
    
    return jsonify({
        "status": "success", 
        "alerts": alerts,
        "timestamp": datetime.now().isoformat()
    })

@app.route('/mobile/v1/cancellation/<rid>', methods=['GET'])
def get_cancellation_detail(rid):
    """Detailed cancellation information for a specific RID"""
    
    # Fetch all cancellations and find the specific one
    data = mobile_service.get_enhanced_data('/cancellations')
    if not data:
        return jsonify({"status": "error", "message": "Service unavailable"}), 503
    
    # Find the specific cancellation
    cancellation = next((c for c in data if c.get('rid') == rid), None)
    if not cancellation:
        return jsonify({"status": "error", "message": "Cancellation not found"}), 404
    
    # Format detailed mobile response
    mobile_detail = mobile_service.format_for_mobile([cancellation])[0]
    
    # Add additional detail for single view
    if cancellation.get('darwin_enriched'):
        mobile_detail["journey_details"] = {
            "total_distance": "Calculated from calling points",
            "estimated_duration": "Based on schedule",
            "affected_passengers": "High impact service"
        }
    
    return jsonify({
        "status": "success",
        "data": mobile_detail,
        "timestamp": datetime.now().isoformat()
    })

@app.route('/mobile/v1/status', methods=['GET'])
def mobile_service_status():
    """Mobile app service status"""
    
    # Check backend service
    stats = mobile_service.get_enhanced_data('/cancellations/stats')
    backend_healthy = stats is not None
    
    return jsonify({
        "status": "healthy" if backend_healthy else "degraded",
        "services": {
            "live_feed": "operational" if backend_healthy else "unavailable",
            "enrichment": "available" if backend_healthy else "limited",
            "notifications": "active"
        },
        "stats": {
            "active_cancellations": stats.get('total_cancellations', 0) if stats else 0,
            "enrichment_rate": f"{stats.get('enrichment_rate', 0)}%" if stats else "0%"
        },
        "timestamp": datetime.now().isoformat()
    })

@app.route('/mobile/v1/journey-planning', methods=['POST'])
def mobile_journey_planning():
    """Journey planning with cancellation awareness"""
    
    data = request.get_json() or {}
    origin = data.get('origin', '')
    destination = data.get('destination', '')
    
    if not origin or not destination:
        return jsonify({
            "status": "error", 
            "message": "Origin and destination required"
        }), 400
    
    # Get current cancellations
    cancellations_data = mobile_service.get_enhanced_data('/cancellations/enriched')
    
    # Check for affected services on this route
    affected_services = []
    if cancellations_data:
        for cancel in cancellations_data:
            if (cancel.get('origin_tiploc_darwin', '').lower() == origin.lower() or
                cancel.get('destination_tiploc_darwin', '').lower() == destination.lower()):
                affected_services.append({
                    "service": cancel.get('train_service_code', ''),
                    "reason": mobile_service.simplify_reason(cancel.get('reason_text', ''))
                })
    
    return jsonify({
        "status": "success",
        "journey": {
            "origin": origin,
            "destination": destination,
            "affected_services": affected_services,
            "alternative_routes": "Contact station staff for current alternatives",
            "disruption_level": "high" if affected_services else "none"
        },
        "recommendations": [
            "Check live departures before traveling",
            "Consider alternative transport if multiple services affected",
            "Allow extra journey time"
        ] if affected_services else ["Journey appears normal"],
        "timestamp": datetime.now().isoformat()
    })

if __name__ == '__main__':
    print("🚀 Starting Mobile API Service for Phase 2")
    print("📱 Mobile endpoints:")
    print("   GET /mobile/v1/cancellations - Mobile cancellations")
    print("   GET /mobile/v1/alerts - Push notification alerts")  
    print("   GET /mobile/v1/cancellation/<rid> - Detailed cancellation")
    print("   GET /mobile/v1/status - Service status")
    print("   POST /mobile/v1/journey-planning - Journey planning")
    print()
    print("🌐 Mobile API listening on: http://localhost:5002")
    print("📊 Dashboard: http://localhost:5002")
    
    app.run(host='0.0.0.0', port=5002, debug=True)