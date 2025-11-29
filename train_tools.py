#!/usr/bin/env python3
"""
Train Departure AI Agent (renamed module)
This file is a direct rename of `train_agent.py` to provide the canonical
`train_tools` module name. It contains the `TrainTools` class and the same
top-level compatibility wrappers.
"""

import os
from typing import Iterable, Sequence, Set, Union
import requests
from dotenv import load_dotenv
from agents import Agent, Runner
from zeep import Client, Settings, xsd


# Load environment variables from .env file
load_dotenv()


# Configuration defaults
DEFAULT_WSDL = 'http://lite.realtime.nationalrail.co.uk/OpenLDBWS/wsdl.aspx?ver=2021-11-01'

# Backwards-compatible module-level names (tests expect these)
LDB_TOKEN = os.getenv('LDB_TOKEN')
WSDL = DEFAULT_WSDL


class TrainTools:
    """Encapsulates train departure tool functions.

    Usage:
        tt = TrainTools(ldb_token=os.getenv('LDB_TOKEN'))
        board = tt.get_departure_board('EUS')
    """

    def __init__(self, ldb_token: str = None, wsdl: str = None):
        load_dotenv()
        self.ldb_token = ldb_token or os.getenv('LDB_TOKEN')
        self.wsdl = wsdl or DEFAULT_WSDL
        # Disruptions API configuration (REST)
        self.disruptions_base_url = os.getenv('DISRUPTIONS_BASE_URL', 'https://api1.raildeliverygroup.com')
        # Prefer specific key, fall back to a generic RDG key if present
        self.disruptions_api_key = os.getenv('DISRUPTIONS_API_KEY') or os.getenv('RDG_API_KEY')

    def _make_header(self):
        header = xsd.Element(
            '{http://thalesgroup.com/RTTI/2013-11-28/Token/types}AccessToken',
            xsd.ComplexType([
                xsd.Element(
                    '{http://thalesgroup.com/RTTI/2013-11-28/Token/types}TokenValue',
                    xsd.String()),
            ])
        )
        return header(TokenValue=self.ldb_token)

    def get_departure_board(self, station_code: str, num_rows: int = 10) -> dict:
        """Fetch departure board information for a given station."""
        try:
            settings = Settings(strict=False)
            client = Client(wsdl=self.wsdl, settings=settings)

            header_value = self._make_header()

            res = client.service.GetDepartureBoard(
                numRows=num_rows,
                crs=station_code.upper(),
                _soapheaders=[header_value]
            )

            # Format response
            trains = []
            if hasattr(res, 'trainServices') and res.trainServices:
                for service in res.trainServices.service:
                    destination = (
                        service.destination.location[0].locationName
                        if service.destination and service.destination.location
                        else "Unknown"
                    )
                    trains.append({
                        'std': service.std,
                        'etd': service.etd,
                        'destination': destination,
                        'platform': getattr(service, 'platform', 'TBA'),
                        'operator': getattr(service, 'operator', 'Unknown')
                    })

            return {
                'station': res.locationName,
                'trains': trains,
                'message': f"Found {len(trains)} departing trains from {res.locationName}"
            }

        except Exception as e:
            return {
                'error': str(e),
                'message': f"Unable to fetch departure information: {str(e)}"
            }

    def get_next_departures_with_details(self, station_code: str, filter_list: Union[Iterable[str], Sequence[str], Set[str], None] = None, time_offset: int = 0, time_window: int = 120) -> dict:
        """Fetch next departures with detailed information for a given station.

        Parameters:
        - station_code: CRS code for origin station (e.g., 'EUS').
        - filter_list: Optional iterable of destination CRS codes to filter on (list/tuple/set). If None, uses GetDepBoardWithDetails instead. Plain strings are not accepted.
        - time_offset: Minutes offset from current time (default 0).
        - time_window: Time window in minutes to search (default 120).
        """
        try:
            settings = Settings(strict=False)
            client = Client(wsdl=self.wsdl, settings=settings)

            header_value = self._make_header()

            # If no filter_list provided, use GetDepBoardWithDetails
            if filter_list is None:
                res = client.service.GetDepBoardWithDetails(
                    numRows=150,
                    crs=station_code.upper(),
                    timeOffset=time_offset,
                    timeWindow=time_window,
                    _soapheaders=[header_value]
                )
            else:
                # Build filter list for SOAP call; API requires at least one destination CRS
                # Reject a single string (iterable of characters) and ensure we have at least one code
                if isinstance(filter_list, str):
                    raise ValueError("filter_list must be an iterable of CRS codes (e.g., list/tuple/set), not a string")
                if not filter_list:
                    raise ValueError("filter_list must be a non-empty iterable of destination CRS codes")
                filter_crs = [str(c).upper() for c in filter_list if str(c).strip()]
                if not filter_crs:
                    raise ValueError("filter_list must contain at least one valid CRS code")

                res = client.service.GetNextDeparturesWithDetails(
                    crs=station_code.upper(),
                    filterList={'crs': filter_crs},
                    timeOffset=time_offset,
                    timeWindow=time_window,
                    _soapheaders=[header_value]
                )

            trains = []
            # Handle response structure based on API call type
            if filter_list is None:
                # GetDepBoardWithDetails returns trainServices
                if hasattr(res, 'trainServices') and res.trainServices:
                    for service in res.trainServices.service:
                        # Extract destination name
                        dest_name = "Unknown"
                        if hasattr(service, 'destination') and service.destination:
                            if hasattr(service.destination, 'location') and service.destination.location:
                                dest_name = service.destination.location[0].locationName
                        
                        train_detail = {
                            'std': service.std,
                            'etd': service.etd,
                            'destination': dest_name,
                            'platform': getattr(service, 'platform', 'TBA'),
                            'operator': getattr(service, 'operator', 'Unknown'),
                            'service_id': getattr(service, 'serviceID', 'N/A'),
                            'service_type': getattr(service, 'serviceType', 'Unknown'),
                            'length': getattr(service, 'length', 'Unknown'),
                            'is_cancelled': getattr(service, 'isCancelled', False),
                            'cancel_reason': getattr(service, 'cancelReason', None),
                            'delay_reason': getattr(service, 'delayReason', None),
                        }
                        trains.append(train_detail)
            else:
                # GetNextDeparturesWithDetails returns departures.destination structure
                if hasattr(res, 'departures') and res.departures and hasattr(res.departures, 'destination'):
                    for destination_item in res.departures.destination:
                        service = destination_item.service
                        
                        # Extract destination name from the service's destination element
                        dest_name = "Unknown"
                        if hasattr(service, 'destination') and service.destination:
                            if hasattr(service.destination, 'location') and service.destination.location:
                                dest_name = service.destination.location[0].locationName
                        
                        train_detail = {
                            'std': service.std,
                            'etd': service.etd,
                            'destination': dest_name,
                            'platform': getattr(service, 'platform', 'TBA'),
                            'operator': getattr(service, 'operator', 'Unknown'),
                            'service_id': getattr(service, 'serviceID', 'N/A'),
                            'service_type': getattr(service, 'serviceType', 'Unknown'),
                            'length': getattr(service, 'length', 'Unknown'),
                            'is_cancelled': getattr(service, 'isCancelled', False),
                            'cancel_reason': getattr(service, 'cancelReason', None),
                            'delay_reason': getattr(service, 'delayReason', None),
                        }
                        trains.append(train_detail)

            return {
                'station': res.locationName,
                'trains': trains,
                'message': f"Found {len(trains)} next departing trains with details from {res.locationName}"
            }

        except Exception as e:
            return {
                'error': str(e),
                'message': f"Unable to fetch next departures with details: {str(e)}"
            }

    def get_station_messages(self) -> dict:
        """Fetch station disruption/incident messages.

        Endpoint:
        GET https://api1.raildata.org.uk/1010-knowlegebase-incidents-xml-feed1_0/incidents.xml

        The feed returns XML with PtIncident elements containing incident information.
        Returns normalized messages plus raw XML payload.
        """
        try:
            if not self.disruptions_api_key:
                return {
                    'error': 'Missing API key',
                    'message': 'DISRUPTIONS_API_KEY (or RDG_API_KEY) is not set in environment.'
                }
            
            url = "https://api1.raildata.org.uk/1010-knowlegebase-incidents-xml-feed1_0/incidents.xml"
            
            headers = {
                'x-apikey': self.disruptions_api_key,
                'User-Agent': 'TrainTools/1.0'
            }

            resp = requests.get(url, headers=headers, timeout=15)
            resp.raise_for_status()

            # Parse XML response
            import xml.etree.ElementTree as ET
            try:
                xml_root = ET.fromstring(resp.text)
            except ET.ParseError as pe:
                return {
                    'error': 'ParseError',
                    'message': f'Unable to parse XML station messages: {pe}'
                }

            # Define namespace map for the XML
            ns = {
                'inc': 'http://nationalrail.co.uk/xml/incident',
                'com': 'http://nationalrail.co.uk/xml/common'
            }

            # Extract all PtIncident elements
            incidents = xml_root.findall('.//inc:PtIncident', ns)
            if not incidents:
                # Try without namespace if namespaced search fails
                incidents = xml_root.findall('.//PtIncident')

            normalized = []
            for incident in incidents:
                # Helper function to get text from element (handles namespaces)
                def get_text(elem, path, namespaces=ns):
                    # First try with incident namespace if path doesn't have prefix
                    if not ':' in path and not path.startswith('.//'):
                        try:
                            found = elem.find('inc:' + path, namespaces)
                            if found is not None and found.text:
                                return found.text.strip()
                        except:
                            pass
                    
                    # Try the path as given
                    try:
                        found = elem.find(path, namespaces)
                        if found is not None and found.text:
                            return found.text.strip()
                    except:
                        pass
                    
                    # Try without namespace
                    try:
                        simple_path = path.split(':')[-1] if ':' in path else path
                        found = elem.find('.//' + simple_path)
                        if found is not None and found.text:
                            return found.text.strip()
                    except:
                        pass
                    return None

                # Extract validity period times
                start_time = get_text(incident, './/com:StartTime')
                end_time = get_text(incident, './/com:EndTime')
                last_updated = get_text(incident, './/com:LastChangedDate')

                # Extract incident details
                incident_number = get_text(incident, 'IncidentNumber')
                summary = get_text(incident, 'Summary')
                description = get_text(incident, 'Description')
                priority = get_text(incident, 'IncidentPriority')
                planned = get_text(incident, 'Planned')

                # Extract operator information
                operators = []
                operator_elems = incident.findall('.//inc:AffectedOperator', ns)
                if not operator_elems:
                    operator_elems = incident.findall('.//AffectedOperator')
                
                for op_elem in operator_elems:
                    op_ref = get_text(op_elem, 'OperatorRef')
                    op_name = get_text(op_elem, 'OperatorName')
                    if op_ref or op_name:
                        operators.append({'ref': op_ref, 'name': op_name})

                # Extract routes affected
                routes = get_text(incident, './/inc:RoutesAffected')

                normalized.append({
                    'id': incident_number,
                    'category': 'planned' if planned == 'true' else 'unplanned',
                    'severity': priority,
                    'title': summary,
                    'message': description,
                    'start_time': start_time,
                    'end_time': end_time,
                    'last_updated': last_updated,
                    'operators': operators,
                    'routes_affected': routes,
                    'is_planned': planned == 'true'
                })

            return {
                'messages': normalized,
                'raw': resp.text,
                'message': f"Found {len(normalized)} incident(s) from incidents feed"
            }

        except requests.HTTPError as http_err:
            status = getattr(http_err.response, 'status_code', 'unknown')
            return {
                'error': f"HTTP {status}",
                'message': f"Incidents feed request failed with status {status}: {http_err}"
            }
        except Exception as e:
            return {
                'error': str(e),
                'message': f"Unable to fetch station messages: {str(e)}"
            }

    def format_departures(self, board_data: dict) -> str:
        """Format departure board data into a readable string."""
        if 'error' in board_data:
            return board_data['message']

        if not board_data['trains']:
            return f"No trains currently departing from {board_data['station']}"

        output = f"\n📍 Departures from {board_data['station']}\n"
        output += "=" * 70 + "\n"
        output += f"{'STD':<8} {'ETD':<8} {'Destination':<30} {'Platform':<8} {'Operator':<15}\n"
        output += "-" * 70 + "\n"

        for train in board_data['trains']:
            output += f"{train['std']:<8} {train['etd']:<8} {train['destination']:<30} {train['platform']:<8} {train['operator']:<15}\n"

        return output

    def main(self):
        """Demo method: fetch and display departures for Glasgow Central."""
        print("\n" + "=" * 70)
        print("🚂 Train Departure Information for Glasgow Central")
        print("=" * 70)

        # Fetch basic departure board
        print("\n📋 Basic Departure Board:")
        print("-" * 70)
        board_data = self.get_departure_board('GLC', num_rows=3)
        formatted_board = self.format_departures(board_data)
        print(formatted_board)

        # Fetch next departures with details (filtered to show trains to Edinburgh)
        print("\n📋 Next Departures with Details:")
        print("-" * 70)
        details_data = self.get_next_departures_with_details('GLC', time_window=120)
        if 'error' not in details_data and details_data['trains']:
            print(f"\nStation: {details_data['station']}")
            print(f"{'STD':<8} {'ETD':<8} {'Destination':<25} {'Status':<15} {'Reason':<20}")
            print("-" * 76)
            for train in details_data['trains']:
                status = "Cancelled" if train['is_cancelled'] else "On time" if train['etd'] == train['std'] else "Delayed"
                reason = train['cancel_reason'] or train['delay_reason'] or "-"
                print(f"{train['std']:<8} {train['etd']:<8} {train['destination']:<25} {status:<15} {reason:<20}")
        else:
            print(details_data.get('message', 'Unable to fetch details'))

        # Fetch station messages (disruptions) - incidents feed (not station-specific)
        print("\n📋 Station Messages:")
        print("-" * 70)
        messages_data = self.get_station_messages()
        if 'error' in messages_data:
            print(messages_data['message'])
        elif not messages_data.get('messages'):
            print("No incident messages available")
        else:
            print(f"Found {len(messages_data['messages'])} incident message(s)")
            print(f"{'ID':<40} {'Category':<12} {'Severity':<8} {'Title':<50}")
            print("-" * 120)
            for m in messages_data['messages'][:5]:  # Show first 5
                incident_id = str(m.get('id', ''))[:38]
                category = str(m.get('category', ''))[:10]
                severity = str(m.get('severity', ''))[:6]
                title = str(m.get('title', ''))
                print(f"{incident_id:<40} {category:<12} {severity:<8} {title:<50}")

        print("\n" + "=" * 70)


# Backwards-compatible top-level wrappers (useful for scripts/tests expecting functions)
_default_tools = TrainTools(ldb_token=LDB_TOKEN, wsdl=WSDL)

def get_departure_board(station_code: str, num_rows: int = 10) -> dict:
    return _default_tools.get_departure_board(station_code, num_rows=num_rows)


def get_next_departures_with_details(station_code: str, filter_list: Union[Iterable[str], Sequence[str], Set[str], None] = None, time_offset: int = 0, time_window: int = 120) -> dict:
    return _default_tools.get_next_departures_with_details(station_code, filter_list=filter_list, time_offset=time_offset, time_window=time_window)


def format_departures(board_data: dict) -> str:
    return _default_tools.format_departures(board_data)


def get_station_messages() -> dict:
    return _default_tools.get_station_messages()


def main_demo():
    print ("""Demo function to run the main method of TrainTools.""")
    _default_tools.main()


if __name__ == "__main__":
    main_demo()
