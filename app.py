"""
Flask Web Application for ScotRail Train Travel Advisor

Provides a web-based chat interface for the ScotRail AI agent.
"""

from collections import OrderedDict
from datetime import datetime, timedelta
from threading import Lock
import logging
from logging.handlers import RotatingFileHandler
import time
import os

from flask import Flask, render_template, request, jsonify, session
import secrets
from scotrail_agent import ScotRailAgent

app = Flask(__name__)
app.secret_key = os.getenv('FLASK_SECRET_KEY', secrets.token_hex(32))

# Configure logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Console handler
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
console_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
console_handler.setFormatter(console_formatter)
logger.addHandler(console_handler)

# File handler for production (if not in debug mode)
if not app.debug and not os.getenv('TESTING'):
    # Create logs directory if it doesn't exist
    os.makedirs('logs', exist_ok=True)
    file_handler = RotatingFileHandler('logs/app.log', maxBytes=10485760, backupCount=10)
    file_handler.setLevel(logging.INFO)
    file_formatter = logging.Formatter(
        '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
    )
    file_handler.setFormatter(file_formatter)
    logger.addHandler(file_handler)
    logger.info('ScotRail Train Travel Advisor startup')

# Session management configuration
MAX_SESSIONS = int(os.getenv('MAX_SESSIONS', '100'))
SESSION_TTL_HOURS = int(os.getenv('SESSION_TTL_HOURS', '24'))

# Store agent instances per session with LRU eviction
agents = OrderedDict()
session_metadata = {}  # Track last access time
agents_lock = Lock()


def _cleanup_expired_sessions():
    """Remove sessions older than SESSION_TTL_HOURS."""
    now = datetime.now()
    expired = [
        sid for sid, last_access in session_metadata.items()
        if now - last_access > timedelta(hours=SESSION_TTL_HOURS)
    ]
    if expired:
        logger.info(f"Cleaning up {len(expired)} expired sessions")
    for sid in expired:
        agents.pop(sid, None)
        session_metadata.pop(sid, None)


def get_or_create_agent(session_id):
    """Get existing agent for session or create new one with LRU eviction."""
    with agents_lock:
        # Clean expired sessions
        _cleanup_expired_sessions()
        
        # Update or create session
        if session_id in agents:
            # Move to end (most recently used)
            agents.move_to_end(session_id)
            session_metadata[session_id] = datetime.now()
            return agents[session_id], None
        
        # Create new agent
        try:
            if len(agents) >= MAX_SESSIONS:
                # Remove oldest session (LRU eviction)
                oldest_id, _ = agents.popitem(last=False)
                session_metadata.pop(oldest_id, None)
                logger.info(f"LRU eviction: removed session {oldest_id[:8]}... (total sessions: {len(agents)})")
            
            agents[session_id] = ScotRailAgent()
            session_metadata[session_id] = datetime.now()
            logger.info(f"Created new agent for session {session_id[:8]}... (total sessions: {len(agents)})")
            return agents[session_id], None
            
        except ValueError as e:
            logger.error(f"Agent initialization failed for session {session_id[:8]}...: {str(e)}")
            return None, str(e)
        except Exception as e:
            logger.error(f"Agent initialization error for session {session_id[:8]}...: {str(e)}", exc_info=True)
            return None, f"Failed to initialize agent: {str(e)}"


@app.route('/')
def index():
    """Redirect to main chat interface."""
    logger.debug(f"Index page accessed from {request.remote_addr}")
    return render_template('index.html')


@app.route('/traintraveladvisor')
def train_travel_advisor():
    """Main chat interface for train travel advisor."""
    # Initialize session if needed
    if 'session_id' not in session:
        session['session_id'] = secrets.token_hex(16)
        logger.info(f"New session created: {session['session_id'][:8]}... from {request.remote_addr}")
    else:
        logger.debug(f"Existing session {session['session_id'][:8]}... accessed chat interface")
    
    return render_template('chat.html')


@app.route('/api/chat', methods=['POST'])
def chat():
    """Handle chat messages from the user."""
    start_time = time.time()
    session_id = session.get('session_id', 'unknown')
    
    try:
        data = request.get_json()
        user_message = data.get('message', '').strip()
        
        logger.info(f"Chat request from session {session_id[:8]}..., message length: {len(user_message)} chars")
        
        if not user_message:
            logger.warning(f"Empty message from session {session_id[:8]}...")
            return jsonify({'error': 'Message cannot be empty'}), 400
        
        # Get or create agent for this session
        if not session_id or session_id == 'unknown':
            session['session_id'] = secrets.token_hex(16)
            session_id = session['session_id']
            logger.info(f"Created session ID for anonymous request: {session_id[:8]}...")
        
        agent, error = get_or_create_agent(session_id)
        if error:
            logger.error(f"Failed to get agent for session {session_id[:8]}...: {error}")
            return jsonify({'error': error}), 500
        
        # Get response from agent
        response = agent.chat(user_message)
        
        duration = time.time() - start_time
        logger.info(f"Chat response sent to session {session_id[:8]}... in {duration:.2f}s, response length: {len(response)} chars")
        
        return jsonify({
            'response': response,
            'success': True
        })
    
    except Exception as e:
        duration = time.time() - start_time
        logger.error(f"Chat error for session {session_id[:8]}... after {duration:.2f}s: {str(e)}", exc_info=True)
        return jsonify({
            'error': f'An error occurred: {str(e)}',
            'success': False
        }), 500


@app.route('/api/reset', methods=['POST'])
def reset_conversation():
    """Reset the conversation history."""
    session_id = session.get('session_id', 'unknown')
    
    try:
        if session_id and session_id != 'unknown' and session_id in agents:
            agents[session_id].reset_conversation()
            logger.info(f"Conversation reset for session {session_id[:8]}...")
            return jsonify({
                'success': True,
                'message': 'Conversation reset successfully'
            })
        logger.debug(f"Reset requested for session {session_id[:8]}... with no active conversation")
        return jsonify({
            'success': True,
            'message': 'No active conversation to reset'
        })
    except Exception as e:
        logger.error(f"Failed to reset conversation for session {session_id[:8]}...: {str(e)}", exc_info=True)
        return jsonify({
            'error': f'Failed to reset conversation: {str(e)}',
            'success': False
        }), 500


@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint."""
    logger.debug(f"Health check from {request.remote_addr}")
    return jsonify({
        'status': 'healthy',
        'service': 'ScotRail Train Travel Advisor',
        'active_sessions': len(agents)
    })


if __name__ == '__main__':
    # Flask server configuration from environment (production-safe defaults)
    debug_mode = os.getenv('FLASK_DEBUG', 'False').lower() in ('true', '1', 'yes')
    port = int(os.getenv('FLASK_PORT', '5001'))
    host = os.getenv('FLASK_HOST', '0.0.0.0')
    
    logger.info(f'Starting ScotRail Train Travel Advisor on http://{host}:{port}')
    logger.info(f'Debug mode: {debug_mode}')
    logger.info(f'Session limits: MAX_SESSIONS={MAX_SESSIONS}, SESSION_TTL_HOURS={SESSION_TTL_HOURS}')
    
    if debug_mode:
        logger.warning('Running in DEBUG mode - not suitable for production!')
    
    app.run(debug=debug_mode, host=host, port=port)
