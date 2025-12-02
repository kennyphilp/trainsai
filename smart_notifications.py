#!/usr/bin/env python3
"""
Smart Notifications System
Proactive passenger alerts using Darwin enrichment data
"""

import json
import time
import threading
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from typing import List, Dict, Optional
import requests
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class Notification:
    """Smart notification data structure"""
    id: str
    type: str  # 'cancellation', 'delay', 'platform_change', 'proactive'
    title: str
    message: str
    priority: str  # 'low', 'medium', 'high', 'critical'
    timestamp: str
    expires_at: str
    data: Dict
    channels: List[str]  # ['push', 'email', 'sms', 'app']

class SmartNotificationEngine:
    """Advanced notification engine with proactive alerts"""
    
    def __init__(self, base_api_url="http://localhost:8080"):
        self.base_api_url = base_api_url
        self.notification_history = []
        self.subscription_db = {}  # Simulated subscriber database
        self.running = False
        self.last_check = datetime.now()
        
        # Notification rules
        self.rules = {
            'peak_hours': [(7, 9), (17, 19)],  # Morning and evening peaks
            'high_impact_routes': ['WATRLOO', 'GUILDFD', 'EDINBUR', 'GLASGOW'],
            'priority_operators': ['SW', 'SR', 'CS'],
        }
    
    def subscribe_user(self, user_id: str, preferences: Dict):
        """Subscribe user to notifications"""
        self.subscription_db[user_id] = {
            'preferences': preferences,
            'subscribed_at': datetime.now().isoformat(),
            'active': True
        }
        logger.info(f"User {user_id} subscribed to notifications")
    
    def get_enhanced_cancellations(self) -> Optional[List[Dict]]:
        """Fetch latest cancellations from enhanced API"""
        try:
            response = requests.get(f"{self.base_api_url}/cancellations", timeout=5)
            if response.status_code == 200:
                data = response.json()
                # Ensure we have a list of dictionaries
                if isinstance(data, list):
                    return data
                elif isinstance(data, dict):
                    # Sometimes API might return a single object or wrapper
                    if 'cancellations' in data:
                        return data['cancellations'] if isinstance(data['cancellations'], list) else []
                    elif 'data' in data:
                        return data['data'] if isinstance(data['data'], list) else []
                    else:
                        logger.warning(f"Unexpected data format from API: {type(data)}")
                        return []
                else:
                    logger.warning(f"API returned non-list data: {type(data)}")
                    return []
            else:
                logger.warning(f"API returned status {response.status_code}")
                return None
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to fetch cancellations: {e}")
            return None
        except ValueError as e:
            logger.error(f"Failed to parse JSON response: {e}")
            return None
    
    def analyze_impact(self, cancellation: Dict) -> str:
        """Analyze passenger impact of cancellation"""
        current_hour = datetime.now().hour
        
        # Check if it's peak hours
        is_peak = any(start <= current_hour <= end for start, end in self.rules['peak_hours'])
        
        # Check if it's a high-impact route
        origin = cancellation.get('origin_tiploc_darwin', '')
        destination = cancellation.get('destination_tiploc_darwin', '')
        is_high_impact_route = (origin in self.rules['high_impact_routes'] or 
                               destination in self.rules['high_impact_routes'])
        
        # Check operator priority
        operator = cancellation.get('toc_darwin', '')
        is_priority_operator = operator in self.rules['priority_operators']
        
        # Check calling points count (longer journeys = higher impact)
        calling_points = cancellation.get('calling_points_count', 0)
        is_long_journey = calling_points > 5
        
        if is_peak and is_high_impact_route and is_priority_operator:
            return 'critical'
        elif (is_peak and is_high_impact_route) or (is_priority_operator and is_long_journey):
            return 'high'
        elif is_peak or is_high_impact_route or calling_points > 3:
            return 'medium'
        else:
            return 'low'
    
    def create_cancellation_notification(self, cancellation: Dict) -> Notification:
        """Create smart notification for cancellation"""
        rid = cancellation.get('rid', '')
        service = cancellation.get('train_service_code', 'Unknown')
        timestamp = datetime.now().isoformat()
        
        # Determine priority based on impact analysis
        priority = self.analyze_impact(cancellation)
        
        # Base notification
        if cancellation.get('darwin_enriched'):
            # Enhanced notification with Darwin data
            origin = cancellation.get('origin_tiploc_darwin', 'Unknown')
            destination = cancellation.get('destination_tiploc_darwin', 'Unknown')
            departure_time = cancellation.get('origin_time_darwin', '')
            platform = cancellation.get('origin_platform_darwin', '')
            
            title = f"Service {service} Cancelled"
            message = f"{origin} → {destination}"
            if departure_time:
                message += f" departing {departure_time}"
            if platform:
                message += f" from Platform {platform}"
            
            # Add calling points for affected passengers
            calling_points = cancellation.get('calling_points_darwin', [])
            affected_stations = [cp.get('tiploc', '') for cp in calling_points[:5]]
            
            notification_data = {
                'service_code': service,
                'route': {'origin': origin, 'destination': destination},
                'scheduled_departure': departure_time,
                'platform': platform,
                'affected_stations': affected_stations,
                'reason': cancellation.get('reason_text', ''),
                'operator': cancellation.get('toc_darwin', ''),
                'enriched': True
            }
        else:
            # Basic notification
            title = f"Service {service} Cancelled"
            message = "Check station displays for details"
            notification_data = {
                'service_code': service,
                'reason': cancellation.get('reason_text', ''),
                'enriched': False
            }
        
        # Determine notification channels based on priority
        channels = ['push', 'app']
        if priority in ['high', 'critical']:
            channels.extend(['email', 'sms'])
        
        return Notification(
            id=f"cancel_{rid}_{int(time.time())}",
            type='cancellation',
            title=title,
            message=message,
            priority=priority,
            timestamp=timestamp,
            expires_at=(datetime.now() + timedelta(hours=6)).isoformat(),
            data=notification_data,
            channels=channels
        )
    
    def create_proactive_alerts(self, cancellations: List[Dict]) -> List[Notification]:
        """Create proactive alerts based on patterns"""
        alerts = []
        
        if not cancellations:
            return alerts
        
        # Analyze patterns
        current_hour = datetime.now().hour
        is_peak = any(start <= current_hour <= end for start, end in self.rules['peak_hours'])
        
        # Count cancellations by operator
        operator_counts = {}
        for cancel in cancellations:
            operator = cancel.get('toc_darwin', 'Unknown')
            operator_counts[operator] = operator_counts.get(operator, 0) + 1
        
        # Alert for multiple cancellations from same operator
        for operator, count in operator_counts.items():
            if count >= 3:  # 3 or more cancellations
                alert = Notification(
                    id=f"proactive_operator_{operator}_{int(time.time())}",
                    type='proactive',
                    title=f'Multiple {operator} Cancellations',
                    message=f'{count} services cancelled. Consider alternative routes.',
                    priority='high' if is_peak else 'medium',
                    timestamp=datetime.now().isoformat(),
                    expires_at=(datetime.now() + timedelta(hours=4)).isoformat(),
                    data={'operator': operator, 'count': count, 'type': 'operator_disruption'},
                    channels=['push', 'app', 'email']
                )
                alerts.append(alert)
        
        # Alert for peak hour disruptions
        if is_peak and len(cancellations) >= 5:
            alert = Notification(
                id=f"proactive_peak_{int(time.time())}",
                type='proactive', 
                title='Peak Hour Disruptions',
                message=f'{len(cancellations)} cancellations during peak hours. Allow extra travel time.',
                priority='high',
                timestamp=datetime.now().isoformat(),
                expires_at=(datetime.now() + timedelta(hours=2)).isoformat(),
                data={'total_cancellations': len(cancellations), 'type': 'peak_disruption'},
                channels=['push', 'app', 'email', 'sms']
            )
            alerts.append(alert)
        
        return alerts
    
    def generate_platform_alerts(self, cancellations: List[Dict]) -> List[Notification]:
        """Generate platform-specific alerts"""
        alerts = []
        
        # Group by platform for station alerts
        platform_impacts = {}
        for cancel in cancellations:
            if cancel.get('darwin_enriched'):
                platform = cancel.get('origin_platform_darwin', '')
                station = cancel.get('origin_tiploc_darwin', '')
                
                if platform and station:
                    key = f"{station}_{platform}"
                    if key not in platform_impacts:
                        platform_impacts[key] = []
                    platform_impacts[key].append(cancel)
        
        # Create alerts for platforms with multiple cancellations
        for platform_key, cancellations_list in platform_impacts.items():
            if len(cancellations_list) >= 2:
                station, platform = platform_key.split('_')
                
                alert = Notification(
                    id=f"platform_{platform_key}_{int(time.time())}",
                    type='platform_change',
                    title=f'Platform {platform} Disruptions',
                    message=f'Multiple cancellations at {station} Platform {platform}',
                    priority='medium',
                    timestamp=datetime.now().isoformat(),
                    expires_at=(datetime.now() + timedelta(hours=3)).isoformat(),
                    data={
                        'station': station,
                        'platform': platform,
                        'affected_services': [c.get('train_service_code') for c in cancellations_list]
                    },
                    channels=['push', 'app']
                )
                alerts.append(alert)
        
        return alerts
    
    def process_notifications(self):
        """Main notification processing loop"""
        logger.info("Starting notification processing...")
        
        while self.running:
            try:
                # Fetch latest cancellations
                cancellations = self.get_enhanced_cancellations()
                
                if cancellations and isinstance(cancellations, list):
                    new_notifications = []
                    
                    # Process individual cancellations
                    for cancellation in cancellations:
                        # Ensure cancellation is a dictionary
                        if not isinstance(cancellation, dict):
                            logger.warning(f"Skipping invalid cancellation data: {type(cancellation)}")
                            continue
                            
                        # Check if we've already notified about this cancellation
                        rid = cancellation.get('rid', '')
                        existing = any(n.data.get('service_code') == cancellation.get('train_service_code') 
                                     and rid in n.id for n in self.notification_history[-50:])
                        
                        if not existing:
                            try:
                                notification = self.create_cancellation_notification(cancellation)
                                new_notifications.append(notification)
                            except Exception as e:
                                logger.error(f"Failed to create notification for cancellation {rid}: {e}")
                                continue
                    
                    # Generate proactive alerts
                    try:
                        proactive_alerts = self.create_proactive_alerts(cancellations)
                        new_notifications.extend(proactive_alerts)
                    except Exception as e:
                        logger.error(f"Failed to create proactive alerts: {e}")
                    
                    # Generate platform alerts
                    try:
                        platform_alerts = self.generate_platform_alerts(cancellations)
                        new_notifications.extend(platform_alerts)
                    except Exception as e:
                        logger.error(f"Failed to create platform alerts: {e}")
                    
                    # Send notifications
                    for notification in new_notifications:
                        try:
                            self.send_notification(notification)
                            self.notification_history.append(notification)
                        except Exception as e:
                            logger.error(f"Failed to send notification {notification.id}: {e}")
                    
                    if new_notifications:
                        logger.info(f"Sent {len(new_notifications)} notifications")
                elif cancellations is None:
                    logger.debug("No cancellations data available from API")
                
                # Clean up old notifications
                cutoff = datetime.now() - timedelta(hours=24)
                self.notification_history = [
                    n for n in self.notification_history 
                    if datetime.fromisoformat(n.timestamp.replace('Z', '+00:00')) > cutoff
                ]
                
                time.sleep(30)  # Check every 30 seconds
                
            except Exception as e:
                logger.error(f"Error in notification processing: {e}")
                time.sleep(60)  # Wait longer on error
    
    def send_notification(self, notification: Notification):
        """Send notification through configured channels"""
        logger.info(f"📢 {notification.priority.upper()}: {notification.title}")
        logger.info(f"   Message: {notification.message}")
        logger.info(f"   Channels: {', '.join(notification.channels)}")
        
        # Here you would integrate with actual notification services:
        # - Push notifications (FCM, APNs)
        # - Email (SendGrid, SES)
        # - SMS (Twilio)
        # For now, just log the notification
        
        if 'push' in notification.channels:
            self._send_push_notification(notification)
        if 'email' in notification.channels:
            self._send_email_notification(notification)
        if 'sms' in notification.channels:
            self._send_sms_notification(notification)
    
    def _send_push_notification(self, notification: Notification):
        """Send push notification (placeholder)"""
        logger.info(f"📱 Push: {notification.title}")
    
    def _send_email_notification(self, notification: Notification):
        """Send email notification (placeholder)"""
        logger.info(f"📧 Email: {notification.title}")
    
    def _send_sms_notification(self, notification: Notification):
        """Send SMS notification (placeholder)"""
        logger.info(f"📱 SMS: {notification.title}")
    
    def start(self):
        """Start notification engine"""
        self.running = True
        self.thread = threading.Thread(target=self.process_notifications)
        self.thread.daemon = True
        self.thread.start()
        logger.info("Smart notification engine started")
    
    def stop(self):
        """Stop notification engine"""
        self.running = False
        if hasattr(self, 'thread'):
            self.thread.join()
        logger.info("Smart notification engine stopped")
    
    def get_recent_notifications(self, limit: int = 20) -> List[Dict]:
        """Get recent notifications for API"""
        recent = self.notification_history[-limit:]
        return [asdict(n) for n in recent]

# Flask API for notifications
from flask import Flask, jsonify, request

def create_notification_api(notification_engine: SmartNotificationEngine):
    """Create Flask API for notification management"""
    
    app = Flask(__name__)
    
    @app.route('/notifications/v1/subscribe', methods=['POST'])
    def subscribe():
        """Subscribe user to notifications"""
        data = request.get_json() or {}
        user_id = data.get('user_id')
        preferences = data.get('preferences', {})
        
        if not user_id:
            return jsonify({'error': 'user_id required'}), 400
        
        notification_engine.subscribe_user(user_id, preferences)
        return jsonify({'status': 'subscribed', 'user_id': user_id})
    
    @app.route('/notifications/v1/recent', methods=['GET'])
    def get_recent():
        """Get recent notifications"""
        limit = request.args.get('limit', 20, type=int)
        notifications = notification_engine.get_recent_notifications(limit)
        
        return jsonify({
            'status': 'success',
            'notifications': notifications,
            'count': len(notifications),
            'timestamp': datetime.now().isoformat()
        })
    
    @app.route('/notifications/v1/status', methods=['GET'])
    def notification_status():
        """Get notification service status"""
        return jsonify({
            'status': 'active' if notification_engine.running else 'inactive',
            'subscribers': len(notification_engine.subscription_db),
            'notifications_sent_today': len(notification_engine.notification_history),
            'timestamp': datetime.now().isoformat()
        })
    
    return app

if __name__ == '__main__':
    # Initialize notification engine
    notification_engine = SmartNotificationEngine()
    
    print("🚀 Starting Smart Notifications System")
    print("📢 Features:")
    print("   • Real-time cancellation alerts")
    print("   • Proactive disruption warnings")
    print("   • Platform-specific notifications")
    print("   • Priority-based delivery")
    print("   • Multi-channel support")
    print()
    
    # Start notification processing
    notification_engine.start()
    
    # Subscribe demo user
    notification_engine.subscribe_user('demo_user', {
        'peak_alerts': True,
        'platform_alerts': True,
        'proactive_alerts': True,
        'channels': ['push', 'email']
    })
    
    # Create and run API
    app = create_notification_api(notification_engine)
    
    try:
        print("🌐 Smart Notifications listening on: http://localhost:5003")
        print("📊 Notifications API: http://localhost:5003")
        app.run(host='0.0.0.0', port=5003, debug=False)
    except KeyboardInterrupt:
        print("\n🛑 Stopping notification engine...")
        notification_engine.stop()
        print("✅ Smart notifications stopped")