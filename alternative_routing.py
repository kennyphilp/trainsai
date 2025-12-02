#!/usr/bin/env python3
"""
Alternative Routing Engine
Intelligent route suggestions using Darwin enrichment data
"""

import json
import requests
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

@dataclass
class Route:
    """Route suggestion data structure"""
    origin: str
    destination: str
    services: List[str]
    estimated_duration: int  # minutes
    calling_points: List[str]
    disruption_risk: str  # 'low', 'medium', 'high'
    recommendation: str

@dataclass
class AlternativeRoute:
    """Alternative route suggestion"""
    route_id: str
    description: str
    transport_modes: List[str]  # ['rail', 'bus', 'coach']
    estimated_time: int  # minutes
    cost_estimate: str
    reliability_score: float  # 0-1
    instructions: List[str]
    disruption_notes: str

class RouteOptimizer:
    """Intelligent routing with disruption awareness"""
    
    def __init__(self, base_api_url="http://localhost:8080"):
        self.base_api_url = base_api_url
        
        # Scottish rail network knowledge base
        self.network_map = {
            'WATRLOO': {'name': 'London Waterloo', 'major_hub': True},
            'GUILDFD': {'name': 'Guildford', 'major_hub': False},
            'EDINBUR': {'name': 'Edinburgh', 'major_hub': True},
            'GLASGOW': {'name': 'Glasgow Central', 'major_hub': True},
            'STIRLNG': {'name': 'Stirling', 'major_hub': False},
            'PERTH': {'name': 'Perth', 'major_hub': False},
            'DUNDEE': {'name': 'Dundee', 'major_hub': False},
            'ABERDEEN': {'name': 'Aberdeen', 'major_hub': True},
        }
        
        # Common route patterns
        self.route_patterns = {
            'glasgow_edinburgh': {
                'primary': ['GLASGOW', 'FALKIRK', 'EDINBUR'],
                'alternative': ['GLASGOW', 'MOTHERWELL', 'SHOTTS', 'EDINBUR'],
                'bus_route': ['Citylink', 'Megabus']
            },
            'central_scotland': {
                'hubs': ['GLASGOW', 'EDINBUR', 'STIRLNG'],
                'connections': ['FALKIRK', 'MOTHERWELL', 'HAYMARKET']
            }
        }
        
        # Transport integration data
        self.transport_modes = {
            'bus': {'operators': ['Citylink', 'Stagecoach', 'First Bus'], 'reliability': 0.8},
            'coach': {'operators': ['Megabus', 'National Express'], 'reliability': 0.7},
            'taxi': {'operators': ['Uber', 'Local Taxis'], 'reliability': 0.9}
        }
    
    def get_current_disruptions(self) -> List[Dict]:
        """Fetch current disruptions from enhanced API"""
        try:
            response = requests.get(f"{self.base_api_url}/cancellations", timeout=5)
            if response.status_code == 200:
                data = response.json()
                
                # Ensure we return a list of dictionaries
                if isinstance(data, list):
                    # Validate each item is a dictionary
                    validated_data = []
                    for item in data:
                        if isinstance(item, dict):
                            validated_data.append(item)
                        else:
                            logger.warning(f"Skipping non-dict disruption item: {type(item)} - {item}")
                    return validated_data
                elif isinstance(data, dict):
                    # If single dict returned, wrap in list
                    return [data]
                else:
                    logger.warning(f"Unexpected data type from API: {type(data)}")
                    return []
            else:
                logger.warning(f"API returned status {response.status_code}")
                return []
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to fetch disruptions: {e}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error fetching disruptions: {e}")
            return []
    
    def analyze_route_disruptions(self, origin: str, destination: str) -> Dict:
        """Analyze current disruptions affecting a route"""
        disruptions = self.get_current_disruptions()
        
        affected_services = []
        affected_stations = []
        disruption_level = 'low'
        
        # Ensure disruptions is a list
        if not isinstance(disruptions, list):
            logger.warning(f"Expected list of disruptions, got {type(disruptions)}")
            return {
                'level': 'low',
                'affected_services': [],
                'affected_stations': [],
                'total_disruptions': 0
            }
        
        for disruption in disruptions:
            # Ensure each disruption is a dictionary
            if not isinstance(disruption, dict):
                logger.warning(f"Expected disruption dict, got {type(disruption)}: {disruption}")
                continue
                
            # Check if disruption has Darwin enrichment data
            if disruption.get('darwin_enriched'):
                # Check direct route impact
                d_origin = disruption.get('origin_tiploc_darwin', '')
                d_destination = disruption.get('destination_tiploc_darwin', '')
                
                if (d_origin == origin and d_destination == destination):
                    service_code = disruption.get('train_service_code', '')
                    if service_code:
                        affected_services.append(service_code)
                    disruption_level = 'high'
                
                # Check calling points impact
                calling_points = disruption.get('calling_points_darwin', [])
                if isinstance(calling_points, list):
                    route_stations = [origin, destination]
                    
                    for point in calling_points:
                        if isinstance(point, dict):
                            station = point.get('tiploc', '')
                            if station in route_stations:
                                affected_stations.append(station)
                                if disruption_level == 'low':
                                    disruption_level = 'medium'
        
        return {
            'level': disruption_level,
            'affected_services': list(set(affected_services)),
            'affected_stations': list(set(affected_stations)),
            'total_disruptions': len(disruptions)
        }
    
    def find_alternative_rail_routes(self, origin: str, destination: str, disruptions: Dict) -> List[Route]:
        """Find alternative rail routes considering disruptions"""
        alternatives = []
        
        # Direct route analysis
        direct_route = Route(
            origin=origin,
            destination=destination,
            services=['Direct Service'],
            estimated_duration=60,  # Placeholder
            calling_points=[origin, destination],
            disruption_risk=disruptions['level'],
            recommendation="Check live departures" if disruptions['level'] == 'low' else "Consider alternatives"
        )
        
        if disruptions['level'] != 'high':
            alternatives.append(direct_route)
        
        # Hub-based routing for major disruptions
        if disruptions['level'] in ['medium', 'high']:
            # Find potential hubs
            hubs = [station for station, info in self.network_map.items() 
                   if info.get('major_hub') and station not in [origin, destination]]
            
            for hub in hubs:
                if self._is_viable_hub_route(origin, hub, destination):
                    hub_route = Route(
                        origin=origin,
                        destination=destination,
                        services=[f'Via {self.network_map[hub]["name"]}'],
                        estimated_duration=90,  # Longer via hub
                        calling_points=[origin, hub, destination],
                        disruption_risk='low',  # Assume hub routes less affected
                        recommendation=f"Alternative via {self.network_map[hub]['name']}"
                    )
                    alternatives.append(hub_route)
        
        return alternatives
    
    def _is_viable_hub_route(self, origin: str, hub: str, destination: str) -> bool:
        """Check if hub routing is viable"""
        # Simplified logic - in reality would check actual connections
        major_stations = ['GLASGOW', 'EDINBUR', 'STIRLNG']
        return hub in major_stations and origin != hub and destination != hub
    
    def suggest_multimodal_alternatives(self, origin: str, destination: str, disruptions: Dict) -> List[AlternativeRoute]:
        """Suggest multimodal transport alternatives"""
        alternatives = []
        
        # Bus alternatives for high disruptions
        if disruptions['level'] == 'high':
            bus_alternative = AlternativeRoute(
                route_id=f"bus_{origin}_{destination}",
                description=f"Bus service from {origin} to {destination}",
                transport_modes=['bus'],
                estimated_time=90,
                cost_estimate="£5-15",
                reliability_score=0.8,
                instructions=[
                    f"Walk to nearest bus station from {origin}",
                    "Take Citylink or local bus service",
                    f"Travel directly to {destination}",
                    "Check Traveline Scotland for live times"
                ],
                disruption_notes="Bus services typically not affected by rail disruptions"
            )
            alternatives.append(bus_alternative)
            
            # Coach alternative
            coach_alternative = AlternativeRoute(
                route_id=f"coach_{origin}_{destination}",
                description=f"Coach service from {origin} to {destination}",
                transport_modes=['coach'],
                estimated_time=120,
                cost_estimate="£10-25",
                reliability_score=0.7,
                instructions=[
                    f"Walk to coach station from {origin}",
                    "Take Megabus or National Express",
                    f"Travel to {destination} coach station",
                    "Book in advance for best prices"
                ],
                disruption_notes="Coach services independent of rail network"
            )
            alternatives.append(coach_alternative)
        
        # Taxi/rideshare for short distances
        taxi_alternative = AlternativeRoute(
            route_id=f"taxi_{origin}_{destination}",
            description=f"Taxi/rideshare from {origin} to {destination}",
            transport_modes=['taxi'],
            estimated_time=45,
            cost_estimate="£30-80",
            reliability_score=0.9,
            instructions=[
                "Book Uber, taxi, or rideshare app",
                f"Direct journey from {origin} to {destination}",
                "Most reliable but expensive option"
            ],
            disruption_notes="Not affected by rail disruptions"
        )
        alternatives.append(taxi_alternative)
        
        # Walking for very short distances
        if self._calculate_walking_time(origin, destination) <= 120:  # 2 hours max
            walking_alternative = AlternativeRoute(
                route_id=f"walk_{origin}_{destination}",
                description=f"Walking route from {origin} to {destination}",
                transport_modes=['walking'],
                estimated_time=self._calculate_walking_time(origin, destination),
                cost_estimate="Free",
                reliability_score=1.0,
                instructions=[
                    f"Walk from {origin} to {destination}",
                    "Use maps app for best route",
                    "Allow extra time for weather"
                ],
                disruption_notes="Weather dependent only"
            )
            alternatives.append(walking_alternative)
        
        return alternatives
    
    def _calculate_walking_time(self, origin: str, destination: str) -> int:
        """Estimate walking time between stations (placeholder)"""
        # Simplified - would use actual distance calculation
        station_distances = {
            ('WATRLOO', 'GUILDFD'): 180,  # Too far to walk
            ('GLASGOW', 'EDINBUR'): 300,  # Too far to walk
            # Add more realistic short distances
        }
        return station_distances.get((origin, destination), 300)  # Default too far
    
    def optimize_journey_timing(self, alternatives: List[AlternativeRoute], preferred_arrival: str) -> List[AlternativeRoute]:
        """Optimize alternatives based on preferred arrival time"""
        try:
            target_time = datetime.strptime(preferred_arrival, '%H:%M').time()
            current_time = datetime.now().time()
            
            # Calculate how much time is available
            target_datetime = datetime.combine(datetime.now().date(), target_time)
            if target_datetime < datetime.now():
                target_datetime += timedelta(days=1)
            
            available_minutes = int((target_datetime - datetime.now()).total_seconds() / 60)
            
            # Filter alternatives that can make the time
            viable_alternatives = []
            for alt in alternatives:
                if alt.estimated_time <= available_minutes:
                    # Adjust recommendation based on time constraint
                    if alt.estimated_time <= available_minutes * 0.8:
                        alt.recommendation = f"Recommended - arrives with time to spare"
                    else:
                        alt.recommendation = f"Tight timing - allow buffer time"
                    viable_alternatives.append(alt)
            
            # Sort by reliability and estimated time
            viable_alternatives.sort(key=lambda x: (-x.reliability_score, x.estimated_time))
            return viable_alternatives
            
        except ValueError:
            # Invalid time format, return all alternatives
            return alternatives
    
    def get_route_recommendations(self, origin: str, destination: str, 
                                 preferences: Dict = None) -> Dict:
        """Main method to get comprehensive route recommendations"""
        
        # Analyze current disruptions
        disruptions = self.analyze_route_disruptions(origin, destination)
        
        # Find rail alternatives
        rail_routes = self.find_alternative_rail_routes(origin, destination, disruptions)
        
        # Find multimodal alternatives
        multimodal_routes = self.suggest_multimodal_alternatives(origin, destination, disruptions)
        
        # Apply user preferences if provided
        if preferences and preferences.get('preferred_arrival'):
            multimodal_routes = self.optimize_journey_timing(
                multimodal_routes, preferences['preferred_arrival']
            )
        
        # Create comprehensive recommendation
        recommendation = {
            'journey': {
                'origin': origin,
                'destination': destination,
                'origin_name': self.network_map.get(origin, {}).get('name', origin),
                'destination_name': self.network_map.get(destination, {}).get('name', destination)
            },
            'disruption_analysis': disruptions,
            'rail_options': [
                {
                    'services': route.services,
                    'duration_minutes': route.estimated_duration,
                    'disruption_risk': route.disruption_risk,
                    'recommendation': route.recommendation,
                    'calling_points': route.calling_points
                }
                for route in rail_routes
            ],
            'alternative_transport': [
                {
                    'mode': ', '.join(route.transport_modes),
                    'description': route.description,
                    'duration_minutes': route.estimated_time,
                    'cost': route.cost_estimate,
                    'reliability': f"{route.reliability_score*100:.0f}%",
                    'instructions': route.instructions,
                    'notes': route.disruption_notes
                }
                for route in multimodal_routes
            ],
            'recommendations': self._generate_overall_recommendations(
                disruptions, rail_routes, multimodal_routes
            ),
            'last_updated': datetime.now().isoformat()
        }
        
        return recommendation
    
    def _generate_overall_recommendations(self, disruptions: Dict, 
                                        rail_routes: List[Route], 
                                        multimodal_routes: List[AlternativeRoute]) -> List[str]:
        """Generate overall journey recommendations"""
        recommendations = []
        
        if disruptions['level'] == 'low':
            recommendations.append("Rail services appear normal - proceed with planned journey")
            recommendations.append("Check live departures before traveling")
        elif disruptions['level'] == 'medium':
            recommendations.append("Some rail disruptions detected - allow extra time")
            recommendations.append("Consider alternative routes if traveling urgently")
            if multimodal_routes:
                best_alt = min(multimodal_routes, key=lambda x: x.estimated_time)
                recommendations.append(f"Backup option: {best_alt.description}")
        else:  # high
            recommendations.append("Significant rail disruptions - consider alternative transport")
            if multimodal_routes:
                reliable_alts = [r for r in multimodal_routes if r.reliability_score >= 0.8]
                if reliable_alts:
                    best_alt = min(reliable_alts, key=lambda x: x.estimated_time)
                    recommendations.append(f"Recommended: {best_alt.description}")
            recommendations.append("Check with station staff for latest updates")
        
        return recommendations

# Flask-RESTX API for routing service with Swagger documentation
from flask import Flask
from flask_restx import Api, Resource, fields, reqparse

def create_routing_api(route_optimizer: RouteOptimizer):
    """Create Flask-RESTX API for route optimization with Swagger documentation"""
    
    app = Flask(__name__)
    
    # Configure Flask-RESTX
    api = Api(
        app,
        version='1.0',
        title='Darwin Rail Alternative Routing API',
        description='Intelligent route suggestions using Darwin enrichment data with disruption awareness',
        doc='/docs/',  # Swagger UI endpoint
        prefix='/routing/v1'
    )
    
    # Create namespace
    ns = api.namespace('routing', description='Route planning and disruption analysis')
    
    # Define data models for Swagger documentation
    
    # Input models
    preferences_model = api.model('Preferences', {
        'preferred_arrival': fields.String(description='Preferred arrival time in HH:MM format', example='14:30')
    })
    
    journey_request_model = api.model('JourneyRequest', {
        'origin': fields.String(required=True, description='Origin station TIPLOC code', example='GLASGOW'),
        'destination': fields.String(required=True, description='Destination station TIPLOC code', example='EDINBUR'),
        'preferences': fields.Nested(preferences_model, required=False, description='Journey preferences')
    })
    
    # Output models
    disruption_model = api.model('DisruptionAnalysis', {
        'level': fields.String(description='Disruption level', enum=['low', 'medium', 'high']),
        'affected_services': fields.List(fields.String, description='List of affected service codes'),
        'affected_stations': fields.List(fields.String, description='List of affected station codes'),
        'total_disruptions': fields.Integer(description='Total number of disruptions')
    })
    
    rail_option_model = api.model('RailOption', {
        'services': fields.List(fields.String, description='Available rail services'),
        'duration_minutes': fields.Integer(description='Estimated journey duration in minutes'),
        'disruption_risk': fields.String(description='Risk level', enum=['low', 'medium', 'high']),
        'recommendation': fields.String(description='Service recommendation'),
        'calling_points': fields.List(fields.String, description='Station calling points')
    })
    
    alternative_transport_model = api.model('AlternativeTransport', {
        'mode': fields.String(description='Transport mode(s)'),
        'description': fields.String(description='Route description'),
        'duration_minutes': fields.Integer(description='Estimated duration in minutes'),
        'cost': fields.String(description='Estimated cost range'),
        'reliability': fields.String(description='Reliability percentage'),
        'instructions': fields.List(fields.String, description='Step-by-step instructions'),
        'notes': fields.String(description='Additional notes')
    })
    
    journey_info_model = api.model('JourneyInfo', {
        'origin': fields.String(description='Origin TIPLOC code'),
        'destination': fields.String(description='Destination TIPLOC code'),
        'origin_name': fields.String(description='Origin station name'),
        'destination_name': fields.String(description='Destination station name')
    })
    
    journey_response_model = api.model('JourneyResponse', {
        'status': fields.String(description='Response status'),
        'data': fields.Nested(api.model('JourneyData', {
            'journey': fields.Nested(journey_info_model, description='Journey information'),
            'disruption_analysis': fields.Nested(disruption_model, description='Current disruption analysis'),
            'rail_options': fields.List(fields.Nested(rail_option_model), description='Available rail options'),
            'alternative_transport': fields.List(fields.Nested(alternative_transport_model), description='Alternative transport options'),
            'recommendations': fields.List(fields.String, description='Overall journey recommendations'),
            'last_updated': fields.String(description='Last update timestamp in ISO format')
        }))
    })
    
    station_info_model = api.model('StationInfo', {
        'name': fields.String(description='Station name'),
        'major_hub': fields.Boolean(description='Whether this is a major hub station')
    })
    
    stations_response_model = api.model('StationsResponse', {
        'status': fields.String(description='Response status'),
        'stations': fields.Raw(description='Dictionary of station codes to station information')
    })
    
    disruption_response_model = api.model('DisruptionResponse', {
        'status': fields.String(description='Response status'),
        'route': fields.Nested(api.model('RouteInfo', {
            'origin': fields.String(description='Origin station code'),
            'destination': fields.String(description='Destination station code')
        }), required=False, description='Route information (when querying specific route)'),
        'disruptions': fields.Nested(disruption_model, required=False, description='Route-specific disruptions'),
        'network_disruptions': fields.Integer(required=False, description='Total network disruptions'),
        'timestamp': fields.String(required=False, description='Timestamp in ISO format')
    })
    
    error_model = api.model('Error', {
        'status': fields.String(description='Error status'),
        'message': fields.String(description='Error message'),
        'error': fields.String(description='Detailed error information')
    })
    
    # API endpoints
    
    @ns.route('/plan')
    class JourneyPlan(Resource):
        @ns.doc('plan_journey')
        @ns.expect(journey_request_model)
        @ns.marshal_with(journey_response_model, code=200)
        @ns.marshal_with(error_model, code=400, description='Bad Request')
        @ns.marshal_with(error_model, code=500, description='Internal Server Error')
        def post(self):
            """Plan journey with disruption awareness
            
            Plan an intelligent journey between two stations considering current rail disruptions.
            Provides rail options and alternative transport modes with real-time recommendations.
            """
            data = api.payload or {}
            
            origin = data.get('origin', '').upper()
            destination = data.get('destination', '').upper()
            preferences = data.get('preferences', {})
            
            if not origin or not destination:
                api.abort(400, 'Origin and destination required. Use TIPLOC codes (e.g., GLASGOW, EDINBUR)')
            
            try:
                recommendations = route_optimizer.get_route_recommendations(
                    origin, destination, preferences
                )
                
                return {
                    'status': 'success',
                    'data': recommendations
                }
                
            except Exception as e:
                logger.error(f"Route planning error: {e}")
                api.abort(500, f'Route planning failed: {str(e)}')
    
    @ns.route('/disruptions')
    class Disruptions(Resource):
        @ns.doc('get_disruptions')
        @ns.marshal_with(disruption_response_model, code=200)
        @ns.param('origin', 'Origin station TIPLOC code (optional)', type='string')
        @ns.param('destination', 'Destination station TIPLOC code (optional)', type='string')
        def get(self):
            """Get current network disruptions
            
            Retrieve current rail network disruptions. If origin and destination are provided,
            returns route-specific disruption analysis. Otherwise returns general network status.
            """
            parser = reqparse.RequestParser()
            parser.add_argument('origin', type=str, help='Origin station TIPLOC code')
            parser.add_argument('destination', type=str, help='Destination station TIPLOC code')
            args = parser.parse_args()
            
            origin = args['origin'].upper() if args['origin'] else ''
            destination = args['destination'].upper() if args['destination'] else ''
            
            if origin and destination:
                disruptions = route_optimizer.analyze_route_disruptions(origin, destination)
                return {
                    'status': 'success',
                    'route': {'origin': origin, 'destination': destination},
                    'disruptions': disruptions
                }
            else:
                # General network status
                all_disruptions = route_optimizer.get_current_disruptions()
                return {
                    'status': 'success',
                    'network_disruptions': len(all_disruptions),
                    'timestamp': datetime.now().isoformat()
                }
    
    @ns.route('/stations')
    class Stations(Resource):
        @ns.doc('get_stations')
        @ns.marshal_with(stations_response_model, code=200)
        def get(self):
            """Get available station codes
            
            Returns a list of all available station TIPLOC codes and their information
            that can be used for journey planning.
            """
            return {
                'status': 'success',
                'stations': route_optimizer.network_map
            }
    
    # Add a root redirect to docs
    @app.route('/')
    def redirect_to_docs():
        return f'<h1>Darwin Rail Alternative Routing API</h1><p>Visit <a href="/docs/">Swagger Documentation</a> to test the APIs</p>'
    
    return app

if __name__ == '__main__':
    # Initialize route optimizer
    route_optimizer = RouteOptimizer()
    
    print("🚀 Starting Alternative Routing Engine with Swagger Documentation")
    print("🗺️  Features:")
    print("   • Disruption-aware route planning")
    print("   • Multimodal alternatives")
    print("   • Real-time network analysis")
    print("   • Intelligent recommendations")
    print("   • Interactive API documentation")
    print()
    
    # Create and run API
    app = create_routing_api(route_optimizer)
    
    print("🌐 Alternative Routing listening on: http://localhost:5004")
    print("📋 Swagger API Documentation: http://localhost:5004/docs/")
    print("🚀 Main endpoint: http://localhost:5004")
    print()
    print("📊 Available APIs:")
    print("   • POST /routing/v1/plan - Plan journey with disruption awareness")
    print("   • GET  /routing/v1/disruptions - Get network disruptions")
    print("   • GET  /routing/v1/stations - Get available station codes")
    print()
    print("💡 Use Swagger UI at /docs/ to test all APIs interactively!")
    
    app.run(host='0.0.0.0', port=5004, debug=True)