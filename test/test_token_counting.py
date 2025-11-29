"""
Tests for token counting functionality in ScotRailAgent

Tests ensure that:
1. Token counting works accurately with tiktoken
2. Token counting falls back to estimation when tiktoken unavailable
3. Proactive truncation prevents context overflow
4. Token usage is properly logged
5. Smart truncation preserves conversation coherence
"""

import pytest
import json
from unittest.mock import patch, MagicMock, Mock
import os


class TestTokenCounting:
    """Test suite for token counting functionality."""
    
    @patch.dict('os.environ', {'OPENAI_API_KEY': 'test-key'})
    def test_token_encoder_initialization_with_tiktoken(self):
        """Test that token encoder initializes correctly when tiktoken is available."""
        with patch('scotrail_agent.TIKTOKEN_AVAILABLE', True):
            with patch('scotrail_agent.tiktoken.encoding_for_model') as mock_encoder:
                mock_encoding = MagicMock()
                mock_encoder.return_value = mock_encoding
                
                from scotrail_agent import ScotRailAgent
                agent = ScotRailAgent()
                
                assert agent.encoding is not None
                mock_encoder.assert_called_once_with("gpt-4o-mini")
    
    @patch.dict('os.environ', {'OPENAI_API_KEY': 'test-key'})
    def test_token_encoder_fallback_to_cl100k_base(self):
        """Test fallback to cl100k_base encoding when model encoding not found."""
        with patch('scotrail_agent.TIKTOKEN_AVAILABLE', True):
            with patch('scotrail_agent.tiktoken.encoding_for_model', side_effect=KeyError):
                with patch('scotrail_agent.tiktoken.get_encoding') as mock_get_encoding:
                    mock_encoding = MagicMock()
                    mock_get_encoding.return_value = mock_encoding
                    
                    from scotrail_agent import ScotRailAgent
                    agent = ScotRailAgent()
                    
                    assert agent.encoding is not None
                    mock_get_encoding.assert_called_once_with("cl100k_base")
    
    @patch.dict('os.environ', {'OPENAI_API_KEY': 'test-key'})
    def test_token_encoder_none_when_tiktoken_unavailable(self):
        """Test that encoding is None when tiktoken is not available."""
        with patch('scotrail_agent.TIKTOKEN_AVAILABLE', False):
            from scotrail_agent import ScotRailAgent
            agent = ScotRailAgent()
            
            assert agent.encoding is None
    
    @patch.dict('os.environ', {'OPENAI_API_KEY': 'test-key'})
    def test_count_tokens_with_tiktoken(self):
        """Test accurate token counting with tiktoken."""
        with patch('scotrail_agent.TIKTOKEN_AVAILABLE', True):
            with patch('scotrail_agent.tiktoken.encoding_for_model') as mock_encoder:
                mock_encoding = MagicMock()
                mock_encoding.encode.return_value = [1, 2, 3, 4, 5]  # 5 tokens
                mock_encoder.return_value = mock_encoding
                
                from scotrail_agent import ScotRailAgent
                agent = ScotRailAgent()
                
                messages = [
                    {"role": "user", "content": "Hello"},
                    {"role": "assistant", "content": "Hi there"}
                ]
                
                token_count = agent.count_tokens(messages)
                
                # Should count: 2 messages * 4 overhead + content tokens
                assert token_count > 0
                assert isinstance(token_count, int)
    
    @patch.dict('os.environ', {'OPENAI_API_KEY': 'test-key'})
    def test_count_tokens_with_tool_calls(self):
        """Test token counting includes tool calls."""
        with patch('scotrail_agent.TIKTOKEN_AVAILABLE', True):
            with patch('scotrail_agent.tiktoken.encoding_for_model') as mock_encoder:
                mock_encoding = MagicMock()
                mock_encoding.encode.return_value = [1, 2, 3]
                mock_encoder.return_value = mock_encoding
                
                from scotrail_agent import ScotRailAgent
                agent = ScotRailAgent()
                
                messages = [
                    {
                        "role": "assistant",
                        "content": None,
                        "tool_calls": [
                            {
                                "function": {
                                    "name": "get_departure_board",
                                    "arguments": '{"station_code": "EDB"}'
                                }
                            }
                        ]
                    }
                ]
                
                token_count = agent.count_tokens(messages)
                
                assert token_count > 0
                assert isinstance(token_count, int)
    
    @patch.dict('os.environ', {'OPENAI_API_KEY': 'test-key'})
    def test_count_tokens_estimation_fallback(self):
        """Test token counting falls back to estimation without tiktoken."""
        with patch('scotrail_agent.TIKTOKEN_AVAILABLE', False):
            from scotrail_agent import ScotRailAgent
            agent = ScotRailAgent()
            
            messages = [
                {"role": "user", "content": "Hello world"},
                {"role": "assistant", "content": "Hi there, how can I help?"}
            ]
            
            token_count = agent.count_tokens(messages)
            
            # Estimation: ~1 token per 4 characters
            # "Hello world" = 11 chars, "Hi there, how can I help?" = 26 chars
            # Total ~37 chars / 4 = ~9 tokens
            assert token_count > 0
            assert isinstance(token_count, int)
    
    @patch.dict('os.environ', {'OPENAI_API_KEY': 'test-key'})
    def test_should_truncate_returns_false_under_limit(self):
        """Test should_truncate returns False when under token limit."""
        with patch('scotrail_agent.TIKTOKEN_AVAILABLE', False):
            from scotrail_agent import ScotRailAgent
            agent = ScotRailAgent()
            
            # Small conversation should not need truncation
            agent.conversation_history = [
                {"role": "system", "content": "System prompt"},
                {"role": "user", "content": "Hello"},
                {"role": "assistant", "content": "Hi"}
            ]
            
            should_truncate = agent.should_truncate()
            
            assert should_truncate is False
    
    @patch.dict('os.environ', {'OPENAI_API_KEY': 'test-key'})
    def test_should_truncate_returns_true_over_limit(self):
        """Test should_truncate returns True when over token limit."""
        with patch('scotrail_agent.TIKTOKEN_AVAILABLE', False):
            from scotrail_agent import ScotRailAgent
            agent = ScotRailAgent()
            
            # Simulate large conversation by directly mocking count_tokens
            # to return a value over the limit
            agent.count_tokens = MagicMock(return_value=150000)  # Over 128k limit
            
            should_truncate = agent.should_truncate()
            
            assert should_truncate is True
    
    @patch.dict('os.environ', {'OPENAI_API_KEY': 'test-key'})
    def test_truncate_conversation_preserves_system_prompt(self):
        """Test that truncation always preserves the system prompt."""
        with patch('scotrail_agent.TIKTOKEN_AVAILABLE', False):
            from scotrail_agent import ScotRailAgent
            agent = ScotRailAgent()
            
            system_prompt = agent.conversation_history[0]
            
            # Add many messages
            for i in range(30):
                agent.conversation_history.append({
                    "role": "user" if i % 2 == 0 else "assistant",
                    "content": f"Message {i}"
                })
            
            agent._truncate_conversation()
            
            # System prompt should be first message
            assert agent.conversation_history[0] == system_prompt
            assert agent.conversation_history[0]["role"] == "system"
    
    @patch.dict('os.environ', {'OPENAI_API_KEY': 'test-key'})
    def test_truncate_conversation_keeps_recent_messages(self):
        """Test that truncation keeps the most recent messages."""
        with patch('scotrail_agent.TIKTOKEN_AVAILABLE', False):
            from scotrail_agent import ScotRailAgent
            agent = ScotRailAgent()
            
            # Add many messages
            for i in range(30):
                agent.conversation_history.append({
                    "role": "user" if i % 2 == 0 else "assistant",
                    "content": f"Message {i}"
                })
            
            last_message_before = agent.conversation_history[-1]
            
            agent._truncate_conversation()
            
            # Last message should still be present
            assert agent.conversation_history[-1] == last_message_before
            # Should keep system prompt + 15 recent messages
            assert len(agent.conversation_history) == 16  # 1 system + 15 recent
    
    @patch.dict('os.environ', {'OPENAI_API_KEY': 'test-key'})
    def test_truncate_conversation_no_truncation_when_small(self):
        """Test that truncation does nothing when conversation is small."""
        with patch('scotrail_agent.TIKTOKEN_AVAILABLE', False):
            from scotrail_agent import ScotRailAgent
            agent = ScotRailAgent()
            
            # Add just a few messages
            agent.conversation_history.append({"role": "user", "content": "Hello"})
            agent.conversation_history.append({"role": "assistant", "content": "Hi"})
            
            messages_before = len(agent.conversation_history)
            
            agent._truncate_conversation()
            
            # Should not truncate
            assert len(agent.conversation_history) == messages_before


class TestTokenCountingIntegration:
    """Integration tests for token counting with chat functionality."""
    
    @patch.dict('os.environ', {'OPENAI_API_KEY': 'test-key'})
    @patch('scotrail_agent.TIKTOKEN_AVAILABLE', False)
    def test_chat_triggers_proactive_truncation(self):
        """Test that chat() triggers truncation when token limit approaches."""
        from scotrail_agent import ScotRailAgent
        
        agent = ScotRailAgent()
        
        # Mock the OpenAI client
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Test response"
        mock_response.choices[0].message.tool_calls = None
        agent.client.chat.completions.create = MagicMock(return_value=mock_response)
        
        # Add many messages to trigger truncation
        for i in range(30):
            agent.conversation_history.append({
                "role": "user" if i % 2 == 0 else "assistant",
                "content": f"Message {i}"
            })
        
        # Mock should_truncate to return True
        agent.should_truncate = MagicMock(return_value=True)
        agent._truncate_conversation = MagicMock()
        
        agent.chat("Test message")
        
        # Truncation should have been called
        agent._truncate_conversation.assert_called_once()
    
    @patch.dict('os.environ', {'OPENAI_API_KEY': 'test-key'})
    @patch('scotrail_agent.TIKTOKEN_AVAILABLE', True)
    def test_token_counting_logged(self):
        """Test that token counting is logged during chat."""
        with patch('scotrail_agent.tiktoken.encoding_for_model') as mock_encoder:
            mock_encoding = MagicMock()
            mock_encoding.encode.return_value = [1, 2, 3]
            mock_encoder.return_value = mock_encoding
            
            from scotrail_agent import ScotRailAgent
            import logging
            
            agent = ScotRailAgent()
            
            # Mock the OpenAI client
            mock_response = MagicMock()
            mock_response.choices = [MagicMock()]
            mock_response.choices[0].message.content = "Test response"
            mock_response.choices[0].message.tool_calls = None
            agent.client.chat.completions.create = MagicMock(return_value=mock_response)
            
            # Capture logs
            with patch('scotrail_agent.logger') as mock_logger:
                agent.chat("Test message")
                
                # Should log token information
                assert mock_logger.info.called
                # Check that at least one call mentions tokens
                log_calls = [str(call) for call in mock_logger.info.call_args_list]
                assert any('token' in str(call).lower() for call in log_calls)


class TestTokenConstants:
    """Test token-related constants and configuration."""
    
    def test_max_context_tokens_set_correctly(self):
        """Test that MAX_CONTEXT_TOKENS is set to GPT-4o-mini limit."""
        from scotrail_agent import MAX_CONTEXT_TOKENS
        
        assert MAX_CONTEXT_TOKENS == 128000
    
    def test_safety_margin_tokens_set(self):
        """Test that SAFETY_MARGIN_TOKENS is configured."""
        from scotrail_agent import SAFETY_MARGIN_TOKENS
        
        assert SAFETY_MARGIN_TOKENS == 1000
    
    def test_max_tokens_per_response_set(self):
        """Test that MAX_TOKENS_PER_RESPONSE is configured."""
        from scotrail_agent import MAX_TOKENS_PER_RESPONSE
        
        assert MAX_TOKENS_PER_RESPONSE == 1000
    
    @patch.dict('os.environ', {'OPENAI_API_KEY': 'test-key'})
    def test_agent_token_limits_initialized(self):
        """Test that agent initializes with correct token limits."""
        with patch('scotrail_agent.TIKTOKEN_AVAILABLE', False):
            from scotrail_agent import ScotRailAgent
            agent = ScotRailAgent()
            
            assert agent.max_context_tokens == 128000
            assert agent.max_response_tokens == 1000
            assert agent.safety_margin == 1000


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
