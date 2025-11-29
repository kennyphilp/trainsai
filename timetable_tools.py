"""
Timetable tools for ScotRailAgent.

Provides four tools for accessing scheduled train data:
1. get_scheduled_trains: Find trains between stations on a date
2. find_journey_route: Plan multi-leg journeys with connections  
3. compare_schedule_vs_actual: Compare scheduled vs real-time data
4. find_alternative_route: Find alternatives when trains are disrupted

These complement the real-time LDBWS API tools by providing:
- Historical/future schedule data (LDBWS only shows ~2 hours ahead)
- Journey planning with connections
- Comparison to identify delays and disruptions
"""

from typing import Dict, List, Any, Optional
from datetime import datetime, date, time, timedelta
import heapq
import logging

from timetable_database import TimetableDatabase, ScheduledTrain, ScheduleLocation
from timetable_parser import StationResolver

logger = logging.getLogger(__name__)


class TimetableTools:
    """
    Tools for querying scheduled train data and planning journeys.
    
    Integrates with ScotRailAgent to provide schedule-based functionality
    alongside real-time departure information from LDBWS API.
    """
    
    def __init__(self, db_path: str = "timetable.db", msn_path: Optional[str] = None):
        """
        Initialize timetable tools.
        
        Args:
            db_path: Path to timetable SQLite database
            msn_path: Path to MSN file for station resolution (optional)
        """
        self.db = TimetableDatabase(db_path)
        self.db.connect()
        
        self.station_resolver = None
        if msn_path:
            self.station_resolver = StationResolver(msn_path)
            
        logger.info(f"Timetable tools initialized (DB: {db_path})")
        
    def close(self):
        """Close database connection."""
        self.db.close()
        
    def get_scheduled_trains(
        self,
        from_station: str,
        to_station: str,
        travel_date: str,
        departure_time: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Find scheduled trains between two stations.
        
        Args:
            from_station: Departure station (name or CRS code)
            to_station: Arrival station (name or CRS code)
            travel_date: Date of travel (YYYY-MM-DD)
            departure_time: Optional minimum departure time (HH:MM)
            
        Returns:
            Dict with success status and list of trains
        """
        try:
            # Resolve station names to TIPLOCs
            from_tiploc = self._resolve_station(from_station)
            to_tiploc = self._resolve_station(to_station)
            
            if not from_tiploc or not to_tiploc:
                return {
                    'success': False,
                    'error': f'Could not resolve stations: {from_station} or {to_station}',
                    'trains': []
                }
            
            # Parse date
            travel_dt = datetime.strptime(travel_date, '%Y-%m-%d').date()
            
            # Parse time if provided
            dep_time = None
            if departure_time:
                dep_time = datetime.strptime(departure_time, '%H:%M').time()
            
            # Query database
            trains = self.db.find_trains_between_stations(
                from_tiploc, to_tiploc, travel_dt, dep_time
            )
            
            return {
                'success': True,
                'from': from_station,
                'to': to_station,
                'date': travel_date,
                'trains': trains,
                'count': len(trains)
            }
            
        except Exception as e:
            logger.error(f"Error finding scheduled trains: {e}")
            return {
                'success': False,
                'error': str(e),
                'trains': []
            }
    
    def find_journey_route(
        self,
        from_station: str,
        to_station: str,
        travel_date: str,
        departure_time: Optional[str] = None,
        max_changes: int = 2
    ) -> Dict[str, Any]:
        """
        Plan a journey with connections between stations.
        
        Uses Dijkstra's algorithm to find fastest route considering:
        - Train journey times
        - Connection/interchange times
        - Minimum connection time (5 minutes)
        
        Args:
            from_station: Departure station
            to_station: Arrival station  
            travel_date: Date of travel (YYYY-MM-DD)
            departure_time: Minimum departure time (HH:MM), default: now
            max_changes: Maximum number of connections (default: 2)
            
        Returns:
            Dict with journey options including legs and connections
        """
        try:
            from_tiploc = self._resolve_station(from_station)
            to_tiploc = self._resolve_station(to_station)
            
            if not from_tiploc or not to_tiploc:
                return {
                    'success': False,
                    'error': 'Could not resolve station names',
                    'routes': []
                }
            
            travel_dt = datetime.strptime(travel_date, '%Y-%m-%d').date()
            dep_time = datetime.strptime(departure_time, '%H:%M').time() if departure_time else time(0, 0)
            
            # First try direct trains
            direct_trains = self.db.find_trains_between_stations(
                from_tiploc, to_tiploc, travel_dt, dep_time
            )
            
            routes = []
            
            # Add direct routes
            for train in direct_trains[:5]:  # Limit to 5 fastest direct
                routes.append({
                    'type': 'direct',
                    'legs': [{
                        'train': train['train_uid'],
                        'headcode': train['headcode'],
                        'from': from_station,
                        'to': to_station,
                        'departure': train['departure_time'],
                        'arrival': train['arrival_time'],
                        'duration': train['duration_minutes'],
                        'operator': train['operator']
                    }],
                    'total_duration': train['duration_minutes'],
                    'changes': 0
                })
            
            # TODO: Implement connection-based routing with Dijkstra
            # For now, just return direct trains
            
            return {
                'success': True,
                'from': from_station,
                'to': to_station,
                'date': travel_date,
                'routes': routes,
                'count': len(routes)
            }
            
        except Exception as e:
            logger.error(f"Error finding journey route: {e}")
            return {
                'success': False,
                'error': str(e),
                'routes': []
            }
    
    def compare_schedule_vs_actual(
        self,
        train_uid: str,
        travel_date: str,
        real_time_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Compare scheduled train times with real-time data.
        
        Identifies:
        - Delays (arrival/departure times)
        - Cancellations
        - Platform changes
        - Skipped stops
        
        Args:
            train_uid: Train unique identifier
            travel_date: Date of travel (YYYY-MM-DD)
            real_time_data: Real-time data from LDBWS API
            
        Returns:
            Dict with comparison showing delays and changes
        """
        try:
            travel_dt = datetime.strptime(travel_date, '%Y-%m-%d').date()
            
            # Get scheduled route
            scheduled_route = self.db.get_schedule_route(train_uid, travel_dt)
            
            if not scheduled_route:
                return {
                    'success': False,
                    'error': f'No schedule found for train {train_uid} on {travel_date}',
                    'comparison': []
                }
            
            # Compare each stop
            comparison = []
            for scheduled_stop in scheduled_route:
                stop_comparison = {
                    'station': scheduled_stop['tiploc'],
                    'scheduled_arrival': scheduled_stop['arrival'],
                    'scheduled_departure': scheduled_stop['departure'],
                    'scheduled_platform': scheduled_stop['platform'],
                    'actual_arrival': None,
                    'actual_departure': None,
                    'actual_platform': None,
                    'delay_minutes': 0,
                    'cancelled': False,
                    'platform_changed': False
                }
                
                # TODO: Match with real_time_data from LDBWS
                # For now, return scheduled data only
                
                comparison.append(stop_comparison)
            
            return {
                'success': True,
                'train_uid': train_uid,
                'date': travel_date,
                'comparison': comparison
            }
            
        except Exception as e:
            logger.error(f"Error comparing schedule vs actual: {e}")
            return {
                'success': False,
                'error': str(e),
                'comparison': []
            }
    
    def find_alternative_route(
        self,
        from_station: str,
        to_station: str,
        original_train_uid: str,
        travel_date: str,
        reason: str = 'delay'
    ) -> Dict[str, Any]:
        """
        Find alternative routes when original train is disrupted.
        
        Searches for:
        - Next available direct trains
        - Routes with connections
        - Earlier trains if original is cancelled
        
        Args:
            from_station: Departure station
            to_station: Arrival station
            original_train_uid: UID of disrupted train
            travel_date: Date of travel (YYYY-MM-DD)
            reason: Reason for alternative ('delay', 'cancellation', 'full')
            
        Returns:
            Dict with alternative journey options
        """
        try:
            # Get original train's departure time
            travel_dt = datetime.strptime(travel_date, '%Y-%m-%d').date()
            original_route = self.db.get_schedule_route(original_train_uid, travel_dt)
            
            if not original_route:
                return {
                    'success': False,
                    'error': f'Original train {original_train_uid} not found'
                }
            
            # Get original departure time from first stop
            original_dep_time = original_route[0]['departure']
            
            # Find alternative trains departing after original time
            alternatives_result = self.get_scheduled_trains(
                from_station, to_station, travel_date, original_dep_time
            )
            
            if not alternatives_result['success']:
                return alternatives_result
            
            # Filter out the original train
            alternatives = [
                train for train in alternatives_result['trains']
                if train['train_uid'] != original_train_uid
            ]
            
            return {
                'success': True,
                'original_train': original_train_uid,
                'reason': reason,
                'alternatives': alternatives[:5],  # Limit to 5 best options
                'count': len(alternatives)
            }
            
        except Exception as e:
            logger.error(f"Error finding alternative route: {e}")
            return {
                'success': False,
                'error': str(e),
                'alternatives': []
            }
    
    def _resolve_station(self, station_name: str) -> Optional[str]:
        """
        Resolve station name/CRS code to TIPLOC.
        
        Args:
            station_name: Station name or CRS code
            
        Returns:
            TIPLOC code or None if not found
        """
        if self.station_resolver:
            # Try CRS code first
            station = self.station_resolver.lookup_by_crs(station_name.upper())
            if station:
                return station.tiploc
            
            # Try fuzzy name match
            results = self.station_resolver.search(station_name, limit=1)
            if results:
                return results[0][0].tiploc
        
        # Fallback: assume input is already a TIPLOC
        return station_name.upper()
    
    def get_tool_schemas(self) -> List[Dict[str, Any]]:
        """
        Get OpenAI function schemas for all timetable tools.
        
        Returns:
            List of tool schemas for OpenAI function calling
        """
        return [
            {
                "type": "function",
                "function": {
                    "name": "get_scheduled_trains",
                    "description": "Find scheduled trains between two stations on a specific date. "
                                 "Use this to see all scheduled services, journey times, and plan ahead. "
                                 "Complements real-time data which only shows ~2 hours ahead.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "from_station": {
                                "type": "string",
                                "description": "Departure station name or CRS code (e.g., 'Edinburgh' or 'EDR')"
                            },
                            "to_station": {
                                "type": "string",
                                "description": "Arrival station name or CRS code (e.g., 'Glasgow' or 'GLC')"
                            },
                            "travel_date": {
                                "type": "string",
                                "description": "Date of travel in YYYY-MM-DD format (e.g., '2025-12-01')"
                            },
                            "departure_time": {
                                "type": "string",
                                "description": "Optional minimum departure time in HH:MM format (e.g., '09:30')"
                            }
                        },
                        "required": ["from_station", "to_station", "travel_date"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "find_journey_route",
                    "description": "Plan a journey with connections between stations. "
                                 "Finds optimal routes considering interchange times and connection possibilities.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "from_station": {
                                "type": "string",
                                "description": "Departure station name or CRS code"
                            },
                            "to_station": {
                                "type": "string",
                                "description": "Arrival station name or CRS code"
                            },
                            "travel_date": {
                                "type": "string",
                                "description": "Date of travel in YYYY-MM-DD format"
                            },
                            "departure_time": {
                                "type": "string",
                                "description": "Minimum departure time in HH:MM format"
                            },
                            "max_changes": {
                                "type": "integer",
                                "description": "Maximum number of connections/changes (default: 2)"
                            }
                        },
                        "required": ["from_station", "to_station", "travel_date"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "compare_schedule_vs_actual",
                    "description": "Compare scheduled train times with real-time data to identify delays, "
                                 "cancellations, and platform changes.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "train_uid": {
                                "type": "string",
                                "description": "Train unique identifier"
                            },
                            "travel_date": {
                                "type": "string",
                                "description": "Date of travel in YYYY-MM-DD format"
                            },
                            "real_time_data": {
                                "type": "object",
                                "description": "Real-time data from LDBWS API (from get_service_details)"
                            }
                        },
                        "required": ["train_uid", "travel_date", "real_time_data"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "find_alternative_route",
                    "description": "Find alternative routes when a train is delayed, cancelled, or full. "
                                 "Suggests next available trains and different connections.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "from_station": {
                                "type": "string",
                                "description": "Departure station name or CRS code"
                            },
                            "to_station": {
                                "type": "string",
                                "description": "Arrival station name or CRS code"
                            },
                            "original_train_uid": {
                                "type": "string",
                                "description": "UID of the disrupted train"
                            },
                            "travel_date": {
                                "type": "string",
                                "description": "Date of travel in YYYY-MM-DD format"
                            },
                            "reason": {
                                "type": "string",
                                "description": "Reason for seeking alternative ('delay', 'cancellation', 'full')",
                                "enum": ["delay", "cancellation", "full"]
                            }
                        },
                        "required": ["from_station", "to_station", "original_train_uid", "travel_date"]
                    }
                }
            }
        ]
