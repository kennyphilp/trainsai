"""
Flask Web Application for ScotRail Train Travel Advisor

Provides a web-based chat interface for the ScotRail AI agent.
"""

from flask import Flask, render_template, request, jsonify, session
import secrets
import os
from scotrail_agent import ScotRailAgent

app = Flask(__name__)
app.secret_key = os.getenv('FLASK_SECRET_KEY', secrets.token_hex(32))

# Store agent instances per session
agents = {}


def get_or_create_agent(session_id):
    """Get existing agent for session or create new one."""
    if session_id not in agents:
        try:
            agents[session_id] = ScotRailAgent()
        except ValueError as e:
            return None, str(e)
        except Exception as e:
            return None, f"Failed to initialize agent: {str(e)}"
    return agents[session_id], None


@app.route('/')
def index():
    """Redirect to main chat interface."""
    return render_template('index.html')


@app.route('/traintraveladvisor')
def train_travel_advisor():
    """Main chat interface for train travel advisor."""
    # Initialize session if needed
    if 'session_id' not in session:
        session['session_id'] = secrets.token_hex(16)
    
    return render_template('chat.html')


@app.route('/api/chat', methods=['POST'])
def chat():
    """Handle chat messages from the user."""
    try:
        data = request.get_json()
        user_message = data.get('message', '').strip()
        
        if not user_message:
            return jsonify({'error': 'Message cannot be empty'}), 400
        
        # Get or create agent for this session
        session_id = session.get('session_id')
        if not session_id:
            session['session_id'] = secrets.token_hex(16)
            session_id = session['session_id']
        
        agent, error = get_or_create_agent(session_id)
        if error:
            return jsonify({'error': error}), 500
        
        # Get response from agent
        response = agent.chat(user_message)
        
        return jsonify({
            'response': response,
            'success': True
        })
    
    except Exception as e:
        return jsonify({
            'error': f'An error occurred: {str(e)}',
            'success': False
        }), 500


@app.route('/api/reset', methods=['POST'])
def reset_conversation():
    """Reset the conversation history."""
    try:
        session_id = session.get('session_id')
        if session_id and session_id in agents:
            agents[session_id].reset_conversation()
            return jsonify({
                'success': True,
                'message': 'Conversation reset successfully'
            })
        return jsonify({
            'success': True,
            'message': 'No active conversation to reset'
        })
    except Exception as e:
        return jsonify({
            'error': f'Failed to reset conversation: {str(e)}',
            'success': False
        }), 500


@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint."""
    return jsonify({
        'status': 'healthy',
        'service': 'ScotRail Train Travel Advisor'
    })


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5001)
