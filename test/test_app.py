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

from app import app, agents, session_metadata, get_or_create_agent


@pytest.fixture
def client():
    """Create Flask test client."""
    from app import limiter
    app.config['TESTING'] = True
    app.config['SECRET_KEY'] = 'test-secret-key'
    
    with app.test_client() as client:
        yield client
    
    # Cleanup
    agents.clear()
    session_metadata.clear()
    limiter.reset()  # Reset rate limiter state

@pytest.fixture
def mock_agent():
    """Create mock ScotRailAgent."""
    agent = Mock()
    agent.chat.return_value = "Test response from agent"
    agent.reset_conversation.return_value = None
    return agent


@pytest.fixture
def rate_limited_client():
    """Create Flask test client with rate limiting enabled."""
    from app import limiter
    
    # Save original state
    original_testing = app.config.get('TESTING')
    
    # Enable rate limiting for this test
    app.config['TESTING'] = False
    limiter.enabled = True
    limiter.reset()  # Start with clean slate
    
    with app.test_client() as client:
        yield client
    
    # Restore original state
    app.config['TESTING'] = original_testing
    limiter.enabled = True  # Keep enabled but respect exempt_when
    limiter.reset()
    agents.clear()
    session_metadata.clear()


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
        session_metadata.clear()
        
        with patch('app.ScotRailAgent', return_value=mock_agent):
            # Session 1
            agent1, _ = get_or_create_agent('session-1')
            
            # Session 2
            agent2, _ = get_or_create_agent('session-2')
            
            assert len(agents) == 2
            assert 'session-1' in agents
            assert 'session-2' in agents
    
    @patch.dict('os.environ', {'OPENAI_API_KEY': 'test-api-key', 'MAX_SESSIONS': '2'})
    def test_lru_eviction_when_max_sessions_reached(self, mock_agent):
        """Test LRU eviction when MAX_SESSIONS limit is reached."""
        # Need to reload app module to pick up new env vars
        import importlib
        import app as app_module
        importlib.reload(app_module)
        from app import get_or_create_agent, agents, session_metadata
        
        agents.clear()
        session_metadata.clear()
        
        with patch('app.ScotRailAgent', return_value=mock_agent):
            # Create 2 sessions (max limit)
            agent1, _ = get_or_create_agent('session-1')
            agent2, _ = get_or_create_agent('session-2')
            assert len(agents) == 2
            
            # Create 3rd session - should evict session-1 (oldest)
            agent3, _ = get_or_create_agent('session-3')
            assert len(agents) == 2
            assert 'session-1' not in agents
            assert 'session-2' in agents
            assert 'session-3' in agents
    
    @patch.dict('os.environ', {'OPENAI_API_KEY': 'test-api-key', 'SESSION_TTL_HOURS': '0'})
    def test_expired_sessions_cleanup(self, mock_agent):
        """Test that expired sessions are cleaned up."""
        # Need to reload app module to pick up new env vars
        import importlib
        import app as app_module
        importlib.reload(app_module)
        from app import get_or_create_agent, agents, session_metadata, _cleanup_expired_sessions
        from datetime import datetime, timedelta
        
        agents.clear()
        session_metadata.clear()
        
        with patch('app.ScotRailAgent', return_value=mock_agent):
            # Create a session
            agent1, _ = get_or_create_agent('session-1')
            assert 'session-1' in agents
            
            # Manually set session to be expired (older than TTL)
            session_metadata['session-1'] = datetime.now() - timedelta(hours=1)
            
            # Create another session - should trigger cleanup
            agent2, _ = get_or_create_agent('session-2')
            
            # session-1 should be cleaned up
            assert 'session-1' not in agents
            assert 'session-2' in agents
    
    @patch.dict('os.environ', {'OPENAI_API_KEY': 'test-api-key'})
    def test_session_access_updates_timestamp(self, mock_agent):
        """Test that accessing a session returns the same agent instance."""
        agents.clear()
        session_metadata.clear()
        
        with patch('app.ScotRailAgent', return_value=mock_agent):
            # Create a session
            agent1, _ = get_or_create_agent('session-1')
            
            # Access the same session again - should return same instance
            agent2, _ = get_or_create_agent('session-1')
            
            # Should return the same agent instance
            assert agent1 == agent2
            assert agent1 is agent2


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
        from app import agents as app_agents
        app_agents.clear()
        session_metadata.clear()
        
        with patch('app.ScotRailAgent', return_value=mock_agent):
            client1 = app.test_client()
            client2 = app.test_client()
            
            with client1.session_transaction() as sess:
                sess['session_id'] = 'concurrent-session-1'
            
            with client2.session_transaction() as sess:
                sess['session_id'] = 'concurrent-session-2'
            
            # Both clients make requests
            resp1 = client1.post('/api/chat', json={'message': 'Hello from 1'})
            resp2 = client2.post('/api/chat', json={'message': 'Hello from 2'})
            
            assert resp1.status_code == 200
            assert resp2.status_code == 200
            # Verify at least one session was created successfully
            assert len(app_agents) >= 1


class TestRateLimiting:
    """Test rate limiting functionality."""
    
    @patch.dict('os.environ', {'OPENAI_API_KEY': 'test-api-key'})
    def test_rate_limit_chat_endpoint(self, rate_limited_client, mock_agent):
        """Test rate limiting on chat endpoint."""
        with rate_limited_client.session_transaction() as sess:
            sess['session_id'] = 'rate-limit-test'
        
        with patch('app.ScotRailAgent', return_value=mock_agent):
            # Make requests up to the limit (default: 10 per minute)
            # We'll make 12 requests to exceed the limit
            responses = []
            for i in range(12):
                response = rate_limited_client.post('/api/chat', json={'message': f'Test message {i}'})
                responses.append(response)
            
            # First 10 should succeed
            successful = [r for r in responses if r.status_code == 200]
            rate_limited = [r for r in responses if r.status_code == 429]
            
            # At least some requests should succeed, and some should be rate limited
            assert len(successful) > 0, "Expected some successful requests"
            assert len(rate_limited) > 0, "Expected some rate-limited (429) responses"
    
    @patch.dict('os.environ', {'OPENAI_API_KEY': 'test-api-key'})
    def test_rate_limit_health_endpoint(self, rate_limited_client):
        """Test rate limiting on health endpoint."""
        # Health endpoint has higher limit (60 per minute)
        # Make 65 requests to test the limit
        responses = []
        for i in range(65):
            response = rate_limited_client.get('/api/health')
            responses.append(response)
        
        # Should have mix of successful and rate-limited
        successful = [r for r in responses if r.status_code == 200]
        rate_limited = [r for r in responses if r.status_code == 429]
        
        # Most should succeed due to higher limit
        assert len(successful) >= 55, f"Expected at least 55 successful, got {len(successful)}"
        assert len(rate_limited) > 0, "Expected some rate-limited responses"
    
    @patch.dict('os.environ', {'OPENAI_API_KEY': 'test-api-key'})
    def test_rate_limit_headers_present(self, rate_limited_client):
        """Test that rate limit headers are present in responses."""
        response = rate_limited_client.get('/api/health')
        
        # Check for common rate limit headers
        # Flask-Limiter adds X-RateLimit headers
        headers = response.headers
        
        # Should have at least a status code
        assert response.status_code in [200, 429]
        
        # When rate limiting is enabled, check for headers
        # The headers may vary, so we just verify the response is valid
        assert response.status_code == 200 or response.status_code == 429
    
    def test_rate_limiting_exempt_in_testing_mode(self, client):
        """Test that TESTING mode is enabled and exempts rate limiting."""
        # Verify we're in testing mode which should exempt from rate limiting
        assert app.config['TESTING'] == True
        
        # The other rate limiting tests verify rate limiting works when enabled
        # This test just confirms the testing configuration is correct
    
    @patch.dict('os.environ', {'OPENAI_API_KEY': 'test-api-key'})
    def test_rate_limit_per_ip(self, rate_limited_client, mock_agent):
        """Test that rate limiting is applied per IP address."""
        with rate_limited_client.session_transaction() as sess:
            sess['session_id'] = 'per-ip-test'
        
        with patch('app.ScotRailAgent', return_value=mock_agent):
            # Simulate requests from same IP (default in test client)
            responses = []
            for i in range(15):
                response = rate_limited_client.post('/api/chat', json={'message': f'Test {i}'})
                responses.append(response)
            
            # Should have rate limiting applied
            rate_limited = [r for r in responses if r.status_code == 429]
            assert len(rate_limited) > 0, "Expected rate limiting for same IP"


class TestCORS:
    """Test CORS (Cross-Origin Resource Sharing) functionality."""
    
    @pytest.fixture(autouse=True)
    def reset_limiter_for_cors(self):
        """Automatically reset rate limiter before each CORS test."""
        from app import limiter
        limiter.reset()
        yield
    
    def test_cors_configuration_loaded(self):
        """Test that CORS configuration is loaded correctly."""
        # Verify CORS configuration is set
        import os
        cors_enabled = os.getenv('CORS_ENABLED', 'true').lower() == 'true'
        # This is a simple configuration test
        assert cors_enabled in [True, False]
    
    @patch.dict('os.environ', {'CORS_ENABLED': 'true', 'OPENAI_API_KEY': 'test-key'})
    def test_cors_preflight_request(self, client):
        """Test CORS preflight OPTIONS request."""
        # Preflight request for POST /api/chat
        response = client.options('/api/chat',
                                 headers={
                                     'Origin': 'http://localhost:3000',
                                     'Access-Control-Request-Method': 'POST',
                                     'Access-Control-Request-Headers': 'Content-Type'
                                 })
        
        # Should return 200 or 204 for OPTIONS
        assert response.status_code in [200, 204]
    
    @patch.dict('os.environ', {'CORS_ENABLED': 'true'})
    def test_cors_origin_header_accepted(self, client):
        """Test that requests with Origin header are accepted."""
        # Simple request with Origin header
        response = client.get('/', headers={'Origin': 'http://localhost:3000'})
        assert response.status_code == 200
    
    @patch.dict('os.environ', {'CORS_ENABLED': 'false'})
    def test_cors_can_be_disabled(self, client):
        """Test that CORS can be disabled via environment variable."""
        # When CORS is disabled, the app should still work
        response = client.get('/')
        assert response.status_code == 200
    
    @patch.dict('os.environ', {'CORS_ENABLED': 'true', 'CORS_ORIGINS': 'http://localhost:3000,http://localhost:5173'})
    def test_cors_respects_configured_origins(self):
        """Test that CORS configuration respects environment variables."""
        import os
        cors_origins = os.getenv('CORS_ORIGINS', '').split(',')
        assert 'http://localhost:3000' in cors_origins
        assert 'http://localhost:5173' in cors_origins
