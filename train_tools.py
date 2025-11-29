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

    def get_next_departures_with_details(self, station_code: str, filter_list: Union[Iterable[str], Sequence[str], Set[str]], time_offset: int = 0, time_window: int = 120) -> dict:
        """Fetch next departures with detailed information for a given station.

        Parameters:
        - station_code: CRS code for origin station (e.g., 'EUS').
        - filter_list: Iterable of destination CRS codes to filter on (list/tuple/set). Must contain at least one item. Plain strings are not accepted.
        - time_offset: Minutes offset from current time (default 0).
        - time_window: Time window in minutes to search (default 120).
        """
        try:
            settings = Settings(strict=False)
            client = Client(wsdl=self.wsdl, settings=settings)

            header_value = self._make_header()

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
            # Response structure: departures.destination contains DepartureItemWithCallingPoints,
            # each with a service element containing detailed information
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

    def get_station_messages(self, station_code: str) -> dict:
        """Fetch station disruption/incident messages.

        Updated endpoint:
        GET https://api1.raildata.org.uk/1010-knowlegebase-incidents-xml-feed1_0/incidents.xml

        The feed is XML; for backward compatibility tests we also attempt JSON first.
        Returns normalized messages plus raw payload (XML string or JSON object).
        """
        try:
            if not self.disruptions_api_key:
                return {
                    'error': 'Missing API key',
                    'message': 'DISRUPTIONS_API_KEY (or RDG_API_KEY) is not set in environment.'
                }

            crs = station_code.upper()
            url = "https://api1.raildata.org.uk/1010-knowlegebase-incidents-xml-feed1_0/incidents.xml"
            headers = {
                'x-apikey': self.disruptions_api_key
            }

            resp = requests.get(url, headers=headers, timeout=15)
            resp.raise_for_status()
            content_type = resp.headers.get('Content-Type', '')

            json_payload = None
            xml_root = None
            raw_data = None
            # Try JSON first (keeps existing tests working)
            try:
                json_payload = resp.json()
                raw_data = json_payload
            except ValueError:
                if 'xml' in content_type or resp.text.strip().startswith('<'):
                    import xml.etree.ElementTree as ET
                    try:
                        xml_root = ET.fromstring(resp.text)
                        raw_data = resp.text
                    except ET.ParseError as pe:
                        return {
                            'error': 'ParseError',
                            'message': f'Unable to parse XML station messages: {pe}'
                        }
                else:
                    return {
                        'error': 'UnsupportedFormat',
                        'message': 'Response was neither valid JSON nor XML.'
                    }

            # Collect items
            items = []
            if json_payload is not None:
                if isinstance(json_payload, list):
                    items = json_payload
                elif isinstance(json_payload, dict):
                    for key in ('messages', 'stationMessages', 'data', 'results', 'incidents'):
                        if key in json_payload and isinstance(json_payload[key], list):
                            items = json_payload[key]
                            break
            elif xml_root is not None:
                # Attempt both incident and message elements
                for elem in xml_root.findall('.//incident') + xml_root.findall('.//message'):
                    node_dict = {}
                    for child in list(elem):
                        node_dict[child.tag.lower()] = (child.text or '').strip()
                    items.append(node_dict)

            def pick(d: dict, *keys):
                # Case-insensitive lookup for keys
                lower_map = {k.lower(): v for k, v in d.items()}
                for k in keys:
                    k_lower = k.lower()
                    if k_lower in lower_map and lower_map[k_lower] is not None:
                        return lower_map[k_lower]
                return None

            normalized = []
            for item in items:
                if not isinstance(item, dict):
                    continue
                normalized.append({
                    'crs': crs,
                    'id': pick(item, 'id', 'messageid', 'uid', 'incidentid'),
                    'category': pick(item, 'category', 'categorycode', 'type'),
                    'severity': pick(item, 'severity', 'priority', 'level', 'impact'),
                    'title': pick(item, 'title', 'headline', 'summary', 'subject'),
                    'message': pick(item, 'message', 'messagetext', 'body', 'description', 'detail'),
                    'start_time': pick(item, 'starttime', 'start', 'validfrom', 'from'),
                    'end_time': pick(item, 'endtime', 'end', 'validto', 'to'),
                    'last_updated': pick(item, 'lastupdated', 'updatedat', 'updatetime', 'modified'),
                    'source': pick(item, 'source', 'origin', 'publisher', 'provider')
                })

            return {
                'station': crs,
                'messages': normalized,
                'raw': raw_data,
                'message': f"Found {len(normalized)} station message(s) for {crs} from incidents feed"
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
        board_data = self.get_departure_board('GLC', num_rows=5)
        formatted_board = self.format_departures(board_data)
        print(formatted_board)

        # Fetch next departures with details (filtered to show trains to Edinburgh)
        print("\n📋 Next Departures with Details (to Edinburgh):")
        print("-" * 70)
        details_data = self.get_next_departures_with_details('GLC', filter_list=['EDB'], time_window=120)
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

        # Fetch station messages (disruptions) for Glasgow Central
        print("\n📋 Station Messages:")
        print("-" * 70)
        messages_data = self.get_station_messages('GLC')
        if 'error' in messages_data:
            print(messages_data['message'])
        elif not messages_data.get('messages'):
            print(f"No station messages for {messages_data.get('station', 'GLC')}")
        else:
            print(f"Found {len(messages_data['messages'])} message(s) for {messages_data['station']}")
            print(f"{'ID':<10} {'Category':<10} {'Severity':<8} {'Title':<30} {'Last Updated':<20}")
            print("-" * 100)
            for m in messages_data['messages']:
                print(f"{str(m.get('id',''))[:10]:<10} {str(m.get('category',''))[:10]:<10} {str(m.get('severity',''))[:8]:<8} {str(m.get('title',''))[:30]:<30} {str(m.get('last_updated',''))[:20]:<20}")

        print("\n" + "=" * 70)


# Backwards-compatible top-level wrappers (useful for scripts/tests expecting functions)
_default_tools = TrainTools(ldb_token=LDB_TOKEN, wsdl=WSDL)

def get_departure_board(station_code: str, num_rows: int = 10) -> dict:
    return _default_tools.get_departure_board(station_code, num_rows=num_rows)


def get_next_departures_with_details(station_code: str, filter_list: Union[Iterable[str], Sequence[str], Set[str]], time_offset: int = 0, time_window: int = 120) -> dict:
    return _default_tools.get_next_departures_with_details(station_code, filter_list=filter_list, time_offset=time_offset, time_window=time_window)


def format_departures(board_data: dict) -> str:
    return _default_tools.format_departures(board_data)


def get_station_messages(station_code: str) -> dict:
    return _default_tools.get_station_messages(station_code)


def main_demo():
    print ("""Demo function to run the main method of TrainTools.""")
    _default_tools.main()


if __name__ == "__main__":
    main_demo()
