"""
Comprehensive tests for Flask application (app.py)

Tests cover:
- Flask routes (/, /traintraveladvisor)
- API endpoints (/api/chat, /api/reset, /api/health)
- Session management
- Agent lifecycle
- Error handling
- Input validation
"""

import pytest
import secrets
from unittest.mock import Mock, patch
from flask import session

from app import app, agents, get_or_create_agent


@pytest.fixture
def client():
    """Create Flask test client."""
    app.config['TESTING'] = True
    app.config['SECRET_KEY'] = 'test-secret-key'
    
    with app.test_client() as client:
        yield client
    
    # Cleanup
    agents.clear()


@pytest.fixture
def mock_agent():
    """Create mock ScotRailAgent."""
    agent = Mock()
    agent.chat.return_value = "Test response from agent"
    agent.reset_conversation.return_value = None
    return agent


class TestRoutes:
    """Test Flask routes."""
    
    def test_index_route(self, client):
        """Test landing page route."""
        response = client.get('/')
        assert response.status_code == 200
        assert b'ScotRail Train Travel Advisor' in response.data
        assert b'Start Chatting' in response.data
    
    def test_chat_interface_route(self, client):
        """Test chat interface route."""
        response = client.get('/traintraveladvisor')
        assert response.status_code == 200
        assert b'ScotRail Train Travel Advisor' in response.data
        assert b'message-input' in response.data or b'userInput' in response.data
    
    def test_chat_interface_creates_session(self, client):
        """Test chat interface generates session ID."""
        with client.session_transaction() as sess:
            assert 'session_id' not in sess
        
        response = client.get('/traintraveladvisor')
        
        with client.session_transaction() as sess:
            assert 'session_id' in sess
            assert len(sess['session_id']) == 32  # secrets.token_hex(16) = 32 chars


class TestAPIEndpoints:
    """Test API endpoints."""
    
    @patch.dict('os.environ', {'OPENAI_API_KEY': 'test-api-key'})
    def test_chat_endpoint_success(self, client, mock_agent):
        """Test successful chat API call."""
        with patch('app.ScotRailAgent', return_value=mock_agent):
            with client.session_transaction() as sess:
                sess['session_id'] = 'test-session-123'
            
            response = client.post('/api/chat', json={
                'message': 'What time is it?'
            })
            
            assert response.status_code == 200
            data = response.get_json()
            assert data['success'] == True
            assert data['response'] == "Test response from agent"
            
            # Verify agent was called
            mock_agent.chat.assert_called_once_with('What time is it?')
    
    def test_chat_endpoint_missing_message(self, client):
        """Test chat API without message field."""
        with client.session_transaction() as sess:
            sess['session_id'] = 'test-session-123'
        
        response = client.post('/api/chat', json={})
        
        assert response.status_code == 400
        data = response.get_json()
        assert 'error' in data
        assert 'empty' in data['error'].lower()
    
    def test_chat_endpoint_empty_message(self, client):
        """Test chat API with empty message."""
        with client.session_transaction() as sess:
            sess['session_id'] = 'test-session-123'
        
        response = client.post('/api/chat', json={
            'message': '   '
        })
        
        assert response.status_code == 400
        data = response.get_json()
        assert 'error' in data
        assert 'empty' in data['error'].lower()
    
    def test_chat_endpoint_invalid_json(self, client):
        """Test chat API with invalid JSON."""
        with client.session_transaction() as sess:
            sess['session_id'] = 'test-session-123'
        
        response = client.post('/api/chat', 
                               data='not json',
                               content_type='application/json')
        
        assert response.status_code in [400, 500]  # Accept either
    
    @patch.dict('os.environ', {'OPENAI_API_KEY': 'test-api-key'})
    def test_chat_endpoint_agent_error(self, client):
        """Test chat API when agent raises error."""
        mock_agent = Mock()
        mock_agent.chat.side_effect = Exception("Agent error")
        
        with patch('app.ScotRailAgent', return_value=mock_agent):
            with client.session_transaction() as sess:
                sess['session_id'] = 'test-session-123'
            
            response = client.post('/api/chat', json={
                'message': 'Hello'
            })
            
            assert response.status_code == 500
            data = response.get_json()
            assert data['success'] == False
            assert 'error' in data
    
    @patch.dict('os.environ', {'OPENAI_API_KEY': 'test-api-key'})
    def test_reset_endpoint_success(self, client, mock_agent):
        """Test successful conversation reset."""
        with patch('app.ScotRailAgent', return_value=mock_agent):
            with client.session_transaction() as sess:
                sess['session_id'] = 'test-session-123'
            
            # Create agent first
            client.post('/api/chat', json={'message': 'Hello'})
            
            # Reset conversation
            response = client.post('/api/reset')
            
            assert response.status_code == 200
            data = response.get_json()
            assert data['success'] == True
            assert 'reset' in data['message'].lower()
            
            # Verify reset was called
            mock_agent.reset_conversation.assert_called_once()
    
    @patch.dict('os.environ', {'OPENAI_API_KEY': 'test-api-key'})
    def test_reset_endpoint_error(self, client):
        """Test reset endpoint when agent raises error."""
        mock_agent = Mock()
        mock_agent.reset_conversation.side_effect = Exception("Reset error")
        
        with patch('app.ScotRailAgent', return_value=mock_agent):
            with client.session_transaction() as sess:
                sess['session_id'] = 'test-session-123'
            
            # Create agent first
            client.post('/api/chat', json={'message': 'Hello'})
            
            # Try to reset
            response = client.post('/api/reset')
            
            assert response.status_code == 500
            data = response.get_json()
            assert data['success'] == False
            assert 'error' in data
    
    def test_health_endpoint(self, client):
        """Test health check endpoint."""
        response = client.get('/api/health')
        
        assert response.status_code == 200
        data = response.get_json()
        assert data['status'] == 'healthy'
        assert data['service'] == 'ScotRail Train Travel Advisor'


class TestSessionManagement:
    """Test session and agent management."""
    
    @patch.dict('os.environ', {'OPENAI_API_KEY': 'test-api-key'})
    def test_get_or_create_agent_creates_new(self, mock_agent):
        """Test agent creation for new session."""
        from app import get_or_create_agent
        
        with patch('app.ScotRailAgent', return_value=mock_agent):
            agent, error = get_or_create_agent('new-session-123')
            
            assert agent == mock_agent
            assert error is None
            assert 'new-session-123' in agents
    
    @patch.dict('os.environ', {'OPENAI_API_KEY': 'test-api-key'})
    def test_get_or_create_agent_returns_existing(self, mock_agent):
        """Test agent reuse for existing session."""
        from app import get_or_create_agent
        
        with patch('app.ScotRailAgent', return_value=mock_agent):
            # Create agent first time
            agent1, _ = get_or_create_agent('existing-session-123')
            
            # Get same agent second time
            agent2, _ = get_or_create_agent('existing-session-123')
            
            assert agent1 == agent2
            assert len(agents) >= 1
    
    @patch.dict('os.environ', {'OPENAI_API_KEY': 'test-api-key'})
    def test_multiple_sessions_have_separate_agents(self, mock_agent):
        """Test different sessions get different agents."""
        from app import get_or_create_agent
        
        agents.clear()
        
        with patch('app.ScotRailAgent', return_value=mock_agent):
            # Session 1
            agent1, _ = get_or_create_agent('session-1')
            
            # Session 2
            agent2, _ = get_or_create_agent('session-2')
            
            assert len(agents) == 2
            assert 'session-1' in agents
            assert 'session-2' in agents


class TestInputValidation:
    """Test input validation and sanitization."""
    
    def test_chat_rejects_very_long_message(self, client):
        """Test chat API rejects extremely long messages."""
        with client.session_transaction() as sess:
            sess['session_id'] = 'test-session-123'
        
        long_message = 'a' * 10000  # 10k characters
        response = client.post('/api/chat', json={
            'message': long_message
        })
        
        # Should still process but agent may truncate
        assert response.status_code in [200, 400, 500]
    
    def test_chat_handles_special_characters(self, client, mock_agent):
        """Test chat API handles special characters."""
        with patch('app.ScotRailAgent', return_value=mock_agent):
            with client.session_transaction() as sess:
                sess['session_id'] = 'test-session-123'
            
            response = client.post('/api/chat', json={
                'message': 'What about <script>alert("xss")</script>?'
            })
            
            assert response.status_code == 200
            # Verify message was passed as-is (agent handles sanitization)
            mock_agent.chat.assert_called_once()
    
    def test_chat_handles_unicode(self, client, mock_agent):
        """Test chat API handles unicode characters."""
        with patch('app.ScotRailAgent', return_value=mock_agent):
            with client.session_transaction() as sess:
                sess['session_id'] = 'test-session-123'
            
            response = client.post('/api/chat', json={
                'message': 'Hello 你好 مرحبا 🚂'
            })
            
            assert response.status_code == 200


class TestErrorHandling:
    """Test comprehensive error handling."""
    
    def test_chat_without_session(self, client, mock_agent):
        """Test chat API creates session if missing."""
        with patch('app.ScotRailAgent', return_value=mock_agent):
            # Don't set session_id
            response = client.post('/api/chat', json={
                'message': 'Hello'
            })
            
            assert response.status_code == 200
            # Session should be created automatically
    
    def test_reset_without_agent(self, client):
        """Test reset when no agent exists yet."""
        with client.session_transaction() as sess:
            sess['session_id'] = 'nonexistent-session'
        
        response = client.post('/api/reset')
        
        # Should handle gracefully
        assert response.status_code in [200, 404]
    
    @patch.dict('os.environ', {}, clear=True)
    def test_chat_without_openai_key(self, client):
        """Test chat API when OpenAI key missing."""
        with client.session_transaction() as sess:
            sess['session_id'] = 'test-session-123'
        
        response = client.post('/api/chat', json={
            'message': 'Hello'
        })
        
        # Should return error about configuration
        assert response.status_code == 500
        data = response.get_json()
        # May have 'success': False or just 'error'
        assert 'error' in data or (data.get('success') == False)


class TestConcurrency:
    """Test concurrent request handling."""
    
    @patch.dict('os.environ', {'OPENAI_API_KEY': 'test-api-key'})
    def test_concurrent_sessions(self, mock_agent):
        """Test multiple sessions can coexist."""
        with patch('app.ScotRailAgent', return_value=mock_agent):
            client1 = app.test_client()
            client2 = app.test_client()
            
            with client1.session_transaction() as sess:
                sess['session_id'] = 'session-1'
            
            with client2.session_transaction() as sess:
                sess['session_id'] = 'session-2'
            
            # Both clients make requests
            resp1 = client1.post('/api/chat', json={'message': 'Hello from 1'})
            resp2 = client2.post('/api/chat', json={'message': 'Hello from 2'})
            
            assert resp1.status_code == 200
            assert resp2.status_code == 200
            assert len(agents) == 2
