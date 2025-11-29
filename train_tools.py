#!/usr/bin/env python3
"""
Train Tools - UK National Rail API Client

This module provides a Python interface to the UK National Rail APIs:
- Live Departure Boards (SOAP) - Real-time train departure information
- Knowledgebase Incidents Feed (REST/XML) - Network-wide disruption data

Main class: TrainTools
Provides methods for querying departure boards, detailed service information,
and nationwide incident/disruption messages.

Usage:
    from train_tools import TrainTools
    
    tt = TrainTools(ldb_token='your_token')
    departures = tt.get_departure_board('EUS', num_rows=10)
    incidents = tt.get_station_messages()

Environment Variables:
    LDB_TOKEN - National Rail Live Departure Boards access token
    DISRUPTIONS_API_KEY or RDG_API_KEY - Rail Delivery Group API key
"""

import os
import xml.etree.ElementTree as ET
from typing import Dict, Iterable, List, Optional, Sequence, Set, Union

import requests
from dotenv import load_dotenv
from zeep import Client, Settings, xsd

from models import (
    AffectedOperator,
    DepartureBoardError,
    DepartureBoardResponse,
    DetailedDeparturesError,
    DetailedDeparturesResponse,
    DetailedTrainDeparture,
    Incident,
    ServiceDetailsError,
    ServiceDetailsResponse,
    ServiceLocation,
    StationMessagesError,
    StationMessagesResponse,
    TrainDeparture,
)

# Load environment variables
load_dotenv()

# ============================================================================
# Configuration Constants
# ============================================================================

DEFAULT_WSDL = 'http://lite.realtime.nationalrail.co.uk/OpenLDBWS/wsdl.aspx?ver=2021-11-01'
INCIDENTS_API_URL = 'https://api1.raildata.org.uk/1010-knowlegebase-incidents-xml-feed1_0/incidents.xml'
SERVICE_DETAILS_API_URL = 'https://api1.raildata.org.uk/1010-service-details1_2/LDBWS/api/20220120/GetServiceDetails'
SERVICE_DETAILS_API_KEY = 'FI7Es7TryzBsOo7EhvMxmVL5RbmZAUMH9Md23sTJCjQCjgYC'

# XML Namespaces for incident feed
INCIDENT_NAMESPACES = {
    'inc': 'http://nationalrail.co.uk/xml/incident',
    'com': 'http://nationalrail.co.uk/xml/common'
}

# Backwards-compatible module-level names (tests expect these)
LDB_TOKEN = os.getenv('LDB_TOKEN')
WSDL = DEFAULT_WSDL

# ============================================================================
# TrainTools Class
# ============================================================================

class TrainTools:
    """
    UK National Rail API Client
    
    Provides access to:
    1. Live Departure Boards (SOAP API) - Real-time departure information
    2. Incidents Feed (REST/XML API) - Network disruptions and engineering works
    
    Authentication:
    - Live Departure Boards: Requires LDB_TOKEN from National Rail
    - Incidents Feed: Requires DISRUPTIONS_API_KEY or RDG_API_KEY
    
    Example:
        >>> tt = TrainTools(ldb_token=os.getenv('LDB_TOKEN'))
        >>> board = tt.get_departure_board('EUS', num_rows=5)
        >>> print(f"{board['station']}: {len(board['trains'])} trains")
    """

    def __init__(self, ldb_token: Optional[str] = None, wsdl: Optional[str] = None):
        """
        Initialize TrainTools client.
        
        Args:
            ldb_token: National Rail Live Departure Boards access token.
                      Falls back to LDB_TOKEN environment variable if not provided.
            wsdl: Custom WSDL URL for the SOAP API. Uses default if not provided.
        """
        load_dotenv()
        self.ldb_token = ldb_token or os.getenv('LDB_TOKEN')
        self.wsdl = wsdl or DEFAULT_WSDL
        
        # Disruptions API configuration
        self.disruptions_api_key = os.getenv('DISRUPTIONS_API_KEY') or os.getenv('RDG_API_KEY')
    
    # ------------------------------------------------------------------------
    # Private Helper Methods
    # ------------------------------------------------------------------------
    
    def _make_header(self) -> xsd.Element:
        """Create SOAP authentication header for National Rail API."""
        header = xsd.Element(
            '{http://thalesgroup.com/RTTI/2013-11-28/Token/types}AccessToken',
            xsd.ComplexType([
                xsd.Element(
                    '{http://thalesgroup.com/RTTI/2013-11-28/Token/types}TokenValue',
                    xsd.String()),
            ])
        )
        return header(TokenValue=self.ldb_token)
    
    def _create_soap_client(self) -> Client:
        """Create and configure SOAP client for National Rail API."""
        settings = Settings(strict=False)
        return Client(wsdl=self.wsdl, settings=settings)
    
    def _extract_destination_name(self, service) -> str:
        """Extract destination name from service object."""
        if hasattr(service, 'destination') and service.destination:
            if hasattr(service.destination, 'location') and service.destination.location:
                return service.destination.location[0].locationName
        return "Unknown"
    
    def _build_train_detail_dict(self, service) -> Dict:
        """Build standardized train detail dictionary from service object."""
        # Handle None values by providing defaults
        platform = getattr(service, 'platform', None)
        operator = getattr(service, 'operator', None)
        service_id = getattr(service, 'serviceID', None)
        service_type = getattr(service, 'serviceType', None)
        length = getattr(service, 'length', None)
        is_cancelled = getattr(service, 'isCancelled', None)
        
        return {
            'std': service.std,
            'etd': service.etd,
            'destination': self._extract_destination_name(service),
            'platform': platform if platform is not None else 'TBA',
            'operator': operator if operator is not None else 'Unknown',
            'service_id': service_id if service_id is not None else 'N/A',
            'service_type': service_type if service_type is not None else 'Unknown',
            'length': str(length) if length is not None else 'Unknown',
            'is_cancelled': is_cancelled if is_cancelled is not None else False,
            'cancel_reason': getattr(service, 'cancelReason', None),
            'delay_reason': getattr(service, 'delayReason', None),
        }
    
    # ------------------------------------------------------------------------
    # Public API Methods - Departure Information
    # ------------------------------------------------------------------------

    
    def get_departure_board(self, station_code: str, num_rows: int = 10) -> Union[DepartureBoardResponse, DepartureBoardError]:
        """
        Fetch basic departure board information for a station.
        
        Retrieves real-time departure information from the National Rail Live
        Departure Boards API. Returns basic departure details including scheduled
        time, estimated time, destination, platform, and operating company.
        
        Args:
            station_code: Three-letter CRS code (e.g., 'EUS', 'GLC', 'MAN')
            num_rows: Maximum number of departures to return (default: 10)
        
        Returns:
            DepartureBoardResponse: Success response with station and trains data
            DepartureBoardError: Error response with error details
                
        Example:
            >>> board = tt.get_departure_board('EUS', num_rows=5)
            >>> if isinstance(board, DepartureBoardResponse):
            ...     for train in board.trains:
            ...         print(f"{train.std} to {train.destination}")
        """
        try:
            client = self._create_soap_client()
            header_value = self._make_header()

            res = client.service.GetDepartureBoard(
                numRows=num_rows,
                crs=station_code.upper(),
                _soapheaders=[header_value]
            )

            # Parse response and build trains list
            trains = []
            if hasattr(res, 'trainServices') and res.trainServices:
                for service in res.trainServices.service:
                    trains.append(TrainDeparture(
                        std=service.std,
                        etd=service.etd,
                        destination=self._extract_destination_name(service),
                        platform=getattr(service, 'platform', 'TBA'),
                        operator=getattr(service, 'operator', 'Unknown')
                    ))

            return DepartureBoardResponse(
                station=res.locationName,
                trains=trains,
                message=f"Found {len(trains)} departing trains from {res.locationName}"
            )

        except Exception as e:
            return DepartureBoardError(
                error=str(e),
                message=f"Unable to fetch departure information: {str(e)}"
            )

    
    def get_next_departures_with_details(
        self, 
        station_code: str, 
        filter_list: Union[Iterable[str], Sequence[str], Set[str], None] = None, 
        time_offset: int = 0, 
        time_window: int = 120
    ) -> Union[DetailedDeparturesResponse, DetailedDeparturesError]:
        """
        Fetch comprehensive departure information with service details.
        
        Provides detailed information including cancellation status, delay reasons,
        service IDs, and train characteristics. Supports two modes:
        
        1. Unfiltered (filter_list=None): All departures within time window
        2. Filtered: Next departure to each specified destination
        
        Args:
            station_code: Three-letter CRS code (e.g., 'EUS', 'GLC')
            filter_list: Optional destination CRS codes. None = all departures
            time_offset: Minutes from now to start search (default: 0)
            time_window: Search window in minutes (default: 120)
        
        Returns:
            DetailedDeparturesResponse: Success response with detailed train data
            DetailedDeparturesError: Error response with error details
                
        Raises:
            ValueError: If filter_list is invalid (string or empty iterable)
        
        Example:
            >>> # All departures with details
            >>> details = tt.get_next_departures_with_details('EUS')
            >>> if isinstance(details, DetailedDeparturesResponse):
            ...     for train in details.trains:
            ...         if train.is_cancelled:
            ...             print(f"Cancelled: {train.destination}")
            >>> 
            >>> # Filtered to specific destinations
            >>> details = tt.get_next_departures_with_details('EUS', ['MAN', 'LIV'])
        """
        try:
            client = self._create_soap_client()
            header_value = self._make_header()

            # Choose API method based on filter_list
            if filter_list is None:
                # GetDepBoardWithDetails: All departures within time window
                # Includes cancellation status, delay reasons, service IDs,
                # train length, and calling points
                res = client.service.GetDepBoardWithDetails(
                    numRows=150,
                    crs=station_code.upper(),
                    timeOffset=time_offset,
                    timeWindow=time_window,
                    _soapheaders=[header_value]
                )
            else:
                # Validate and build filter list
                if isinstance(filter_list, str):
                    raise ValueError(
                        "filter_list must be an iterable of CRS codes "
                        "(e.g., list/tuple/set), not a string"
                    )
                if not filter_list:
                    raise ValueError(
                        "filter_list must be a non-empty iterable of destination CRS codes"
                    )
                
                filter_crs = [str(c).upper() for c in filter_list if str(c).strip()]
                if not filter_crs:
                    raise ValueError("filter_list must contain at least one valid CRS code")

                # GetNextDeparturesWithDetails: Next departure to each destination
                res = client.service.GetNextDeparturesWithDetails(
                    crs=station_code.upper(),
                    filterList={'crs': filter_crs},
                    timeOffset=time_offset,
                    timeWindow=time_window,
                    _soapheaders=[header_value]
                )

            # Parse response based on API method used
            trains = self._parse_detailed_departures(res, filter_list is None)

            return DetailedDeparturesResponse(
                station=res.locationName,
                trains=trains,
                message=f"Found {len(trains)} next departing trains with details from {res.locationName}"
            )

        except ValueError as ve:
            return DetailedDeparturesError(
                error=str(ve),
                message=str(ve)
            )
        except Exception as e:
            return DetailedDeparturesError(
                error=str(e),
                message=f"Unable to fetch next departures with details: {str(e)}"
            )
    
    def _parse_detailed_departures(self, response, is_unfiltered: bool) -> List[DetailedTrainDeparture]:
        """
        Parse detailed departure response based on API method.
        
        Args:
            response: SOAP response object
            is_unfiltered: True if GetDepBoardWithDetails, False if GetNextDeparturesWithDetails
        
        Returns:
            List of DetailedTrainDeparture models
        """
        trains = []
        
        if is_unfiltered:
            # GetDepBoardWithDetails returns trainServices structure
            if hasattr(response, 'trainServices') and response.trainServices:
                for service in response.trainServices.service:
                    train_dict = self._build_train_detail_dict(service)
                    trains.append(DetailedTrainDeparture(**train_dict))
        else:
            # GetNextDeparturesWithDetails returns departures.destination structure
            if (hasattr(response, 'departures') and response.departures and 
                hasattr(response.departures, 'destination')):
                for destination_item in response.departures.destination:
                    service = destination_item.service
                    train_dict = self._build_train_detail_dict(service)
                    trains.append(DetailedTrainDeparture(**train_dict))
        
        return trains
        
    
    # ============================================================================
    # Station Messages & Incidents
    # ============================================================================
    
    def get_station_messages(self, station_code: Optional[str] = None) -> Union[StationMessagesResponse, StationMessagesError]:
        """
        Retrieve service disruption messages and incident information.
        
        Fetches incident data from the Rail Delivery Group Knowledgebase XML feed,
        providing real-time information about delays, cancellations, engineering
        works, and other service disruptions. Can filter by station or return all.
        
        Args:
            station_code: Optional three-letter CRS code to filter incidents.
                         None returns all current incidents across the network.
        
        Returns:
            StationMessagesResponse: Success response with list of incidents
            StationMessagesError: Error response with error details
        
        Example:
            >>> # All network incidents
            >>> incidents = tt.get_station_messages()
            >>> if isinstance(incidents, StationMessagesResponse):
            ...     print(f"Total incidents: {len(incidents.messages)}")
            >>> 
            >>> # Station-specific incidents
            >>> incidents = tt.get_station_messages('PAD')
            >>> if isinstance(incidents, StationMessagesResponse):
            ...     for incident in incidents.messages:
            ...         print(f"{incident.title}: {incident.message}")
        """
        try:
            if not self.disruptions_api_key:
                return StationMessagesError(
                    error='Missing API key',
                    message='DISRUPTIONS_API_KEY (or RDG_API_KEY) is not set in environment.'
                )
            
            headers = {'x-apikey': self.disruptions_api_key, 'User-Agent': 'TrainTools/1.0'}
            response = requests.get(INCIDENTS_API_URL, headers=headers, timeout=10)
            response.raise_for_status()

            # Parse XML with namespace handling
            root = ET.fromstring(response.text)
            incidents = self._parse_incidents(root, station_code)

            return StationMessagesResponse(
                messages=incidents,
                message=f"Found {len(incidents)} incident(s)" + 
                       (f" for station {station_code}" if station_code else " across the network")
            )

        except requests.HTTPError as http_err:
            status = getattr(http_err.response, 'status_code', 'unknown')
            return StationMessagesError(
                error=f"HTTP {status}",
                message=f"Incidents feed request failed with status {status}: {http_err}"
            )
        except requests.RequestException as e:
            return StationMessagesError(
                error=str(e),
                message=f"Unable to fetch station messages: {str(e)}"
            )
        except ET.ParseError as e:
            return StationMessagesError(
                error=str(e),
                message=f"Unable to parse station messages XML: {str(e)}"
            )
    
    def _parse_incidents(self, root: ET.Element, station_filter: Optional[str]) -> List[Incident]:
        """
        Parse incidents from XML with namespace handling.
        
        Args:
            root: XML root element
            station_filter: Optional CRS code to filter by
        
        Returns:
            List of Incident models
        """
        incidents = []
        
        # Find all PtIncident elements (old schema)
        for pt_incident in root.findall('.//inc:PtIncident', INCIDENT_NAMESPACES):
            # Extract affected operators
            affected_ops = []
            for operator_elem in pt_incident.findall('.//inc:AffectedOperator', INCIDENT_NAMESPACES):
                op_ref = self._get_text(operator_elem.find('.//inc:OperatorRef', INCIDENT_NAMESPACES))
                op_name = self._get_text(operator_elem.find('.//inc:OperatorName', INCIDENT_NAMESPACES))
                if op_ref or op_name:
                    affected_ops.append({'ref': op_ref, 'name': op_name})
            
            # Extract routes affected
            routes_affected = self._get_text(pt_incident.find('.//inc:RoutesAffected', INCIDENT_NAMESPACES))
            
            # Filter by station if requested (check if station code appears in routes)
            if station_filter and routes_affected:
                station_upper = station_filter.upper()
                if station_upper not in routes_affected.upper():
                    continue
            
            # Extract incident details
            planned_text = self._get_text(pt_incident.find('.//inc:Planned', INCIDENT_NAMESPACES))
            is_planned = planned_text == 'true' if planned_text else False
            
            # Build Pydantic model for affected operators
            operator_models = [AffectedOperator(ref=op['ref'], name=op['name']) for op in affected_ops]
            
            incident = Incident(
                id=self._get_text(pt_incident.find('.//inc:IncidentNumber', INCIDENT_NAMESPACES)),
                category='planned' if is_planned else 'unplanned',
                severity=self._get_text(pt_incident.find('.//inc:IncidentPriority', INCIDENT_NAMESPACES)),
                title=self._get_text(pt_incident.find('.//inc:Summary', INCIDENT_NAMESPACES)),
                message=self._get_text(pt_incident.find('.//inc:Description', INCIDENT_NAMESPACES)),
                start_time=self._get_text(pt_incident.find('.//com:StartTime', INCIDENT_NAMESPACES)),
                end_time=self._get_text(pt_incident.find('.//com:EndTime', INCIDENT_NAMESPACES)),
                last_updated=self._get_text(pt_incident.find('.//com:LastChangedDate', INCIDENT_NAMESPACES)),
                operators=operator_models,
                routes_affected=routes_affected,
                is_planned=is_planned
            )
            incidents.append(incident)
        
        return incidents
    
    def _get_text(self, element: Optional[ET.Element]) -> Optional[str]:
        """
        Safely extract text from XML element with namespace fallback.
        
        Args:
            element: XML element or None
        
        Returns:
            Element text or None if not found
        """
        if element is not None:
            return element.text
        return None
    
    # ============================================================================
    # Service Details
    # ============================================================================
    
    def get_service_details(self, service_id: str) -> Union[ServiceDetailsResponse, ServiceDetailsError]:
        """
        Retrieve detailed information about a specific train service.
        
        Fetches comprehensive service details from the National Rail Service Details API,
        including the complete calling pattern (all stops), real-time status updates,
        cancellation/delay reasons, and operator information.
        
        Args:
            service_id: Unique service identifier (obtained from departure board queries)
        
        Returns:
            ServiceDetailsResponse: Success response with detailed service information
            ServiceDetailsError: Error response with error details
        
        Example:
            >>> details = tt.get_service_details('eWyKjGw1P55lRvA9ReEvBg==')
            >>> if isinstance(details, ServiceDetailsResponse):
            ...     print(f"Service from {details.origin} to {details.destination}")
            ...     for stop in details.calling_points:
            ...         print(f"  {stop.location_name} - {stop.scheduled_time}")
        """
        try:
            url = f"{SERVICE_DETAILS_API_URL}/{service_id}"
            headers = {'x-apikey': SERVICE_DETAILS_API_KEY, 'User-Agent': 'TrainTools/1.0'}
            
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            
            # Extract service information
            service_data = data
            if 'GetServiceDetailsResult' in data:
                service_data = data['GetServiceDetailsResult']
            
            # Parse calling points
            calling_points = []
            if 'subsequentCallingPoints' in service_data:
                calling_points_data = service_data.get('subsequentCallingPoints', [])
                if isinstance(calling_points_data, list):
                    for cp_group in calling_points_data:
                        if 'callingPoint' in cp_group:
                            points = cp_group['callingPoint']
                            if isinstance(points, list):
                                for point in points:
                                    # Convert length to string if it's an integer
                                    length_value = point.get('length')
                                    length_str = str(length_value) if length_value is not None else None
                                    
                                    calling_points.append(ServiceLocation(
                                        location_name=point.get('locationName', 'Unknown'),
                                        crs=point.get('crs', 'N/A'),
                                        scheduled_time=point.get('st'),
                                        estimated_time=point.get('et'),
                                        actual_time=point.get('at'),
                                        is_cancelled=point.get('isCancelled', False),
                                        length=length_str,
                                        platform=point.get('platform')
                                    ))
            
            # Extract origin and destination
            origin = None
            destination = None
            if 'origin' in service_data and isinstance(service_data['origin'], list) and service_data['origin']:
                if 'location' in service_data['origin'][0] and isinstance(service_data['origin'][0]['location'], list):
                    origin = service_data['origin'][0]['location'][0].get('locationName')
            if 'destination' in service_data and isinstance(service_data['destination'], list) and service_data['destination']:
                if 'location' in service_data['destination'][0] and isinstance(service_data['destination'][0]['location'], list):
                    destination = service_data['destination'][0]['location'][0].get('locationName')
            
            return ServiceDetailsResponse(
                service_id=service_id,
                operator=service_data.get('operator'),
                operator_code=service_data.get('operatorCode'),
                service_type=service_data.get('serviceType'),
                is_cancelled=service_data.get('isCancelled', False),
                cancel_reason=service_data.get('cancelReason'),
                delay_reason=service_data.get('delayReason'),
                origin=origin,
                destination=destination,
                std=service_data.get('std'),
                etd=service_data.get('etd'),
                sta=service_data.get('sta'),
                eta=service_data.get('eta'),
                platform=service_data.get('platform'),
                calling_points=calling_points,
                message=f"Service details retrieved for {service_id}"
            )
            
        except requests.HTTPError as http_err:
            status = getattr(http_err.response, 'status_code', 'unknown')
            return ServiceDetailsError(
                error=f"HTTP {status}",
                message=f"Service details request failed with status {status}: {http_err}"
            )
        except requests.RequestException as e:
            return ServiceDetailsError(
                error=str(e),
                message=f"Unable to fetch service details: {str(e)}"
            )
        except Exception as e:
            return ServiceDetailsError(
                error=str(e),
                message=f"Error parsing service details: {str(e)}"
            )
    
    # ============================================================================
    # Formatting & Display
    # ============================================================================
    
    def format_departures(self, board_data: Union[DepartureBoardResponse, DepartureBoardError, Dict]) -> str:
        """
        Format departure board data into readable text.
        
        Args:
            board_data: DepartureBoardResponse, DepartureBoardError, or legacy Dict
        
        Returns:
            Formatted string with departure information table
        """
        # Handle error responses
        if isinstance(board_data, DepartureBoardError):
            return board_data.message
        if isinstance(board_data, dict) and 'error' in board_data:
            return board_data['message']

        # Handle success responses
        if isinstance(board_data, DepartureBoardResponse):
            if not board_data.trains:
                return f"No trains currently departing from {board_data.station}"

            output = f"\n📍 Departures from {board_data.station}\n"
            output += "=" * 70 + "\n"
            output += f"{'STD':<8} {'ETD':<8} {'Destination':<30} {'Platform':<8} {'Operator':<15}\n"
            output += "-" * 70 + "\n"

            for train in board_data.trains:
                output += f"{train.std:<8} {train.etd:<8} {train.destination:<30} {train.platform:<8} {train.operator:<15}\n"

            return output
        
        # Legacy dict support
        if isinstance(board_data, dict):
            if not board_data.get('trains'):
                return f"No trains currently departing from {board_data.get('station', 'Unknown')}"

            output = f"\n📍 Departures from {board_data['station']}\n"
            output += "=" * 70 + "\n"
            output += f"{'STD':<8} {'ETD':<8} {'Destination':<30} {'Platform':<8} {'Operator':<15}\n"
            output += "-" * 70 + "\n"

            for train in board_data['trains']:
                output += f"{train['std']:<8} {train['etd']:<8} {train['destination']:<30} {train['platform']:<8} {train['operator']:<15}\n"

            return output
        
        return "Invalid board data format"

    def main(self) -> None:
        """
        Demo: Display comprehensive departure information for Glasgow Central.
        
        Demonstrates all four main API methods:
        1. Basic departure board
        2. Detailed departures with cancellation/delay info
        3. Service details with full calling pattern
        4. Network-wide incident messages
        """
        self._print_header()
        self._demo_basic_board()
        self._demo_detailed_departures()
        self._demo_service_details()
        self._demo_incident_messages()
        self._print_footer()
    
    def _print_header(self) -> None:
        """Print demo header."""
        print("\n" + "=" * 70)
        print("🚂 Train Departure Information for Glasgow Central")
        print("=" * 70)
    
    def _print_footer(self) -> None:
        """Print demo footer."""
        print("\n" + "=" * 70)
    
    def _demo_basic_board(self) -> None:
        """Demonstrate basic departure board."""
        print("\n📋 Basic Departure Board:")
        print("-" * 70)
        board_data = self.get_departure_board('GLC', num_rows=3)
        formatted_board = self.format_departures(board_data)
        print(formatted_board)
    
    def _demo_detailed_departures(self) -> None:
        """Demonstrate detailed departures with cancellation info."""
        print("\n📋 Next Departures with Details:")
        print("-" * 70)
        details_data = self.get_next_departures_with_details('GLC', time_window=120)
        
        if isinstance(details_data, DetailedDeparturesResponse) and details_data.trains:
            print(f"\nStation: {details_data.station}")
            print(f"{'Service ID':<20} {'STD':<8} {'ETD':<8} {'Destination':<25} {'Status':<15} {'Reason':<20}")
            print("-" * 96)
            
            for train in details_data.trains:
                status = "Cancelled" if train.is_cancelled else train.etd
                reason = train.cancel_reason or train.delay_reason or "-"
                service_id = train.service_id or "N/A"
                print(f"{service_id:<20} {train.std:<8} {train.etd:<8} {train.destination:<25} {status:<15} {reason:<20}")
        elif isinstance(details_data, DetailedDeparturesError):
            print(details_data.message)
        else:
            print('Unable to fetch details')
    
    def _demo_incident_messages(self) -> None:
        """Demonstrate incident messages retrieval."""
        print("\n📋 Station Messages:")
        print("-" * 70)
        messages_data = self.get_station_messages()
        
        if isinstance(messages_data, StationMessagesError):
            print(messages_data.message)
        elif isinstance(messages_data, StationMessagesResponse) and not messages_data.messages:
            print("No incident messages available")
        elif isinstance(messages_data, StationMessagesResponse):
            print(f"Found {len(messages_data.messages)} incident message(s)")
            print(f"{'ID':<15} {'Category':<12} {'Severity':<12} {'Title':<45}")
            print("-" * 84)
            
            for incident in messages_data.messages[:5]:  # Show first 5
                incident_id = (incident.id or 'N/A')[:13]
                category = (incident.category or 'Unknown')[:10]
                severity = (incident.severity or 'N/A')[:10]
                title = (incident.title or 'No title')[:43]
                print(f"{incident_id:<15} {category:<12} {severity:<12} {title:<45}")
    
    def _demo_service_details(self) -> None:
        """Demonstrate service details retrieval."""
        print("\n📋 Service Details:")
        print("-" * 70)
        
        # First get a departure board to obtain a service ID
        board_data = self.get_departure_board('GLC', num_rows=1)
        
        if isinstance(board_data, DepartureBoardResponse) and board_data.trains:
            # Get detailed departures to obtain service ID
            details_data = self.get_next_departures_with_details('GLC', time_window=120)
            
            if isinstance(details_data, DetailedDeparturesResponse) and details_data.trains:
                # Use the first train's service ID
                first_train = details_data.trains[0]
                service_id = first_train.service_id
                
                if service_id and service_id != 'N/A':
                    print(f"Fetching details for service: {service_id}")
                    service_details = self.get_service_details(service_id)
                    
                    if isinstance(service_details, ServiceDetailsResponse):
                        print(f"\nService: {service_details.origin} → {service_details.destination}")
                        print(f"Operator: {service_details.operator or 'Unknown'}")
                        print(f"Service Type: {service_details.service_type or 'Unknown'}")
                        print(f"Status: {'Cancelled' if service_details.is_cancelled else 'Running'}")
                        
                        if service_details.calling_points:
                            print(f"\nCalling Points ({len(service_details.calling_points)} stops):")
                            print(f"{'Station':<30} {'Scheduled':<10} {'Expected':<10} {'Platform':<8}")
                            print("-" * 58)
                            for stop in service_details.calling_points[:10]:  # Show first 10
                                sched = stop.scheduled_time or '-'
                                est = stop.estimated_time or '-'
                                plat = stop.platform or 'TBA'
                                print(f"{stop.location_name:<30} {sched:<10} {est:<10} {plat:<8}")
                    elif isinstance(service_details, ServiceDetailsError):
                        print(f"Error: {service_details.message}")
                else:
                    print("No valid service ID available")
            else:
                print("Unable to fetch departure details for service ID")
        else:
            print("Unable to fetch departures to get service ID")
    
    def _get_train_status(self, train: Dict) -> str:
        """Determine train status from train details."""
        if train['is_cancelled']:
            return "Cancelled"
        elif train['etd'] == train['std']:
            return "On time"
        else:
            return "Delayed"


# ============================================================================
# Module-Level Wrapper Functions (Backwards Compatibility)
# ============================================================================

_default_tools = TrainTools(ldb_token=LDB_TOKEN, wsdl=WSDL)


def get_departure_board(station_code: str, num_rows: int = 10) -> Union[DepartureBoardResponse, DepartureBoardError]:
    """Module-level wrapper for TrainTools.get_departure_board()."""
    return _default_tools.get_departure_board(station_code, num_rows=num_rows)


def get_next_departures_with_details(
    station_code: str, 
    filter_list: Union[Iterable[str], Sequence[str], Set[str], None] = None, 
    time_offset: int = 0, 
    time_window: int = 120
) -> Union[DetailedDeparturesResponse, DetailedDeparturesError]:
    """Module-level wrapper for TrainTools.get_next_departures_with_details()."""
    return _default_tools.get_next_departures_with_details(
        station_code, 
        filter_list=filter_list, 
        time_offset=time_offset, 
        time_window=time_window
    )


def format_departures(board_data: Union[DepartureBoardResponse, DepartureBoardError, Dict]) -> str:
    """Module-level wrapper for TrainTools.format_departures()."""
    return _default_tools.format_departures(board_data)


def get_station_messages(station_code: Optional[str] = None) -> Union[StationMessagesResponse, StationMessagesError]:
    """Module-level wrapper for TrainTools.get_station_messages()."""
    return _default_tools.get_station_messages(station_code)


def get_service_details(service_id: str) -> Union[ServiceDetailsResponse, ServiceDetailsError]:
    """Module-level wrapper for TrainTools.get_service_details()."""
    return _default_tools.get_service_details(service_id)


def main_demo() -> None:
    """Demo function to run the main method of TrainTools."""
    _default_tools.main()


# ============================================================================
# Entry Point
# ============================================================================

if __name__ == "__main__":
    main_demo()

