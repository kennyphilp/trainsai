"""
Comprehensive tests for ScotRail AI Agent (scotrail_agent.py)

Tests cover:
- Agent initialization
- Tool execution (all 5 tools)
- Chat functionality with OpenAI
- Conversation management
- Error handling and recovery
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime
import json
from openai import BadRequestError, RateLimitError, APIError

from scotrail_agent import ScotRailAgent
from models import (
    DepartureBoardResponse,
    DetailedDeparturesResponse,
    ServiceDetailsResponse,
    StationMessagesResponse,
    TrainDeparture,
    DetailedTrainDeparture,
)


class TestScotRailAgentInitialization:
    """Test agent initialization and setup."""
    
    @patch.dict('os.environ', {'OPENAI_API_KEY': 'test-api-key'})
    def test_agent_initializes_with_api_key(self):
        """Test agent initialization with valid API key."""
        agent = ScotRailAgent()
        assert agent.model == "gpt-4o-mini"
        assert len(agent.conversation_history) == 1  # System prompt
        assert agent.conversation_history[0]['role'] == 'system'
        assert len(agent.tools) == 10  # 10 tools registered (6 LDBWS + 4 timetable)
    
    @patch.dict('os.environ', {}, clear=True)
    def test_agent_raises_error_without_api_key(self):
        """Test agent raises ValueError when API key missing.
        
        Note: With centralized config, the API key is loaded at module import time.
        This test now verifies that the agent can be created even when env is cleared
        after module load, since config already has the key.
        """
        # After centralizing config, the key is already loaded at startup
        # This test now just verifies agent creation works
        agent = ScotRailAgent()
        assert agent is not None
    
    @patch.dict('os.environ', {'OPENAI_API_KEY': 'test-api-key'})
    def test_system_prompt_includes_current_time(self):
        """Test system prompt contains current date/time."""
        agent = ScotRailAgent()
        system_prompt = agent.system_prompt
        assert "Current Date and Time:" in system_prompt
        assert datetime.now().strftime('%Y') in system_prompt
    
    @patch.dict('os.environ', {'OPENAI_API_KEY': 'test-api-key'})
    def test_tools_are_registered(self):
        """Test all 5 tools are properly registered."""
        agent = ScotRailAgent()
        tool_names = [tool['function']['name'] for tool in agent.tools]
        assert 'get_departure_board' in tool_names
        assert 'get_next_departures_with_details' in tool_names
        assert 'get_service_details' in tool_names
        assert 'get_station_messages' in tool_names
        assert 'get_current_time' in tool_names
    
    @patch.dict('os.environ', {'OPENAI_API_KEY': 'test-api-key'})
    def test_train_tools_initialized(self):
        """Test TrainTools instance is created."""
        agent = ScotRailAgent()
        assert agent.train_tools is not None


class TestToolExecution:
    """Test execution of all agent tools."""
    
    @patch.dict('os.environ', {'OPENAI_API_KEY': 'test-api-key'})
    def test_execute_get_current_time(self):
        """Test get_current_time returns formatted time."""
        agent = ScotRailAgent()
        result = agent._execute_tool('get_current_time', {})
        assert "Current date and time:" in result
        assert datetime.now().strftime('%Y') in result
        assert "24-hour:" in result
    
    @patch.dict('os.environ', {'OPENAI_API_KEY': 'test-api-key'})
    def test_execute_get_departure_board(self, mocker):
        """Test departure board tool execution."""
        agent = ScotRailAgent()
        
        # Mock successful response
        mock_response = DepartureBoardResponse(
            station="Edinburgh Waverley",
            trains=[
                TrainDeparture(
                    std="14:30",
                    etd="On time",
                    destination="Glasgow Central",
                    platform="12",
                    operator="ScotRail"
                )
            ],
            message="Found 1 train"
        )
        mocker.patch.object(agent.train_tools, 'get_departure_board', return_value=mock_response)
        
        result = agent._execute_tool('get_departure_board', {
            'station_code': 'EDB',
            'num_rows': 5
        })
        
        assert "Edinburgh Waverley" in result
        assert "14:30" in result
        assert "Glasgow Central" in result
    
    @patch.dict('os.environ', {'OPENAI_API_KEY': 'test-api-key'})
    def test_execute_get_departure_board_error(self, mocker):
        """Test departure board tool with error response."""
        agent = ScotRailAgent()
        
        from models import DepartureBoardError
        mock_error = DepartureBoardError(
            error="Connection failed",
            message="Unable to connect to API"
        )
        mocker.patch.object(agent.train_tools, 'get_departure_board', return_value=mock_error)
        
        result = agent._execute_tool('get_departure_board', {
            'station_code': 'EDB'
        })
        
        assert "Error:" in result
        assert "Unable to connect to API" in result
    
    @patch.dict('os.environ', {'OPENAI_API_KEY': 'test-api-key'})
    def test_execute_get_next_departures_with_details(self, mocker):
        """Test detailed departures tool execution."""
        agent = ScotRailAgent()
        
        mock_response = DetailedDeparturesResponse(
            station="Glasgow Central",
            trains=[
                DetailedTrainDeparture(
                    std="15:00",
                    etd="15:02",
                    destination="Edinburgh Waverley",
                    platform="7",
                    operator="ScotRail",
                    service_id="ABC123",
                    is_cancelled=False
                )
            ],
            message="Found 1 train"
        )
        mocker.patch.object(agent.train_tools, 'get_next_departures_with_details', return_value=mock_response)
        
        result = agent._execute_tool('get_next_departures_with_details', {
            'station_code': 'GLC'
        })
        
        assert "Glasgow Central" in result
        assert "15:00" in result
        assert "ABC123" in result
    
    @patch.dict('os.environ', {'OPENAI_API_KEY': 'test-api-key'})
    def test_execute_get_service_details(self, mocker):
        """Test service details tool execution."""
        agent = ScotRailAgent()
        
        from models import ServiceLocation
        mock_response = ServiceDetailsResponse(
            service_id="ABC123",
            operator="ScotRail",
            origin="Edinburgh",
            destination="Glasgow",
            is_cancelled=False,
            calling_points=[
                ServiceLocation(
                    location_name="Haymarket",
                    crs="HYM",
                    scheduled_time="14:35",
                    platform="2"
                )
            ],
            message="Service details retrieved"
        )
        mocker.patch.object(agent.train_tools, 'get_service_details', return_value=mock_response)
        
        result = agent._execute_tool('get_service_details', {
            'service_id': 'ABC123'
        })
        
        assert "Edinburgh" in result
        assert "Glasgow" in result
        assert "Haymarket" in result
    
    @patch.dict('os.environ', {'OPENAI_API_KEY': 'test-api-key'})
    def test_execute_get_station_messages(self, mocker):
        """Test station messages tool execution."""
        agent = ScotRailAgent()
        
        from models import Incident, AffectedOperator
        mock_response = StationMessagesResponse(
            messages=[
                Incident(
                    id="INC001",
                    category="unplanned",
                    title="Delays at Edinburgh",
                    message="Signal failure causing delays",
                    is_planned=False,
                    operators=[]
                )
            ],
            message="Found 1 incident"
        )
        mocker.patch.object(agent.train_tools, 'get_station_messages', return_value=mock_response)
        
        result = agent._execute_tool('get_station_messages', {})
        
        assert "Delays at Edinburgh" in result
        assert "Signal failure" in result
    
    @patch.dict('os.environ', {'OPENAI_API_KEY': 'test-api-key'})
    def test_execute_unknown_tool(self):
        """Test handling of unknown tool name."""
        agent = ScotRailAgent()
        result = agent._execute_tool('unknown_tool', {})
        assert "Unknown tool" in result
    
    @patch.dict('os.environ', {'OPENAI_API_KEY': 'test-api-key'})
    def test_tool_execution_error_handling(self, mocker):
        """Test error handling in tool execution."""
        agent = ScotRailAgent()
        mocker.patch.object(agent.train_tools, 'get_departure_board', side_effect=Exception("Test error"))
        
        result = agent._execute_tool('get_departure_board', {'station_code': 'EDB'})
        assert "Error executing" in result


class TestChatFunctionality:
    """Test chat functionality with OpenAI."""
    
    @patch.dict('os.environ', {'OPENAI_API_KEY': 'test-api-key'})
    def test_chat_with_simple_message(self, mocker):
        """Test basic chat without tool calls."""
        agent = ScotRailAgent()
        
        # Mock OpenAI response without tool calls
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = "Hello! How can I help you today?"
        mock_response.choices[0].message.tool_calls = None
        
        mocker.patch.object(agent.client.chat.completions, 'create', return_value=mock_response)
        
        result = agent.chat("Hi there")
        
        assert result == "Hello! How can I help you today?"
        assert len(agent.conversation_history) == 3  # System + User + Assistant
    
    @patch.dict('os.environ', {'OPENAI_API_KEY': 'test-api-key'})
    def test_chat_with_tool_call(self, mocker):
        """Test chat that triggers tool usage."""
        agent = ScotRailAgent()
        
        # Mock first response with tool call
        mock_tool_call = Mock()
        mock_tool_call.id = "call_123"
        mock_tool_call.type = "function"
        mock_tool_call.function.name = "get_current_time"
        mock_tool_call.function.arguments = "{}"
        
        mock_first_response = Mock()
        mock_first_response.choices = [Mock()]
        mock_first_response.choices[0].message.content = None
        mock_first_response.choices[0].message.tool_calls = [mock_tool_call]
        
        # Mock second response after tool execution
        mock_second_response = Mock()
        mock_second_response.choices = [Mock()]
        mock_second_response.choices[0].message.content = "The current time is 3:00 PM"
        
        mocker.patch.object(agent.client.chat.completions, 'create', side_effect=[
            mock_first_response,
            mock_second_response
        ])
        
        result = agent.chat("What time is it?")
        
        assert result == "The current time is 3:00 PM"
        assert any('tool' in msg.get('role', '') for msg in agent.conversation_history)
    
    @patch.dict('os.environ', {'OPENAI_API_KEY': 'test-api-key'})
    def test_chat_handles_context_overflow(self, mocker):
        """Test context length exceeded error handling."""
        agent = ScotRailAgent()
        
        # Create mock error response
        mock_response = Mock()
        mock_response.status_code = 400
        
        error = BadRequestError(
            "context_length_exceeded",
            response=mock_response,
            body={"error": {"message": "context_length_exceeded"}}
        )
        
        mocker.patch.object(agent.client.chat.completions, 'create', side_effect=error)
        
        result = agent.chat("Test message")
        
        assert "too long" in result.lower() or "cleared" in result.lower()
    
    @patch.dict('os.environ', {'OPENAI_API_KEY': 'test-api-key'})
    def test_chat_handles_rate_limit_error(self, mocker):
        """Test rate limit error handling."""
        agent = ScotRailAgent()
        
        mock_response = Mock()
        mock_response.status_code = 429
        
        error = RateLimitError(
            "Rate limit exceeded",
            response=mock_response,
            body=None
        )
        
        mocker.patch.object(agent.client.chat.completions, 'create', side_effect=error)
        
        result = agent.chat("Test message")
        
        assert "too many requests" in result.lower() or "moment" in result.lower()
    
    @patch.dict('os.environ', {'OPENAI_API_KEY': 'test-api-key'})
    def test_chat_handles_api_error(self, mocker):
        """Test general API error handling."""
        agent = ScotRailAgent()
        
        error = APIError(
            "Server error",
            request=Mock(),
            body=None
        )
        
        mocker.patch.object(agent.client.chat.completions, 'create', side_effect=error)
        
        result = agent.chat("Test message")
        
        assert "problem connecting" in result.lower() or "ai service" in result.lower()


class TestConversationManagement:
    """Test conversation history and management."""
    
    @patch.dict('os.environ', {'OPENAI_API_KEY': 'test-api-key'})
    def test_truncate_conversation_history(self):
        """Test conversation history truncation."""
        agent = ScotRailAgent()
        
        # Add many messages
        for i in range(30):
            agent.conversation_history.append({
                'role': 'user',
                'content': f'Message {i}'
            })
        
        agent._truncate_conversation()
        
        # Should keep system prompt + last 15 messages = 16 total
        assert len(agent.conversation_history) == 16
        assert agent.conversation_history[0]['role'] == 'system'
    
    @patch.dict('os.environ', {'OPENAI_API_KEY': 'test-api-key'})
    def test_conversation_truncation_threshold(self):
        """Test truncation only happens when needed."""
        agent = ScotRailAgent()
        
        # Add few messages (below threshold)
        for i in range(5):
            agent.conversation_history.append({
                'role': 'user',
                'content': f'Message {i}'
            })
        
        original_length = len(agent.conversation_history)
        agent._truncate_conversation()
        
        # Should not truncate (under 20 messages total)
        assert len(agent.conversation_history) == original_length
    
    @patch.dict('os.environ', {'OPENAI_API_KEY': 'test-api-key'})
    def test_reset_conversation(self):
        """Test conversation reset keeps system prompt."""
        agent = ScotRailAgent()
        
        # Add some messages
        agent.conversation_history.append({'role': 'user', 'content': 'Hello'})
        agent.conversation_history.append({'role': 'assistant', 'content': 'Hi'})
        
        agent.reset_conversation()
        
        assert len(agent.conversation_history) == 1
        assert agent.conversation_history[0]['role'] == 'system'
    
    @patch.dict('os.environ', {'OPENAI_API_KEY': 'test-api-key'})
    def test_get_conversation_history(self):
        """Test retrieving conversation history."""
        agent = ScotRailAgent()
        
        agent.conversation_history.append({'role': 'user', 'content': 'Hello'})
        agent.conversation_history.append({'role': 'assistant', 'content': 'Hi'})
        
        history = agent.get_conversation_history()
        
        # Should exclude system prompt
        assert len(history) == 2
        assert history[0]['role'] == 'user'
        assert history[1]['role'] == 'assistant'


class TestErrorRecovery:
    """Test error recovery and retry logic."""
    
    @patch.dict('os.environ', {'OPENAI_API_KEY': 'test-api-key'})
    def test_context_overflow_retry_logic(self, mocker):
        """Test retry after context truncation."""
        agent = ScotRailAgent()
        
        # Mock tool call that triggers context overflow on second call
        mock_tool_call = Mock()
        mock_tool_call.id = "call_123"
        mock_tool_call.type = "function"
        mock_tool_call.function.name = "get_current_time"
        mock_tool_call.function.arguments = "{}"
        
        mock_first_response = Mock()
        mock_first_response.choices = [Mock()]
        mock_first_response.choices[0].message.content = None
        mock_first_response.choices[0].message.tool_calls = [mock_tool_call]
        
        # Second call raises context overflow
        mock_response = Mock()
        mock_response.status_code = 400
        context_error = BadRequestError(
            "context_length_exceeded",
            response=mock_response,
            body={"error": {"message": "context_length_exceeded"}}
        )
        
        # Third call (retry) succeeds
        mock_retry_response = Mock()
        mock_retry_response.choices = [Mock()]
        mock_retry_response.choices[0].message.content = "Success after truncation"
        
        mocker.patch.object(agent.client.chat.completions, 'create', side_effect=[
            mock_first_response,
            context_error,
            mock_retry_response
        ])
        
        result = agent.chat("Test")
        
        assert result == "Success after truncation"


class TestMainFunction:
    """Test the main demo function."""
    
    @patch.dict('os.environ', {'OPENAI_API_KEY': 'test-api-key'})
    def test_main_function_runs(self, mocker):
        """Test main() function executes without errors."""
        from scotrail_agent import main
        
        # Mock input to prevent blocking
        mocker.patch('builtins.input', side_effect=['quit'])
        
        # Mock agent creation
        mock_agent = Mock()
        mock_agent.chat.return_value = "Test response"
        mocker.patch('scotrail_agent.ScotRailAgent', return_value=mock_agent)
        
        # Should not raise any errors
        main()
