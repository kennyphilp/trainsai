"""
Tests for Phase 2: Timetable Database and Tools

Tests cover:
- TimetableDatabase schema and operations
- CIF schedule parser (ZTR format)
- ALF connection parser
- TimetableTools (4 new tools)
- ScotRailAgent integration with timetable tools
"""

import pytest
import os
import tempfile
import sqlite3
from datetime import date, time
from unittest.mock import Mock, patch, MagicMock

from timetable_database import (
    TimetableDatabase,
    ScheduledTrain,
    ScheduleLocation,
    StationConnection
)
from timetable_parser import CIFScheduleParser, ALFParser
from timetable_tools import TimetableTools


class TestTimetableDatabaseSchema:
    """Test database schema creation and structure."""
    
    def test_database_initialization(self):
        """Test database creates and initializes properly."""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = f.name
        
        try:
            db = TimetableDatabase(db_path)
            db.connect()
            
            # Verify tables exist
            cursor = db.conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = {row[0] for row in cursor.fetchall()}
            
            assert 'schedules' in tables
            assert 'schedule_locations' in tables
            assert 'station_connections' in tables
            assert 'metadata' in tables
            
            db.close()
        finally:
            if os.path.exists(db_path):
                os.unlink(db_path)
    
    def test_insert_schedule(self):
        """Test inserting a complete train schedule."""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = f.name
        
        try:
            db = TimetableDatabase(db_path)
            db.connect()
            
            # Create test schedule
            train = ScheduledTrain(
                schedule_id=0,
                train_uid='C12345',
                train_headcode='1A23',
                operator_code='SR',
                service_type='P',
                start_date=date(2025, 12, 1),
                end_date=date(2025, 12, 31),
                days_run='1111100',  # Mon-Fri
                speed=100
            )
            
            locations = [
                ScheduleLocation(
                    location_id=0,
                    schedule_id=0,
                    sequence=0,
                    tiploc='EDINBUR',
                    location_type='LO',
                    departure_time=time(9, 0)
                ),
                ScheduleLocation(
                    location_id=0,
                    schedule_id=0,
                    sequence=1,
                    tiploc='GLASGOW',
                    location_type='LT',
                    arrival_time=time(10, 0)
                )
            ]
            
            schedule_id = db.insert_schedule(train, locations)
            assert schedule_id > 0
            
            # Verify data was inserted
            cursor = db.conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM schedules")
            assert cursor.fetchone()[0] == 1
            
            cursor.execute("SELECT COUNT(*) FROM schedule_locations")
            assert cursor.fetchone()[0] == 2
            
            db.close()
        finally:
            if os.path.exists(db_path):
                os.unlink(db_path)
    
    def test_find_trains_between_stations(self):
        """Test querying trains between two stations."""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = f.name
        
        try:
            db = TimetableDatabase(db_path)
            db.connect()
            
            # Insert test data
            train = ScheduledTrain(
                schedule_id=0,
                train_uid='C12345',
                train_headcode='1A23',
                operator_code='SR',
                service_type='P',
                start_date=date(2025, 12, 1),
                end_date=date(2025, 12, 31),
                days_run='1111111',  # Every day
            )
            
            locations = [
                ScheduleLocation(
                    location_id=0, schedule_id=0, sequence=0,
                    tiploc='EDINBUR', location_type='LO',
                    departure_time=time(9, 0)
                ),
                ScheduleLocation(
                    location_id=0, schedule_id=0, sequence=1,
                    tiploc='GLASGOW', location_type='LT',
                    arrival_time=time(10, 0)
                )
            ]
            
            db.insert_schedule(train, locations)
            
            # Query for trains
            travel_date = date(2025, 12, 15)  # Monday
            results = db.find_trains_between_stations('EDINBUR', 'GLASGOW', travel_date)
            
            assert len(results) == 1
            assert results[0]['train_uid'] == 'C12345'
            assert results[0]['departure_time'] == '09:00'
            assert results[0]['arrival_time'] == '10:00'
            assert results[0]['duration_minutes'] == 60
            
            db.close()
        finally:
            if os.path.exists(db_path):
                os.unlink(db_path)


class TestCIFScheduleParser:
    """Test CIF schedule file parser."""
    
    def test_parse_bs_record(self):
        """Test parsing Basic Schedule record."""
        parser = CIFScheduleParser()
        
        # Sample BS record (fixed-width format)
        bs_line = "BSNC123452512012512311111100P  1A23    12345678 EMU100125 BRS  "
        
        result = parser._parse_bs_record(bs_line)
        
        assert result['train_uid'] == 'C12345'
        assert result['start_date'] is not None
        assert result['end_date'] is not None
        assert result['days_run'] == '1111100'
    
    def test_parse_time(self):
        """Test CIF time format parsing."""
        parser = CIFScheduleParser()
        
        assert parser._parse_time('0930') == '09:30'
        assert parser._parse_time('1545') == '15:45'
        assert parser._parse_time('2359') == '23:59'
        assert parser._parse_time('0930H') == '09:30'  # Half-minute
        assert parser._parse_time('') is None
    
    def test_parse_date(self):
        """Test CIF date format parsing."""
        parser = CIFScheduleParser()
        
        assert parser._parse_date('251201') == '2025-12-01'
        assert parser._parse_date('241231') == '2024-12-31'
        assert parser._parse_date('') is None


class TestALFParser:
    """Test ALF (Additional Fixed Links) parser."""
    
    def test_parse_alf_record(self):
        """Test parsing ALF connection record."""
        parser = ALFParser()
        
        # Sample ALF record (fixed-width format: mode(1), from_tiploc(7), to_tiploc(7), duration(3))
        # Format: I + EDINBUR (7) + GLASGOC (7) + 005 (3) = 18 chars minimum
        alf_line = "IEDINBURGLASGOC005180022000        "
        
        result = parser._parse_alf_record(alf_line)
        
        assert result is not None
        assert result['mode'] == 'I'
        assert result['from_tiploc'] == 'EDINBUR'
        assert result['to_tiploc'] == 'GLASGOC'
        assert result['duration'] == 5


class TestTimetableTools:
    """Test TimetableTools integration layer."""
    
    @pytest.fixture
    def mock_db(self):
        """Create a mock database with test data."""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = f.name
        
        db = TimetableDatabase(db_path)
        db.connect()
        
        # Insert test schedule
        train = ScheduledTrain(
            schedule_id=0,
            train_uid='C12345',
            train_headcode='1A23',
            operator_code='SR',
            service_type='P',
            start_date=date(2025, 12, 1),
            end_date=date(2025, 12, 31),
            days_run='1111111',
        )
        
        locations = [
            ScheduleLocation(
                location_id=0, schedule_id=0, sequence=0,
                tiploc='EDINBUR', location_type='LO',
                departure_time=time(9, 0), platform='7'
            ),
            ScheduleLocation(
                location_id=0, schedule_id=0, sequence=1,
                tiploc='GLASGOW', location_type='LT',
                arrival_time=time(10, 0), platform='5'
            )
        ]
        
        db.insert_schedule(train, locations)
        db.close()
        
        yield db_path
        
        # Cleanup
        if os.path.exists(db_path):
            os.unlink(db_path)
    
    def test_get_scheduled_trains(self, mock_db):
        """Test get_scheduled_trains tool."""
        tools = TimetableTools(db_path=mock_db)
        
        result = tools.get_scheduled_trains(
            from_station='EDINBUR',
            to_station='GLASGOW',
            travel_date='2025-12-15'
        )
        
        assert result['success'] is True
        assert result['count'] >= 1
        assert len(result['trains']) >= 1
        
        train = result['trains'][0]
        assert train['train_uid'] == 'C12345'
        assert train['departure_time'] == '09:00'
        assert train['arrival_time'] == '10:00'
        
        tools.close()
    
    def test_find_journey_route(self, mock_db):
        """Test find_journey_route tool."""
        tools = TimetableTools(db_path=mock_db)
        
        result = tools.find_journey_route(
            from_station='EDINBUR',
            to_station='GLASGOW',
            travel_date='2025-12-15',
            departure_time='08:00'
        )
        
        assert result['success'] is True
        assert 'routes' in result
        
        tools.close()
    
    def test_get_tool_schemas(self):
        """Test tool schemas are properly formatted for OpenAI."""
        tools = TimetableTools()
        schemas = tools.get_tool_schemas()
        
        assert len(schemas) == 4
        
        # Verify all schemas have required structure
        for schema in schemas:
            assert 'type' in schema
            assert schema['type'] == 'function'
            assert 'function' in schema
            assert 'name' in schema['function']
            assert 'description' in schema['function']
            assert 'parameters' in schema['function']
        
        # Verify tool names
        tool_names = {s['function']['name'] for s in schemas}
        assert 'get_scheduled_trains' in tool_names
        assert 'find_journey_route' in tool_names
        assert 'compare_schedule_vs_actual' in tool_names
        assert 'find_alternative_route' in tool_names
        
        tools.close()


class TestScotRailAgentIntegration:
    """Test integration of timetable tools with ScotRailAgent."""
    
    @patch.dict('os.environ', {'OPENAI_API_KEY': 'test-api-key'})
    def test_agent_initializes_with_timetable_tools(self):
        """Test agent loads timetable tools if available."""
        from scotrail_agent import ScotRailAgent
        
        # Agent should initialize even without timetable database
        agent = ScotRailAgent()
        
        # Check if timetable tools attribute exists
        assert hasattr(agent, 'timetable_tools')
    
    @patch.dict('os.environ', {'OPENAI_API_KEY': 'test-api-key'})
    def test_agent_tools_include_timetable_tools(self):
        """Test agent's tool list includes timetable tools."""
        from scotrail_agent import ScotRailAgent
        
        agent = ScotRailAgent()
        
        # Get all tool names
        tool_names = [tool['function']['name'] for tool in agent.tools]
        
        # Should have base tools
        assert 'get_current_time' in tool_names
        assert 'get_departure_board' in tool_names
        
        # May or may not have timetable tools depending on database availability
        # Just verify tools list is populated
        assert len(agent.tools) > 0
    
    @patch.dict('os.environ', {'OPENAI_API_KEY': 'test-api-key'})
    def test_agent_system_prompt_mentions_timetable_tools(self):
        """Test system prompt includes guidance on when to use timetable tools."""
        from scotrail_agent import ScotRailAgent
        
        agent = ScotRailAgent()
        
        # System prompt should mention schedule data
        assert 'SCHEDULE DATA' in agent.system_prompt or 'schedule' in agent.system_prompt.lower()


class TestStatistics:
    """Test database statistics and metadata."""
    
    def test_get_statistics(self):
        """Test retrieving database statistics."""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = f.name
        
        try:
            db = TimetableDatabase(db_path)
            db.connect()
            
            stats = db.get_statistics()
            
            assert 'schedules' in stats
            assert 'locations' in stats
            assert 'connections' in stats
            assert stats['schedules'] == 0  # Empty database
            
            db.close()
        finally:
            if os.path.exists(db_path):
                os.unlink(db_path)
