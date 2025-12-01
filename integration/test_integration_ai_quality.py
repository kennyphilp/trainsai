"""
Integration Test for AI Response Quality

This test suite runs the actual application with real API calls to evaluate
AI response quality and identify opportunities for prompt improvements.

WARNING: This test makes real API calls and will consume tokens/credits.
Set SKIP_INTEGRATION=true to skip these tests.
"""

import os
import pytest
import time
import json
from datetime import datetime
from typing import Dict, List, Any

# Skip if integration tests are disabled
pytestmark = pytest.mark.skipif(
    os.getenv('SKIP_INTEGRATION', 'false').lower() == 'true',
    reason="Integration tests disabled (set SKIP_INTEGRATION=false to enable)"
)


class AIResponseAnalyzer:
    """Analyzes AI responses for quality metrics."""
    
    @staticmethod
    def analyze_response(user_query: str, ai_response: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Analyze an AI response for quality metrics.
        
        Returns:
            Dict with analysis results including:
            - has_station_info: Whether station codes/names are mentioned
            - has_time_info: Whether times are mentioned
            - has_helpful_details: Whether practical details are included
            - is_polite: Whether response is polite and friendly
            - is_accurate: Whether response appears factually correct (basic check)
            - token_efficiency: Rough measure of conciseness
            - suggestions: List of improvement suggestions
        """
        analysis = {
            'user_query': user_query,
            'ai_response': ai_response,
            'timestamp': datetime.now().isoformat(),
            'response_length': len(ai_response),
            'metrics': {},
            'suggestions': []
        }
        
        response_lower = ai_response.lower()
        
        # Check for station information
        analysis['metrics']['has_station_info'] = bool(
            any(code in ai_response.upper() for code in ['GLC', 'EDB', 'EUS', 'PAD', 'MAN', 'BHM']) or
            any(word in response_lower for word in ['glasgow', 'edinburgh', 'station', 'platform'])
        )
        
        # Check for time information
        analysis['metrics']['has_time_info'] = bool(
            ':' in ai_response or
            any(word in response_lower for word in ['morning', 'evening', 'afternoon', 'minute', 'hour', 'time'])
        )
        
        # Check for helpful details
        analysis['metrics']['has_helpful_details'] = bool(
            any(word in response_lower for word in [
                'platform', 'operator', 'delay', 'cancel', 'disruption',
                'ticket', 'fare', 'journey', 'change', 'direct'
            ])
        )
        
        # Check politeness markers (includes conversational friendliness)
        politeness_markers = ['please', 'thank', 'help', 'happy to', 'glad to', 'welcome', 'sorry',
                             'safe travels', 'mind the gap', 'take care', 'enjoy', 'hope this']
        analysis['metrics']['is_polite'] = any(marker in response_lower for marker in politeness_markers)
        
        # Check for apology without information (bad pattern)
        if 'sorry' in response_lower and 'unable' in response_lower:
            analysis['suggestions'].append(
                "Response apologizes without providing information. Consider enhancing prompts to "
                "encourage the AI to provide alternatives or suggestions even when direct answer unavailable."
            )
        
        # Token efficiency (rough heuristic: words per useful fact)
        word_count = len(ai_response.split())
        facts_mentioned = sum([
            analysis['metrics']['has_station_info'],
            analysis['metrics']['has_time_info'],
            analysis['metrics']['has_helpful_details']
        ])
        analysis['metrics']['word_count'] = word_count
        analysis['metrics']['token_efficiency'] = facts_mentioned / max(word_count / 100, 1)
        
        # Check if response is too verbose
        if word_count > 150 and facts_mentioned <= 2:
            analysis['suggestions'].append(
                "Response appears verbose for the amount of information provided. "
                "Consider adding prompt guidance for conciseness."
            )
        
        # Check if response is too terse
        if word_count < 20 and 'train' in user_query.lower():
            analysis['suggestions'].append(
                "Response may be too brief. Consider prompts that encourage helpful context."
            )
        
        # Check for missing context
        if 'when' in user_query.lower() and not analysis['metrics']['has_time_info']:
            analysis['suggestions'].append(
                "User asked about timing but response lacks time information. "
                "Enhance prompts to ensure time-related queries get temporal details."
            )
        
        if 'where' in user_query.lower() and not analysis['metrics']['has_station_info']:
            analysis['suggestions'].append(
                "User asked about location but response lacks station information. "
                "Strengthen location extraction in prompts."
            )
        
        # Overall quality score (0-100)
        score = 0
        if analysis['metrics']['has_station_info']: score += 25
        if analysis['metrics']['has_time_info']: score += 25
        if analysis['metrics']['has_helpful_details']: score += 25
        if analysis['metrics']['is_polite']: score += 15
        if 0.5 <= analysis['metrics']['token_efficiency'] <= 2.0: score += 10
        
        analysis['quality_score'] = min(score, 100)
        
        return analysis


class TestAIResponseQuality:
    """Integration tests for AI response quality."""
    
    @pytest.fixture
    def app_client(self):
        """Create a test client with real backends."""
        from app import app
        app.config['TESTING'] = False  # Enable real API calls
        app.config['RATE_LIMIT_ENABLED'] = False  # Disable rate limiting for tests
        with app.test_client() as client:
            yield client
    
    @pytest.fixture
    def analyzer(self):
        """Provide AI response analyzer."""
        return AIResponseAnalyzer()
    
    def test_simple_departure_query(self, app_client, analyzer):
        """Test: Simple departure query from Glasgow to Edinburgh."""
        # Get session
        response = app_client.get('/traintraveladvisor')
        assert response.status_code == 200
        
        # Extract session ID from cookie or create new session
        with app_client.session_transaction() as sess:
            session_id = sess.get('session_id')
        
        # Send chat message
        user_query = "What trains are leaving from Glasgow Central to Edinburgh?"
        chat_response = app_client.post('/api/chat', json={
            'message': user_query,
            'session_id': session_id
        })
        
        assert chat_response.status_code == 200
        data = chat_response.get_json()
        ai_response = data.get('response', '')
        
        # Analyze response
        analysis = analyzer.analyze_response(user_query, ai_response)
        
        # Print analysis for review (BEFORE assertions so we see it even on failure)
        print(f"\n{'='*80}")
        print(f"TEST: Simple Departure Query")
        print(f"{'='*80}")
        print(f"User Query: {user_query}")
        print(f"\nAI Response:\n{ai_response}")
        print(f"\nQuality Score: {analysis['quality_score']}/100")
        print(f"\nMetrics:")
        for key, value in analysis['metrics'].items():
            print(f"  - {key}: {value}")
        if analysis['suggestions']:
            print(f"\nSuggestions for Improvement:")
            for i, suggestion in enumerate(analysis['suggestions'], 1):
                print(f"  {i}. {suggestion}")
        print(f"{'='*80}\n")
        
        # Assertions
        assert analysis['quality_score'] >= 40, f"Quality score too low: {analysis['quality_score']}"
        assert analysis['metrics']['has_station_info'], "Response should mention station information"
        assert analysis['metrics']['is_polite'], "Response should be polite"
        
        return analysis
    
    def test_disruption_query(self, app_client, analyzer):
        """Test: Query about disruptions."""
        with app_client.session_transaction() as sess:
            session_id = sess.get('session_id')
        
        user_query = "Are there any disruptions at Glasgow Central station today?"
        chat_response = app_client.post('/api/chat', json={
            'message': user_query,
            'session_id': session_id
        })
        
        assert chat_response.status_code == 200
        data = chat_response.get_json()
        ai_response = data.get('response', '')
        
        analysis = analyzer.analyze_response(user_query, ai_response)
        
        # Assertions
        assert analysis['quality_score'] >= 50, f"Quality score too low: {analysis['quality_score']}"
        
        print(f"\n{'='*80}")
        print(f"TEST: Disruption Query")
        print(f"{'='*80}")
        print(f"User Query: {user_query}")
        print(f"\nAI Response:\n{ai_response}")
        print(f"\nQuality Score: {analysis['quality_score']}/100")
        print(f"\nMetrics:")
        for key, value in analysis['metrics'].items():
            print(f"  - {key}: {value}")
        if analysis['suggestions']:
            print(f"\nSuggestions for Improvement:")
            for i, suggestion in enumerate(analysis['suggestions'], 1):
                print(f"  {i}. {suggestion}")
        print(f"{'='*80}\n")
        
        return analysis
    
    def test_time_specific_query(self, app_client, analyzer):
        """Test: Time-specific query."""
        with app_client.session_transaction() as sess:
            session_id = sess.get('session_id')
        
        user_query = "When is the next train from Edinburgh to Glasgow after 2pm?"
        chat_response = app_client.post('/api/chat', json={
            'message': user_query,
            'session_id': session_id
        })
        
        assert chat_response.status_code == 200
        data = chat_response.get_json()
        ai_response = data.get('response', '')
        
        analysis = analyzer.analyze_response(user_query, ai_response)
        
        # Print analysis for review (BEFORE assertions)
        print(f"\n{'='*80}")
        print(f"TEST: Time-Specific Query")
        print(f"{'='*80}")
        print(f"User Query: {user_query}")
        print(f"\nAI Response:\n{ai_response}")
        print(f"\nQuality Score: {analysis['quality_score']}/100")
        print(f"\nMetrics:")
        for key, value in analysis['metrics'].items():
            print(f"  - {key}: {value}")
        if analysis['suggestions']:
            print(f"\nSuggestions for Improvement:")
            for i, suggestion in enumerate(analysis['suggestions'], 1):
                print(f"  {i}. {suggestion}")
        print(f"{'='*80}\n")
        
        # Should have time information for time-specific query
        assert analysis['metrics']['has_time_info'], "Time-specific query should include time information in response"
        print(f"\nAI Response:\n{ai_response}")
        print(f"\nQuality Score: {analysis['quality_score']}/100")
        print(f"\nMetrics:")
        for key, value in analysis['metrics'].items():
            print(f"  - {key}: {value}")
        if analysis['suggestions']:
            print(f"\nSuggestions for Improvement:")
            for i, suggestion in enumerate(analysis['suggestions'], 1):
                print(f"  {i}. {suggestion}")
        print(f"{'='*80}\n")
        
        return analysis
    
    def test_conversational_context(self, app_client, analyzer):
        """Test: Multi-turn conversation maintains context."""
        with app_client.session_transaction() as sess:
            session_id = sess.get('session_id')
        
        # First query
        query1 = "Tell me about trains from Glasgow to Edinburgh"
        response1 = app_client.post('/api/chat', json={
            'message': query1,
            'session_id': session_id
        })
        assert response1.status_code == 200
        ai_response1 = response1.get_json().get('response', '')
        
        time.sleep(1)  # Brief pause between messages
        
        # Follow-up query (should maintain context)
        query2 = "How long does that journey take?"
        response2 = app_client.post('/api/chat', json={
            'message': query2,
            'session_id': session_id
        })
        assert response2.status_code == 200
        ai_response2 = response2.get_json().get('response', '')
        
        analysis = analyzer.analyze_response(query2, ai_response2, context={'previous_query': query1})
        
        print(f"\n{'='*80}")
        print(f"TEST: Conversational Context")
        print(f"{'='*80}")
        print(f"First Query: {query1}")
        print(f"First Response: {ai_response1[:100]}...")
        print(f"\nFollow-up Query: {query2}")
        print(f"\nFollow-up Response:\n{ai_response2}")
        print(f"\nQuality Score: {analysis['quality_score']}/100")
        print(f"\nMetrics:")
        for key, value in analysis['metrics'].items():
            print(f"  - {key}: {value}")
        if analysis['suggestions']:
            print(f"\nSuggestions for Improvement:")
            for i, suggestion in enumerate(analysis['suggestions'], 1):
                print(f"  {i}. {suggestion}")
        print(f"{'='*80}\n")
        
        return analysis
    
    def test_aggregate_quality_report(self, app_client, analyzer):
        """Generate aggregate quality report across multiple test queries."""
        test_queries = [
            "Show me departures from Glasgow Central",
            "Are there any delays on the Edinburgh to Glasgow route?",
            "What platform does the 3pm train to Edinburgh leave from?",
            "I need to travel to Manchester from Glasgow, what are my options?",
            "Is there a direct train to London from Edinburgh?"
        ]
        
        analyses = []
        
        for query in test_queries:
            with app_client.session_transaction() as sess:
                session_id = sess.get('session_id')
            
            response = app_client.post('/api/chat', json={
                'message': query,
                'session_id': session_id
            })
            
            if response.status_code == 200:
                ai_response = response.get_json().get('response', '')
                analysis = analyzer.analyze_response(query, ai_response)
                analyses.append(analysis)
                time.sleep(0.5)  # Rate limiting courtesy
        
        # Aggregate metrics
        avg_score = sum(a['quality_score'] for a in analyses) / len(analyses)
        avg_word_count = sum(a['metrics']['word_count'] for a in analyses) / len(analyses)
        politeness_rate = sum(1 for a in analyses if a['metrics']['is_polite']) / len(analyses)
        
        # Collect all unique suggestions
        all_suggestions = set()
        for analysis in analyses:
            all_suggestions.update(analysis['suggestions'])
        
        print(f"\n{'='*80}")
        print(f"AGGREGATE QUALITY REPORT")
        print(f"{'='*80}")
        print(f"Total Queries Tested: {len(analyses)}")
        print(f"Average Quality Score: {avg_score:.1f}/100")
        print(f"Average Response Length: {avg_word_count:.0f} words")
        print(f"Politeness Rate: {politeness_rate*100:.0f}%")
        print(f"\nAll Improvement Suggestions:")
        for i, suggestion in enumerate(sorted(all_suggestions), 1):
            print(f"  {i}. {suggestion}")
        print(f"{'='*80}\n")
        
        # Overall recommendations
        print(f"\nOVERALL RECOMMENDATIONS FOR PROMPT IMPROVEMENT:")
        print(f"{'='*80}")
        
        if avg_score < 70:
            print("1. PRIORITY: Average quality score is below 70. Focus on improving:")
            print("   - Ensuring responses include relevant station and time information")
            print("   - Adding more helpful details (platforms, operators, journey times)")
            print("   - Maintaining consistent politeness and helpfulness")
        
        if avg_word_count > 120:
            print("2. Responses are verbose. Consider adding prompt instructions for:")
            print("   - Conciseness: 'Provide concise, focused answers'")
            print("   - Bullet points: 'Use bullet points for multiple pieces of information'")
        
        if politeness_rate < 0.8:
            print("3. Politeness could be improved. Add to system prompt:")
            print("   - 'Always maintain a friendly, helpful tone'")
            print("   - 'Use polite language and offer assistance'")
        
        if any('context' in s.lower() or 'alternative' in s.lower() for s in all_suggestions):
            print("4. Context awareness needs improvement:")
            print("   - Enhance prompts to remember previous conversation context")
            print("   - Encourage offering alternatives when direct answer unavailable")
        
        print(f"{'='*80}\n")
        
        assert avg_score >= 50, f"Average quality score too low: {avg_score}"


if __name__ == '__main__':
    # Run with: pytest test/test_integration_ai_quality.py -v -s
    pytest.main([__file__, '-v', '-s'])
