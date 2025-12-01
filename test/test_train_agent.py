"""
Unit tests for train_tools.py using pytest framework.

Tests cover:
- format_departures function with various data scenarios
- get_departure_board error handling
- Train agent configuration
"""

import pytest
import requests
from unittest.mock import Mock, patch, MagicMock
import train_tools


class TestFormatDepartures:
    """Tests for the format_departures function."""
    
    def test_format_departures_with_error(self):
        """Test formatting when error response is provided."""
        board_data = {
            'error': 'Connection failed',
            'message': 'Unable to fetch departure information: Connection timeout'
        }
        result = train_tools.format_departures(board_data)
        assert result == 'Unable to fetch departure information: Connection timeout'
    
    def test_format_departures_with_no_trains(self):
        """Test formatting when no trains are available."""
        board_data = {
            'station': 'Victoria',
            'trains': [],
            'message': 'Found 0 departing trains from Victoria'
        }
        result = train_tools.format_departures(board_data)
        assert 'No trains currently departing from Victoria' in result
    
    def test_format_departures_with_single_train(self):
        """Test formatting with a single train."""
        board_data = {
            'station': 'Euston',
            'trains': [
                {
                    'std': '14:30',
                    'etd': '14:32',
                    'destination': 'Manchester',
                    'platform': '5',
                    'operator': 'Avanti West Coast'
                }
            ],
            'message': 'Found 1 departing train from Euston'
        }
        result = train_tools.format_departures(board_data)
        assert '📍 Departures from Euston' in result
        assert '14:30' in result
        assert '14:32' in result
        assert 'Manchester' in result
        assert '5' in result
        assert 'Avanti West Coast' in result
    
    def test_format_departures_with_multiple_trains(self):
        """Test formatting with multiple trains."""
        board_data = {
            'station': 'Victoria',
            'trains': [
                {
                    'std': '14:00',
                    'etd': '14:02',
                    'destination': 'Brighton',
                    'platform': '3',
                    'operator': 'Southern Rail'
                },
                {
                    'std': '14:15',
                    'etd': '14:15',
                    'destination': 'Gatwick',
                    'platform': '2',
                    'operator': 'Southern Rail'
                }
            ],
            'message': 'Found 2 departing trains from Victoria'
        }
        result = train_tools.format_departures(board_data)
        assert '📍 Departures from Victoria' in result
        assert 'Brighton' in result
        assert 'Gatwick' in result
        assert result.count('Southern Rail') == 2
    
    def test_format_departures_output_structure(self):
        """Test the output format structure."""
        board_data = {
            'station': 'King\'s Cross',
            'trains': [
                {
                    'std': '10:00',
                    'etd': '10:03',
                    'destination': 'Edinburgh',
                    'platform': '7',
                    'operator': 'LNER'
                }
            ],
            'message': 'Found 1 departing train from King\'s Cross'
        }
        result = train_tools.format_departures(board_data)
        # Check for header elements
        assert '=' in result  # Header line
        assert '-' in result  # Separator line
        assert 'STD' in result
        assert 'ETD' in result
        assert 'Destination' in result
        assert 'Platform' in result
        assert 'Operator' in result


class TestGetDepartureBoard:
    """Tests for the get_departure_board function."""
    
    @patch('train_tools.Client')
    def test_get_departure_board_success(self, mock_client_class):
        """Test successful retrieval of departure board."""
        # Setup mock
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        
        # Mock response
        mock_service = MagicMock()
        mock_service.std = '14:30'
        mock_service.etd = '14:32'
        mock_service.platform = '5'
        mock_service.operator = 'Avanti'
        mock_service.destination.location = [MagicMock(locationName='Manchester')]
        
        mock_response = MagicMock()
        mock_response.locationName = 'Euston'
        mock_response.trainServices.service = [mock_service]
        
        mock_client.service.GetDepartureBoard.return_value = mock_response
        
        # Call function
        result = train_tools.get_departure_board('EUS', num_rows=10)
        
        # Assert - now checking Pydantic model
        assert isinstance(result, train_tools.DepartureBoardResponse)
        assert result.station == 'Euston'
        assert len(result.trains) == 1
        assert result.trains[0].std == '14:30'
        assert result.trains[0].destination == 'Manchester'
    
    @patch('train_tools.Client')
    def test_get_departure_board_no_trains(self, mock_client_class):
        """Test when no trains are available."""
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        
        mock_response = MagicMock()
        mock_response.locationName = 'Remote Station'
        mock_response.trainServices = None
        
        mock_client.service.GetDepartureBoard.return_value = mock_response
        
        result = train_tools.get_departure_board('RMT')
        
        assert isinstance(result, train_tools.DepartureBoardResponse)
        assert result.station == 'Remote Station'
        assert result.trains == []
    
    @patch('train_tools.Client')
    def test_get_departure_board_exception_handling(self, mock_client_class):
        """Test exception handling in get_departure_board."""
        mock_client_class.side_effect = Exception('Connection timeout')
        
        result = train_tools.get_departure_board('EUS')
        
        assert isinstance(result, train_tools.DepartureBoardError)
        assert result.error == 'Connection timeout'
        assert 'Connection timeout' in result.message
        assert 'Unable to fetch departure information' in result.message
    
    @patch('train_tools.Client')
    def test_get_departure_board_station_code_uppercase(self, mock_client_class):
        """Test that station code is converted to uppercase."""
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        
        mock_response = MagicMock()
        mock_response.locationName = 'Euston'
        mock_response.trainServices = None
        mock_client.service.GetDepartureBoard.return_value = mock_response
        
        train_tools.get_departure_board('eus')
        
        # Verify the call was made with uppercase station code
        call_args = mock_client.service.GetDepartureBoard.call_args
        assert call_args[1]['crs'] == 'EUS'
    
    @patch('train_tools.Client')
    def test_get_departure_board_default_num_rows(self, mock_client_class):
        """Test that default num_rows is 10."""
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        
        mock_response = MagicMock()
        mock_response.locationName = 'Euston'
        mock_response.trainServices = None
        mock_client.service.GetDepartureBoard.return_value = mock_response
        
        train_tools.get_departure_board('EUS')
        
        # Verify the call was made with default numRows
        call_args = mock_client.service.GetDepartureBoard.call_args
        assert call_args[1]['numRows'] == 10
    
    @patch('train_tools.Client')
    def test_get_departure_board_custom_num_rows(self, mock_client_class):
        """Test with custom num_rows parameter."""
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        
        mock_response = MagicMock()
        mock_response.locationName = 'Euston'
        mock_response.trainServices = None
        mock_client.service.GetDepartureBoard.return_value = mock_response
        
        train_tools.get_departure_board('EUS', num_rows=20)
        
        # Verify the call was made with custom numRows
        call_args = mock_client.service.GetDepartureBoard.call_args
        assert call_args[1]['numRows'] == 20
    
    @patch('train_tools.Client')
    def test_get_departure_board_missing_destination(self, mock_client_class):
        """Test handling of train with missing destination info."""
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        
        mock_service = MagicMock()
        mock_service.std = '14:30'
        mock_service.etd = '14:32'
        mock_service.platform = '5'
        mock_service.operator = 'Avanti'
        mock_service.destination = None
        
        mock_response = MagicMock()
        mock_response.locationName = 'Euston'
        mock_response.trainServices.service = [mock_service]
        
        mock_client.service.GetDepartureBoard.return_value = mock_response
        
        result = train_tools.get_departure_board('EUS')
        
        assert isinstance(result, train_tools.DepartureBoardResponse)
        assert result.trains[0].destination == 'Unknown'
    
    @patch('train_tools.Client')
    def test_get_departure_board_missing_platform(self, mock_client_class):
        """Test handling of train with missing platform info."""
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        
        mock_service = MagicMock(spec=['std', 'etd', 'operator', 'destination'])
        mock_service.std = '14:30'
        mock_service.etd = '14:32'
        mock_service.operator = 'Avanti'
        mock_service.destination.location = [MagicMock(locationName='Manchester')]
        
        mock_response = MagicMock()
        mock_response.locationName = 'Euston'
        mock_response.trainServices.service = [mock_service]
        
        mock_client.service.GetDepartureBoard.return_value = mock_response
        
        result = train_tools.get_departure_board('EUS')
        
        assert isinstance(result, train_tools.DepartureBoardResponse)
        assert result.trains[0].platform == 'TBA'


class TestGetNextDeparturesWithDetails:
    """Tests for the get_next_departures_with_details function."""
    
    @patch('train_tools.Client')
    def test_get_next_departures_with_details_success(self, mock_client_class):
        """Test successful retrieval of next departures with details."""
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        
        mock_service = MagicMock()
        mock_service.std = '14:30'
        mock_service.etd = '14:32'
        mock_service.platform = '5'
        mock_service.operator = 'Avanti'
        mock_service.serviceID = 'SVC001'
        mock_service.serviceType = 'Express'
        mock_service.length = '12'
        mock_service.isCancelled = False
        mock_service.cancelReason = None
        mock_service.delayReason = None
        mock_service.destination.location = [MagicMock(locationName='Manchester')]
        
        # Create a destination wrapper with the service
        mock_destination = MagicMock()
        mock_destination.service = mock_service
        
        # Create departures wrapper with destination list
        mock_departures = MagicMock()
        mock_departures.destination = [mock_destination]
        
        mock_response = MagicMock()
        mock_response.locationName = 'Euston'
        mock_response.departures = mock_departures
        
        mock_client.service.GetNextDeparturesWithDetails.return_value = mock_response
        
        result = train_tools.get_next_departures_with_details('EUS', filter_list=['MAN'], time_window=120)
        
        assert isinstance(result, train_tools.DetailedDeparturesResponse)
        assert result.station == 'Euston'
        assert len(result.trains) == 1
        assert result.trains[0].std == '14:30'
        assert result.trains[0].service_id == 'SVC001'
        assert result.trains[0].service_type == 'Express'
        assert result.trains[0].length == '12'
        assert result.trains[0].is_cancelled is False
    
    @patch('train_tools.Client')
    def test_get_next_departures_with_details_cancelled_train(self, mock_client_class):
        """Test retrieval with cancelled train information."""
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        
        mock_service = MagicMock()
        mock_service.std = '15:00'
        mock_service.etd = '15:00'
        mock_service.platform = 'TBA'
        mock_service.operator = 'GWR'
        mock_service.serviceID = 'SVC002'
        mock_service.serviceType = 'Standard'
        mock_service.length = '8'
        mock_service.isCancelled = True
        mock_service.cancelReason = 'Crew unavailable'
        mock_service.delayReason = None
        mock_service.destination.location = [MagicMock(locationName='Bristol')]
        
        # Create a destination wrapper with the service
        mock_destination = MagicMock()
        mock_destination.service = mock_service
        
        # Create departures wrapper with destination list
        mock_departures = MagicMock()
        mock_departures.destination = [mock_destination]
        
        mock_response = MagicMock()
        mock_response.locationName = 'Paddington'
        mock_response.departures = mock_departures
        
        mock_client.service.GetNextDeparturesWithDetails.return_value = mock_response
        
        result = train_tools.get_next_departures_with_details('PAD', filter_list=['BRI'])
        
        assert isinstance(result, train_tools.DetailedDeparturesResponse)
        assert result.trains[0].is_cancelled is True
        assert result.trains[0].cancel_reason == 'Crew unavailable'
    
    @patch('train_tools.Client')
    def test_get_next_departures_with_details_delayed_train(self, mock_client_class):
        """Test retrieval with delayed train information."""
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        
        mock_service = MagicMock()
        mock_service.std = '16:00'
        mock_service.etd = '16:05'
        mock_service.platform = '3'
        mock_service.operator = 'Southern'
        mock_service.serviceID = 'SVC003'
        mock_service.serviceType = 'Regional'
        mock_service.length = '9'
        mock_service.isCancelled = False
        mock_service.cancelReason = None
        mock_service.delayReason = 'Track works'
        mock_service.destination.location = [MagicMock(locationName='Brighton')]
        
        # Create a destination wrapper with the service
        mock_destination = MagicMock()
        mock_destination.service = mock_service
        
        # Create departures wrapper with destination list
        mock_departures = MagicMock()
        mock_departures.destination = [mock_destination]
        
        mock_response = MagicMock()
        mock_response.locationName = 'Victoria'
        mock_response.departures = mock_departures
        
        mock_client.service.GetNextDeparturesWithDetails.return_value = mock_response
        
        result = train_tools.get_next_departures_with_details('VIC', filter_list=['BTN'])
        
        assert isinstance(result, train_tools.DetailedDeparturesResponse)
        assert result.trains[0].delay_reason == 'Track works'
        assert result.trains[0].etd == '16:05'
    
    @patch('train_tools.Client')
    def test_get_next_departures_with_details_no_trains(self, mock_client_class):
        """Test when no trains are available."""
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        
        mock_response = MagicMock()
        mock_response.locationName = 'Remote Station'
        mock_response.trainServices = None
        
        mock_client.service.GetNextDeparturesWithDetails.return_value = mock_response
        
        result = train_tools.get_next_departures_with_details('RMT', filter_list=['STP'])
        
        assert isinstance(result, train_tools.DetailedDeparturesResponse)
        assert result.station == 'Remote Station'
        assert result.trains == []
    
    @patch('train_tools.Client')
    def test_get_next_departures_with_details_exception_handling(self, mock_client_class):
        """Test exception handling."""
        mock_client_class.side_effect = Exception('API unavailable')
        
        result = train_tools.get_next_departures_with_details('EUS', filter_list=['MAN'])
        
        assert isinstance(result, train_tools.DetailedDeparturesError)
        assert 'API unavailable' in result.message
        assert 'Unable to fetch next departures with details' in result.message
    
    @patch('train_tools.Client')
    def test_get_next_departures_with_details_station_code_uppercase(self, mock_client_class):
        """Test that station code is converted to uppercase."""
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        
        mock_response = MagicMock()
        mock_response.locationName = 'King\'s Cross'
        mock_response.departures = None
        mock_client.service.GetNextDeparturesWithDetails.return_value = mock_response
        
        train_tools.get_next_departures_with_details('kx', filter_list=['KGX'])
        
        call_args = mock_client.service.GetNextDeparturesWithDetails.call_args
        assert call_args[1]['crs'] == 'KX'
    
    @patch('train_tools.Client')
    def test_get_next_departures_with_details_custom_num_rows(self, mock_client_class):
        """Test with custom num_rows parameter (note: API uses timeOffset and timeWindow instead)."""
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        
        mock_response = MagicMock()
        mock_response.locationName = 'Euston'
        mock_response.departures = None
        mock_client.service.GetNextDeparturesWithDetails.return_value = mock_response
        
        train_tools.get_next_departures_with_details('EUS', filter_list=['MAN'], time_window=120)
        
        call_args = mock_client.service.GetNextDeparturesWithDetails.call_args
        # The API uses timeWindow instead of numRows
        assert call_args[1]['timeWindow'] == 120
        assert call_args[1]['timeOffset'] == 0
    
    @patch('train_tools.Client')
    def test_get_next_departures_with_details_missing_details(self, mock_client_class):
        """Test handling of missing detailed information."""
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        
        mock_service = MagicMock(spec=['std', 'etd', 'destination'])
        mock_service.std = '14:30'
        mock_service.etd = '14:32'
        mock_service.destination.location = [MagicMock(locationName='Manchester')]
        
        # Create a destination wrapper with the service
        mock_destination = MagicMock()
        mock_destination.service = mock_service
        
        # Create departures wrapper with destination list
        mock_departures = MagicMock()
        mock_departures.destination = [mock_destination]
        
        mock_response = MagicMock()
        mock_response.locationName = 'Euston'
        mock_response.departures = mock_departures
        
        mock_client.service.GetNextDeparturesWithDetails.return_value = mock_response
        
        result = train_tools.get_next_departures_with_details('EUS', filter_list=['MAN'])
        
        assert isinstance(result, train_tools.DetailedDeparturesResponse)
        assert result.trains[0].service_id == 'N/A'
        assert result.trains[0].service_type == 'Unknown'
        assert result.trains[0].length == 'Unknown'
        assert result.trains[0].is_cancelled is False



class TestEnvironmentVariables:
    """Tests for environment variable handling."""
    
    @patch.dict('os.environ', {'LDB_TOKEN': 'test-token-123'})
    def test_ldb_token_from_env(self):
        """Test that LDB_TOKEN is read from environment."""
        # Re-import to get fresh environment variables
        import importlib
        importlib.reload(train_tools)
        assert train_tools.LDB_TOKEN == 'test-token-123'
    
    def test_wsdl_endpoint_configured(self):
        """Test WSDL endpoint is properly configured."""
        assert 'lite.realtime.nationalrail.co.uk' in train_tools.WSDL
        assert 'OpenLDBWS' in train_tools.WSDL


class TestIntegration:
    """Integration tests combining multiple components."""
    
    @patch('train_tools.Client')
    def test_format_and_display_flow(self, mock_client_class):
        """Test complete flow from API call to formatted output."""
        # Setup mock
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        
        mock_service = MagicMock()
        mock_service.std = '15:45'
        mock_service.etd = '15:47'
        mock_service.platform = '1'
        mock_service.operator = 'GWR'
        mock_service.destination.location = [MagicMock(locationName='Swansea')]
        
        mock_response = MagicMock()
        mock_response.locationName = 'Paddington'
        mock_response.trainServices.service = [mock_service]
        
        mock_client.service.GetDepartureBoard.return_value = mock_response
        
        # Get board data
        board_data = train_tools.get_departure_board('PAD')
        
        # Format output
        formatted = train_tools.format_departures(board_data)
        
        # Verify complete flow
        assert 'Paddington' in formatted
        assert '15:45' in formatted
        assert '15:47' in formatted
        assert 'Swansea' in formatted
        assert '1' in formatted
        assert 'GWR' in formatted


class TestGetStationMessages:
    """Tests for the get_station_messages REST disruptions method."""

    @patch('requests.get')
    def test_get_station_messages_success_list_payload(self, mock_get):
        # Mock XML response from the actual API
        xml_payload = '''<?xml version="1.0" encoding="utf-8"?>
<Incidents xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:com="http://nationalrail.co.uk/xml/common" xmlns="http://nationalrail.co.uk/xml/incident">
  <PtIncident>
    <CreationTime>2025-11-28T08:00:00Z</CreationTime>
    <ChangeHistory>
      <com:ChangedBy>NRE CMS Editor</com:ChangedBy>
      <com:LastChangedDate>2025-11-28T07:55:00Z</com:LastChangedDate>
    </ChangeHistory>
    <IncidentNumber>m1</IncidentNumber>
    <ValidityPeriod>
      <com:StartTime>2025-11-28T08:00:00Z</com:StartTime>
      <com:EndTime>2025-11-28T18:00:00Z</com:EndTime>
    </ValidityPeriod>
    <Planned>true</Planned>
    <Summary><![CDATA[Station open]]></Summary>
    <Description><![CDATA[The station is open as normal.]]></Description>
    <IncidentPriority>1</IncidentPriority>
  </PtIncident>
  <PtIncident>
    <CreationTime>2025-11-28T09:00:00Z</CreationTime>
    <ChangeHistory>
      <com:ChangedBy>NRE CMS Editor</com:ChangedBy>
      <com:LastChangedDate>2025-11-28T09:05:00Z</com:LastChangedDate>
    </ChangeHistory>
    <IncidentNumber>m2</IncidentNumber>
    <ValidityPeriod>
      <com:StartTime>2025-11-28T09:00:00Z</com:StartTime>
    </ValidityPeriod>
    <Planned>false</Planned>
    <Summary><![CDATA[Lift out of order]]></Summary>
    <Description><![CDATA[Platform 3 lift unavailable.]]></Description>
    <IncidentPriority>2</IncidentPriority>
  </PtIncident>
</Incidents>'''

        mock_resp = MagicMock()
        mock_resp.text = xml_payload
        mock_resp.headers = {'Content-Type': 'application/xml'}
        mock_resp.raise_for_status.return_value = None
        mock_get.return_value = mock_resp

        tools = train_tools.TrainTools()
        tools.disruptions_api_key = 'test-key'
        res = tools.get_station_messages()

        # Validate response is Pydantic model
        assert isinstance(res, train_tools.StationMessagesResponse)
        assert len(res.messages) == 2
        first = res.messages[0]
        assert first.id == 'm1'
        assert first.category == 'planned'
        assert first.severity == '1'
        assert first.title == 'Station open'
        assert first.message == 'The station is open as normal.'
        assert first.is_planned == True
        
        second = res.messages[1]
        assert second.id == 'm2'
        assert second.category == 'unplanned'
        assert second.is_planned == False
        
        # Ensure correct request formation
        args, kwargs = mock_get.call_args
        assert args[0].endswith('incidents.xml')
        assert kwargs['headers']['x-apikey'] == 'test-key'

    @patch('requests.get')
    def test_get_station_messages_success_dict_messages(self, mock_get):
        # Mock XML with operator and routes information
        xml_payload = '''<?xml version="1.0" encoding="utf-8"?>
<Incidents xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:com="http://nationalrail.co.uk/xml/common" xmlns="http://nationalrail.co.uk/xml/incident">
  <PtIncident>
    <CreationTime>2025-11-28T20:00:00Z</CreationTime>
    <ChangeHistory>
      <com:ChangedBy>NRE CMS Editor</com:ChangedBy>
      <com:LastChangedDate>2025-11-28T20:00:00Z</com:LastChangedDate>
    </ChangeHistory>
    <IncidentNumber>abc123</IncidentNumber>
    <ValidityPeriod>
      <com:StartTime>2025-11-29T00:00:00Z</com:StartTime>
      <com:EndTime>2025-11-29T06:00:00Z</com:EndTime>
    </ValidityPeriod>
    <Planned>true</Planned>
    <Summary><![CDATA[Engineering work]]></Summary>
    <Description><![CDATA[Track maintenance overnight.]]></Description>
    <Affects>
      <Operators>
        <AffectedOperator>
          <OperatorRef>NR</OperatorRef>
          <OperatorName>Network Rail</OperatorName>
        </AffectedOperator>
      </Operators>
      <RoutesAffected><![CDATA[<p>Between London and Manchester</p>]]></RoutesAffected>
    </Affects>
    <IncidentPriority>3</IncidentPriority>
  </PtIncident>
</Incidents>'''

        mock_resp = MagicMock()
        mock_resp.text = xml_payload
        mock_resp.headers = {'Content-Type': 'application/xml'}
        mock_resp.raise_for_status.return_value = None
        mock_get.return_value = mock_resp

        tools = train_tools.TrainTools()
        tools.disruptions_api_key = 'test-key'
        res = tools.get_station_messages()

        assert isinstance(res, train_tools.StationMessagesResponse)
        assert len(res.messages) == 1
        m = res.messages[0]
        assert m.id == 'abc123'
        assert m.category == 'planned'
        assert m.severity == '3'
        assert m.title == 'Engineering work'
        assert m.message == 'Track maintenance overnight.'
        assert m.start_time == '2025-11-29T00:00:00Z'
        assert m.end_time == '2025-11-29T06:00:00Z'
        assert m.last_updated == '2025-11-28T20:00:00Z'
        assert len(m.operators) == 1
        assert m.operators[0].ref == 'NR'
        assert m.operators[0].name == 'Network Rail'

    def test_get_station_messages_missing_api_key(self):
        # Ensure missing key returns a clear error
        tools = train_tools.TrainTools()
        tools.disruptions_api_key = None
        res = tools.get_station_messages()
        assert isinstance(res, train_tools.StationMessagesError)
        assert 'Missing API key' in res.error

    @patch('requests.get')
    def test_get_station_messages_http_error(self, mock_get):
        # Simulate HTTP error with status code
        mock_resp = MagicMock()
        mock_resp.raise_for_status.side_effect = requests.HTTPError(response=MagicMock(status_code=403))
        mock_get.return_value = mock_resp

        tools = train_tools.TrainTools()
        tools.disruptions_api_key = 'test-key'
        res = tools.get_station_messages()

        assert isinstance(res, train_tools.StationMessagesError)
        assert 'HTTP 403' in res.error
        assert 'Incidents feed request failed' in res.message

    @patch('requests.get')
    def test_get_station_messages_timeout(self, mock_get):
        mock_get.side_effect = requests.Timeout('request timed out')

        tools = train_tools.TrainTools()
        tools.disruptions_api_key = 'test-key'
        res = tools.get_station_messages()

        assert isinstance(res, train_tools.StationMessagesError)
        assert 'request timed out' in res.error
        assert 'Unable to fetch station messages' in res.message
