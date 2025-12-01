"""
Comprehensive unit tests for train_tools.py to achieve 95%+ coverage.

Tests cover:
- Service details API
- Helper methods (_build_train_detail_dict, _parse_detailed_departures, etc.)
- Main demo methods
- Module-level wrapper functions
- Edge cases and error conditions
"""

import pytest
import requests
from unittest.mock import Mock, patch, MagicMock, PropertyMock
import train_tools
from train_tools import (
    TrainTools,
    ServiceDetailsResponse,
    ServiceDetailsError,
    DetailedDeparturesResponse,
    DetailedDeparturesError,
    DepartureBoardResponse,
    DepartureBoardError,
    StationMessagesResponse,
    StationMessagesError,
)


class TestServiceDetails:
    """Tests for get_service_details method."""
    
    @patch('requests.get')
    def test_get_service_details_success(self, mock_get):
        """Test successful service details retrieval."""
        mock_response = {
            'serviceID': 'test123',
            'operator': 'Test Rail',
            'operatorCode': 'TR',
            'serviceType': 'train',
            'isCancelled': False,
            'std': '10:00',
            'etd': '10:02',
            'platform': '5',
            'origin': [{'location': [{'locationName': 'London'}]}],
            'destination': [{'location': [{'locationName': 'Manchester'}]}],
            'subsequentCallingPoints': [
                {
                    'callingPoint': [
                        {
                            'locationName': 'Birmingham',
                            'crs': 'BHM',
                            'st': '11:00',
                            'et': '11:00',
                            'platform': '3',
                            'length': 8
                        }
                    ]
                }
            ]
        }
        
        mock_resp = MagicMock()
        mock_resp.json.return_value = mock_response
        mock_resp.raise_for_status.return_value = None
        mock_get.return_value = mock_resp
        
        tools = TrainTools()
        result = tools.get_service_details('test123')
        
        assert isinstance(result, ServiceDetailsResponse)
        assert result.service_id == 'test123'
        assert result.operator == 'Test Rail'
        assert result.operator_code == 'TR'
        assert result.origin == 'London'
        assert result.destination == 'Manchester'
        assert len(result.calling_points) == 1
        assert result.calling_points[0].location_name == 'Birmingham'
        assert result.calling_points[0].length == '8'  # Converted to string
    
    @patch('requests.get')
    def test_get_service_details_with_cancelled_service(self, mock_get):
        """Test service details for cancelled service."""
        mock_response = {
            'serviceID': 'cancelled123',
            'isCancelled': True,
            'cancelReason': 'Staff shortage',
            'origin': [{'location': [{'locationName': 'London'}]}],
            'destination': [{'location': [{'locationName': 'Edinburgh'}]}],
        }
        
        mock_resp = MagicMock()
        mock_resp.json.return_value = mock_response
        mock_resp.raise_for_status.return_value = None
        mock_get.return_value = mock_resp
        
        tools = TrainTools()
        result = tools.get_service_details('cancelled123')
        
        assert isinstance(result, ServiceDetailsResponse)
        assert result.is_cancelled is True
        assert result.cancel_reason == 'Staff shortage'
    
    @patch('requests.get')
    def test_get_service_details_with_delay(self, mock_get):
        """Test service details for delayed service."""
        mock_response = {
            'serviceID': 'delayed123',
            'delayReason': 'Signal failure',
            'origin': [{'location': [{'locationName': 'A'}]}],
            'destination': [{'location': [{'locationName': 'B'}]}],
        }
        
        mock_resp = MagicMock()
        mock_resp.json.return_value = mock_response
        mock_resp.raise_for_status.return_value = None
        mock_get.return_value = mock_resp
        
        tools = TrainTools()
        result = tools.get_service_details('delayed123')
        
        assert isinstance(result, ServiceDetailsResponse)
        assert result.delay_reason == 'Signal failure'
    
    @patch('requests.get')
    def test_get_service_details_http_error(self, mock_get):
        """Test HTTP error handling."""
        mock_resp = MagicMock()
        mock_resp.status_code = 404
        mock_resp.raise_for_status.side_effect = requests.HTTPError(response=mock_resp)
        mock_get.return_value = mock_resp
        
        tools = TrainTools()
        result = tools.get_service_details('notfound')
        
        assert isinstance(result, ServiceDetailsError)
        assert 'HTTP 404' in result.error
    
    @patch('requests.get')
    def test_get_service_details_network_error(self, mock_get):
        """Test network error handling."""
        mock_get.side_effect = requests.RequestException('Network error')
        
        tools = TrainTools()
        result = tools.get_service_details('test')
        
        assert isinstance(result, ServiceDetailsError)
        assert 'Network error' in result.error
    
    @patch('requests.get')
    def test_get_service_details_json_parse_error(self, mock_get):
        """Test JSON parsing error handling."""
        mock_resp = MagicMock()
        mock_resp.json.side_effect = ValueError('Invalid JSON')
        mock_resp.raise_for_status.return_value = None
        mock_get.return_value = mock_resp
        
        tools = TrainTools()
        result = tools.get_service_details('test')
        
        assert isinstance(result, ServiceDetailsError)
        assert 'Error parsing service details' in result.message
    
    @patch('requests.get')
    def test_get_service_details_with_nested_result(self, mock_get):
        """Test service details with GetServiceDetailsResult wrapper."""
        mock_response = {
            'GetServiceDetailsResult': {
                'serviceID': 'nested123',
                'operator': 'Test Operator',
                'origin': [{'location': [{'locationName': 'Start'}]}],
                'destination': [{'location': [{'locationName': 'End'}]}],
            }
        }
        
        mock_resp = MagicMock()
        mock_resp.json.return_value = mock_response
        mock_resp.raise_for_status.return_value = None
        mock_get.return_value = mock_resp
        
        tools = TrainTools()
        result = tools.get_service_details('nested123')
        
        assert isinstance(result, ServiceDetailsResponse)
        assert result.operator == 'Test Operator'
    
    @patch('requests.get')
    def test_get_service_details_with_zero_length(self, mock_get):
        """Test handling of zero length (edge case that caused original bug)."""
        mock_response = {
            'serviceID': 'test',
            'origin': [{'location': [{'locationName': 'A'}]}],
            'destination': [{'location': [{'locationName': 'B'}]}],
            'subsequentCallingPoints': [
                {
                    'callingPoint': [
                        {
                            'locationName': 'Stop',
                            'crs': 'STP',
                            'length': 0  # Integer zero
                        }
                    ]
                }
            ]
        }
        
        mock_resp = MagicMock()
        mock_resp.json.return_value = mock_response
        mock_resp.raise_for_status.return_value = None
        mock_get.return_value = mock_resp
        
        tools = TrainTools()
        result = tools.get_service_details('test')
        
        assert isinstance(result, ServiceDetailsResponse)
        assert result.calling_points[0].length == '0'


class TestHelperMethods:
    """Tests for private helper methods."""
    
    def test_extract_destination_name(self):
        """Test _extract_destination_name helper."""
        tools = TrainTools()
        
        # Mock service with destination
        service = Mock()
        service.destination = Mock()
        location = Mock()
        location.locationName = 'London Euston'
        service.destination.location = [location]
        
        result = tools._extract_destination_name(service)
        assert result == 'London Euston'
    
    def test_extract_destination_name_no_destination(self):
        """Test _extract_destination_name with no destination."""
        tools = TrainTools()
        
        service = Mock()
        service.destination = None
        
        result = tools._extract_destination_name(service)
        assert result == 'Unknown'
    
    def test_build_train_detail_dict(self):
        """Test _build_train_detail_dict helper."""
        tools = TrainTools()
        
        service = Mock()
        service.std = '10:00'
        service.etd = '10:05'
        service.platform = '3'
        service.operator = 'Test Operator'
        service.serviceID = 'svc123'
        service.serviceType = 'Express'
        service.length = 8
        service.isCancelled = True
        service.cancelReason = 'Staff shortage'
        service.delayReason = None
        
        # Mock destination
        service.destination = Mock()
        location = Mock()
        location.locationName = 'Manchester'
        service.destination.location = [location]
        
        result = tools._build_train_detail_dict(service)
        
        assert result['std'] == '10:00'
        assert result['etd'] == '10:05'
        assert result['destination'] == 'Manchester'
        assert result['platform'] == '3'
        assert result['operator'] == 'Test Operator'
        assert result['service_id'] == 'svc123'
        assert result['service_type'] == 'Express'
        assert result['length'] == '8'
        assert result['is_cancelled'] is True
        assert result['cancel_reason'] == 'Staff shortage'
    
    def test_build_train_detail_dict_with_none_values(self):
        """Test _build_train_detail_dict with None values."""
        tools = TrainTools()
        
        service = Mock()
        service.std = '10:00'
        service.etd = '10:00'
        service.platform = None
        service.operator = None
        service.serviceID = None
        service.serviceType = None
        service.length = None
        service.isCancelled = None
        service.cancelReason = None
        service.delayReason = None
        
        service.destination = Mock()
        location = Mock()
        location.locationName = 'Test'
        service.destination.location = [location]
        
        result = tools._build_train_detail_dict(service)
        
        assert result['platform'] == 'TBA'
        assert result['operator'] == 'Unknown'
        assert result['service_id'] == 'N/A'
        assert result['service_type'] == 'Unknown'
        assert result['length'] == 'Unknown'
        assert result['is_cancelled'] is False
    
    def test_get_text_with_element(self):
        """Test _get_text with valid element."""
        import xml.etree.ElementTree as ET
        tools = TrainTools()
        
        element = ET.fromstring('<test>Hello World</test>')
        result = tools._get_text(element)
        assert result == 'Hello World'
    
    def test_get_text_with_none(self):
        """Test _get_text with None."""
        tools = TrainTools()
        result = tools._get_text(None)
        assert result is None


class TestParseDetailedDepartures:
    """Tests for _parse_detailed_departures method."""
    
    def test_parse_detailed_departures_unfiltered(self):
        """Test parsing unfiltered departures (GetDepBoardWithDetails)."""
        tools = TrainTools()
        
        # Mock response with trainServices
        response = Mock()
        response.trainServices = Mock()
        
        service1 = Mock()
        service1.std = '10:00'
        service1.etd = '10:00'
        service1.platform = '1'
        service1.operator = 'Test Rail'
        service1.serviceID = 'svc1'
        service1.serviceType = 'Train'
        service1.length = 8
        service1.isCancelled = False
        service1.cancelReason = None
        service1.delayReason = None
        service1.destination = Mock()
        dest_location = Mock()
        dest_location.locationName = 'London'
        service1.destination.location = [dest_location]
        
        response.trainServices.service = [service1]
        
        result = tools._parse_detailed_departures(response, is_unfiltered=True)
        
        assert len(result) == 1
        assert result[0].std == '10:00'
        assert result[0].destination == 'London'
    
    def test_parse_detailed_departures_filtered(self):
        """Test parsing filtered departures (GetNextDeparturesWithDetails)."""
        tools = TrainTools()
        
        # Mock response with departures.destination structure
        response = Mock()
        response.departures = Mock()
        
        destination_item = Mock()
        service1 = Mock()
        service1.std = '11:00'
        service1.etd = '11:00'
        service1.platform = '2'
        service1.operator = 'Another Rail'
        service1.serviceID = 'svc2'
        service1.serviceType = 'Express'
        service1.length = 6
        service1.isCancelled = False
        service1.cancelReason = None
        service1.delayReason = None
        service1.destination = Mock()
        dest_location = Mock()
        dest_location.locationName = 'Manchester'
        service1.destination.location = [dest_location]
        
        destination_item.service = service1
        response.departures.destination = [destination_item]
        
        result = tools._parse_detailed_departures(response, is_unfiltered=False)
        
        assert len(result) == 1
        assert result[0].std == '11:00'
        assert result[0].destination == 'Manchester'
    
    def test_parse_detailed_departures_no_services(self):
        """Test parsing with no services."""
        tools = TrainTools()
        
        response = Mock()
        response.trainServices = None
        
        result = tools._parse_detailed_departures(response, is_unfiltered=True)
        assert result == []


class TestParseIncidents:
    """Tests for _parse_incidents method."""
    
    def test_parse_incidents_basic(self):
        """Test basic incident parsing."""
        import xml.etree.ElementTree as ET
        tools = TrainTools()
        
        xml_data = '''<?xml version="1.0"?>
<Incidents xmlns:inc="http://nationalrail.co.uk/xml/incident" xmlns:com="http://nationalrail.co.uk/xml/common">
  <inc:PtIncident>
    <inc:IncidentNumber>12345</inc:IncidentNumber>
    <inc:Planned>true</inc:Planned>
    <inc:IncidentPriority>1</inc:IncidentPriority>
    <inc:Summary>Test incident</inc:Summary>
    <inc:Description>Test description</inc:Description>
    <com:StartTime>2025-01-01T00:00:00</com:StartTime>
    <com:EndTime>2025-01-02T00:00:00</com:EndTime>
    <com:LastChangedDate>2025-01-01T12:00:00</com:LastChangedDate>
    <inc:RoutesAffected>London to Manchester</inc:RoutesAffected>
  </inc:PtIncident>
</Incidents>'''
        
        root = ET.fromstring(xml_data)
        result = tools._parse_incidents(root, None)
        
        assert len(result) == 1
        assert result[0].id == '12345'
        assert result[0].category == 'planned'
        assert result[0].is_planned is True
    
    def test_parse_incidents_with_station_filter(self):
        """Test incident parsing with station filter."""
        import xml.etree.ElementTree as ET
        tools = TrainTools()
        
        xml_data = '''<?xml version="1.0"?>
<Incidents xmlns:inc="http://nationalrail.co.uk/xml/incident" xmlns:com="http://nationalrail.co.uk/xml/common">
  <inc:PtIncident>
    <inc:IncidentNumber>1</inc:IncidentNumber>
    <inc:Planned>false</inc:Planned>
    <inc:Summary>Test 1</inc:Summary>
    <inc:RoutesAffected>Victoria to Brighton</inc:RoutesAffected>
  </inc:PtIncident>
  <inc:PtIncident>
    <inc:IncidentNumber>2</inc:IncidentNumber>
    <inc:Planned>false</inc:Planned>
    <inc:Summary>Test 2</inc:Summary>
    <inc:RoutesAffected>Euston to Manchester</inc:RoutesAffected>
  </inc:PtIncident>
</Incidents>'''
        
        root = ET.fromstring(xml_data)
        result = tools._parse_incidents(root, 'VIC')
        
        # Should only include incident with Victoria
        assert len(result) == 1
        assert 'Victoria' in result[0].routes_affected


class TestModuleLevelFunctions:
    """Tests for module-level wrapper functions."""
    
    @patch('train_tools.TrainTools.get_departure_board')
    def test_module_get_departure_board(self, mock_method):
        """Test module-level get_departure_board."""
        mock_method.return_value = DepartureBoardResponse(
            station='Test',
            trains=[],
            message='Test'
        )
        
        result = train_tools.get_departure_board('TST')
        assert isinstance(result, DepartureBoardResponse)
        mock_method.assert_called_once_with('TST', num_rows=10)
    
    @patch('train_tools.TrainTools.get_next_departures_with_details')
    def test_module_get_next_departures_with_details(self, mock_method):
        """Test module-level get_next_departures_with_details."""
        mock_method.return_value = DetailedDeparturesResponse(
            station='Test',
            trains=[],
            message='Test'
        )
        
        result = train_tools.get_next_departures_with_details('TST', filter_list=['LON'])
        assert isinstance(result, DetailedDeparturesResponse)
        mock_method.assert_called_once()
    
    @patch('train_tools.TrainTools.get_station_messages')
    def test_module_get_station_messages(self, mock_method):
        """Test module-level get_station_messages."""
        mock_method.return_value = StationMessagesResponse(
            messages=[],
            message='Test'
        )
        
        result = train_tools.get_station_messages('TST')
        assert isinstance(result, StationMessagesResponse)
        mock_method.assert_called_once_with('TST')
    
    @patch('train_tools.TrainTools.get_service_details')
    def test_module_get_service_details(self, mock_method):
        """Test module-level get_service_details."""
        mock_method.return_value = ServiceDetailsResponse(
            service_id='test',
            message='Test'
        )
        
        result = train_tools.get_service_details('test')
        assert isinstance(result, ServiceDetailsResponse)
        mock_method.assert_called_once_with('test')
    
    @patch('train_tools.TrainTools.format_departures')
    def test_module_format_departures(self, mock_method):
        """Test module-level format_departures."""
        mock_method.return_value = 'Formatted output'
        
        board = DepartureBoardResponse(station='Test', trains=[], message='Test')
        result = train_tools.format_departures(board)
        assert result == 'Formatted output'


class TestFormatDeparturesPydantic:
    """Tests for format_departures with Pydantic models."""
    
    def test_format_departures_with_pydantic_error(self):
        """Test formatting with Pydantic error model."""
        from train_tools import DepartureBoardError
        
        error = DepartureBoardError(
            error='Test error',
            message='Test message'
        )
        
        result = train_tools.format_departures(error)
        assert result == 'Test message'
    
    def test_format_departures_with_pydantic_response_no_trains(self):
        """Test formatting Pydantic response with no trains."""
        from train_tools import DepartureBoardResponse, TrainDeparture
        
        response = DepartureBoardResponse(
            station='Victoria',
            trains=[],
            message='No trains'
        )
        
        result = train_tools.format_departures(response)
        assert 'No trains currently departing from Victoria' in result
    
    def test_format_departures_with_pydantic_response_with_trains(self):
        """Test formatting Pydantic response with trains."""
        from train_tools import DepartureBoardResponse, TrainDeparture
        
        train = TrainDeparture(
            std='10:00',
            etd='10:05',
            destination='London',
            platform='3',
            operator='Test Rail'
        )
        
        response = DepartureBoardResponse(
            station='Manchester',
            trains=[train],
            message='Found trains'
        )
        
        result = train_tools.format_departures(response)
        assert '📍 Departures from Manchester' in result
        assert '10:00' in result
        assert '10:05' in result
        assert 'London' in result
    
    def test_format_departures_invalid_data(self):
        """Test formatting with invalid data type."""
        result = train_tools.format_departures("invalid")
        assert result == "Invalid board data format"


class TestGetNextDeparturesEdgeCases:
    """Tests for edge cases in get_next_departures_with_details."""
    
    @patch.object(TrainTools, '_create_soap_client')
    @patch.object(TrainTools, '_make_header')
    def test_get_next_departures_with_string_filter_raises_error(self, mock_header, mock_client):
        """Test that passing a string instead of list raises ValueError."""
        tools = TrainTools()
        
        result = tools.get_next_departures_with_details('EUS', filter_list='LON')
        
        assert isinstance(result, DetailedDeparturesError)
        assert 'must be a list' in result.message.lower() or 'iterable' in result.message.lower()
    
    @patch.object(TrainTools, '_create_soap_client')
    @patch.object(TrainTools, '_make_header')
    def test_get_next_departures_with_empty_filter_raises_error(self, mock_header, mock_client):
        """Test that passing an empty list raises ValueError."""
        tools = TrainTools()
        
        result = tools.get_next_departures_with_details('EUS', filter_list=[])
        
        assert isinstance(result, DetailedDeparturesError)


class TestDemoMethods:
    """Tests for demo/display methods."""
    
    @patch.object(TrainTools, 'get_departure_board')
    @patch.object(TrainTools, 'format_departures')
    @patch('builtins.print')
    def test_demo_basic_board(self, mock_print, mock_format, mock_get):
        """Test _demo_basic_board method."""
        mock_get.return_value = DepartureBoardResponse(
            station='Test',
            trains=[],
            message='Test'
        )
        mock_format.return_value = 'Formatted'
        
        tools = TrainTools()
        tools._demo_basic_board()
        
        mock_get.assert_called_once()
        mock_print.assert_called()
    
    @patch.object(TrainTools, 'get_next_departures_with_details')
    @patch('builtins.print')
    def test_demo_detailed_departures_with_trains(self, mock_print, mock_get):
        """Test _demo_detailed_departures with trains."""
        from train_tools import DetailedTrainDeparture
        
        train = DetailedTrainDeparture(
            std='10:00',
            etd='10:00',
            destination='London',
            service_id='test123'
        )
        
        mock_get.return_value = DetailedDeparturesResponse(
            station='Test',
            trains=[train],
            message='Test'
        )
        
        tools = TrainTools()
        tools._demo_detailed_departures()
        
        mock_print.assert_called()
    
    @patch.object(TrainTools, 'get_next_departures_with_details')
    @patch('builtins.print')
    def test_demo_detailed_departures_error(self, mock_print, mock_get):
        """Test _demo_detailed_departures with error."""
        mock_get.return_value = DetailedDeparturesError(
            error='Test error',
            message='Error message'
        )
        
        tools = TrainTools()
        tools._demo_detailed_departures()
        
        # Should print error message
        assert any('Error message' in str(call) for call in mock_print.call_args_list)
    
    @patch.object(TrainTools, 'get_station_messages')
    @patch('builtins.print')
    def test_demo_incident_messages_success(self, mock_print, mock_get):
        """Test _demo_incident_messages with messages."""
        from train_tools import Incident
        
        incident = Incident(
            id='test123',
            category='planned',
            title='Test incident'
        )
        
        mock_get.return_value = StationMessagesResponse(
            messages=[incident],
            message='Test'
        )
        
        tools = TrainTools()
        tools._demo_incident_messages()
        
        mock_print.assert_called()
    
    @patch.object(TrainTools, 'get_station_messages')
    @patch('builtins.print')
    def test_demo_incident_messages_error(self, mock_print, mock_get):
        """Test _demo_incident_messages with error."""
        mock_get.return_value = StationMessagesError(
            error='Test error',
            message='Error message'
        )
        
        tools = TrainTools()
        tools._demo_incident_messages()
        
        assert any('Error message' in str(call) for call in mock_print.call_args_list)
    
    @patch.object(TrainTools, 'get_station_messages')
    @patch('builtins.print')
    def test_demo_incident_messages_no_messages(self, mock_print, mock_get):
        """Test _demo_incident_messages with no messages."""
        mock_get.return_value = StationMessagesResponse(
            messages=[],
            message='No messages'
        )
        
        tools = TrainTools()
        tools._demo_incident_messages()
        
        assert any('No incident' in str(call) for call in mock_print.call_args_list)
    
    @patch.object(TrainTools, 'get_departure_board')
    @patch.object(TrainTools, 'get_next_departures_with_details')
    @patch.object(TrainTools, 'get_service_details')
    @patch('builtins.print')
    def test_demo_service_details_success(self, mock_print, mock_service, mock_details, mock_board):
        """Test _demo_service_details with successful retrieval."""
        from train_tools import TrainDeparture, DetailedTrainDeparture, ServiceLocation
        
        train = TrainDeparture(
            std='10:00',
            etd='10:00',
            destination='London'
        )
        
        detailed_train = DetailedTrainDeparture(
            std='10:00',
            etd='10:00',
            destination='London',
            service_id='real_service_id'
        )
        
        stop = ServiceLocation(
            location_name='Birmingham',
            crs='BHM',
            scheduled_time='11:00'
        )
        
        mock_board.return_value = DepartureBoardResponse(
            station='Test',
            trains=[train],
            message='Test'
        )
        
        mock_details.return_value = DetailedDeparturesResponse(
            station='Test',
            trains=[detailed_train],
            message='Test'
        )
        
        mock_service.return_value = ServiceDetailsResponse(
            service_id='real_service_id',
            origin='London',
            destination='Manchester',
            operator='Test Rail',
            calling_points=[stop],
            message='Test'
        )
        
        tools = TrainTools()
        tools._demo_service_details()
        
        mock_service.assert_called_once_with('real_service_id')
        # Should print service details
        assert mock_print.called
    
    @patch.object(TrainTools, 'get_departure_board')
    @patch('builtins.print')
    def test_demo_service_details_no_service_id(self, mock_print, mock_board):
        """Test _demo_service_details when no service ID available."""
        mock_board.return_value = DepartureBoardError(
            error='Error',
            message='No trains'
        )
        
        tools = TrainTools()
        tools._demo_service_details()
        
        assert any('Unable to fetch' in str(call) for call in mock_print.call_args_list)
    
    @patch('builtins.print')
    def test_print_header(self, mock_print):
        """Test _print_header method."""
        tools = TrainTools()
        tools._print_header()
        assert mock_print.called
    
    @patch('builtins.print')
    def test_print_footer(self, mock_print):
        """Test _print_footer method."""
        tools = TrainTools()
        tools._print_footer()
        assert mock_print.called
    
    @patch.object(TrainTools, '_print_header')
    @patch.object(TrainTools, '_demo_basic_board')
    @patch.object(TrainTools, '_demo_detailed_departures')
    @patch.object(TrainTools, '_demo_service_details')
    @patch.object(TrainTools, '_demo_incident_messages')
    @patch.object(TrainTools, '_print_footer')
    def test_main_method(self, mock_footer, mock_incidents, mock_service, 
                        mock_detailed, mock_basic, mock_header):
        """Test main demo method calls all sub-methods."""
        tools = TrainTools()
        tools.main()
        
        mock_header.assert_called_once()
        mock_basic.assert_called_once()
        mock_detailed.assert_called_once()
        mock_service.assert_called_once()
        mock_incidents.assert_called_once()
        mock_footer.assert_called_once()
    
    @patch('train_tools.TrainTools.main')
    def test_main_demo_function(self, mock_main):
        """Test main_demo() function."""
        train_tools.main_demo()
        mock_main.assert_called_once()


class TestGetTrainStatus:
    """Tests for _get_train_status helper method."""
    
    def test_get_train_status_cancelled(self):
        """Test status for cancelled train."""
        tools = TrainTools()
        train = {
            'is_cancelled': True,
            'std': '10:00',
            'etd': '10:00'
        }
        result = tools._get_train_status(train)
        assert result == "Cancelled"
    
    def test_get_train_status_on_time(self):
        """Test status for on-time train."""
        tools = TrainTools()
        train = {
            'is_cancelled': False,
            'std': '10:00',
            'etd': '10:00'
        }
        result = tools._get_train_status(train)
        assert result == "On time"
    
    def test_get_train_status_delayed(self):
        """Test status for delayed train."""
        tools = TrainTools()
        train = {
            'is_cancelled': False,
            'std': '10:00',
            'etd': '10:15'
        }
        result = tools._get_train_status(train)
        assert result == "Delayed"


class TestSOAPClientCreation:
    """Tests for SOAP client creation methods."""
    
    @patch('train_tools.Client')
    def test_create_soap_client(self, mock_client_class):
        """Test _create_soap_client method."""
        tools = TrainTools()
        tools.wsdl = 'http://test.wsdl'
        
        client = tools._create_soap_client()
        
        mock_client_class.assert_called_once()
    
    @patch('train_tools.xsd')
    def test_make_header(self, mock_xsd):
        """Test _make_header method."""
        tools = TrainTools()
        tools.ldb_token = 'test_token'
        
        # Mock the xsd.Element and xsd.ComplexType
        mock_element_class = Mock()
        mock_xsd.Element = mock_element_class
        mock_xsd.ComplexType = Mock(return_value=Mock())
        mock_xsd.String = Mock(return_value=Mock())
        
        header = tools._make_header()
        
        # Verify xsd.Element was called
        assert mock_element_class.called


class TestInitialization:
    """Tests for TrainTools initialization."""
    
    def test_init_with_tokens(self):
        """Test initialization with provided tokens."""
        tools = TrainTools(ldb_token='test_ldb', wsdl='http://test.wsdl')
        assert tools.ldb_token == 'test_ldb'
        assert tools.wsdl == 'http://test.wsdl'
    
    @patch.dict('os.environ', {'LDB_TOKEN': 'env_token'})
    def test_init_with_env_vars(self):
        """Test initialization falls back to environment variables."""
        tools = TrainTools()
        assert tools.ldb_token == 'env_token'
    
    @patch.dict('os.environ', {'DISRUPTIONS_API_KEY': 'disruption_key'})
    def test_init_disruptions_api_key(self):
        """Test disruptions API key initialization."""
        tools = TrainTools()
        assert tools.disruptions_api_key == 'disruption_key'
    
    @patch.dict('os.environ', {}, clear=True)
    @patch('train_tools.load_dotenv')
    def test_init_rdg_api_key_fallback(self, mock_load_dotenv):
        """Test RDG_API_KEY fallback."""
        # Set up clean environment with only RDG_API_KEY
        with patch.dict('os.environ', {'RDG_API_KEY': 'rdg_key'}, clear=True):
            # Mock load_dotenv to not load from .env file
            mock_load_dotenv.return_value = None
            
            tools = TrainTools()
            assert tools.disruptions_api_key == 'rdg_key'
