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
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_cors import CORS
from flask_talisman import Talisman
from scotrail_agent import ScotRailAgent
from config import get_config
from dependencies import get_container
from health_integration import setup_health_monitoring, update_agents_health_monitoring

# Load configuration
config = get_config()

app = Flask(__name__)
app.secret_key = config.flask_secret_key
app.config['TESTING'] = config.testing

# Initialize limiter - will be enabled/disabled based on runtime configuration
limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=[],  # Set per-endpoint limits instead
    storage_uri="memory://",
    strategy="fixed-window"
)

def should_limit():
    """Check if rate limiting should be applied (not in testing mode)."""
    # Use app.config['TESTING'] so tests can modify it dynamically
    return not app.config.get('TESTING', False) and config.rate_limit_enabled

# Configure CORS
if config.cors_enabled:
    CORS(app,
         origins=config.cors_origins,
         methods=['GET', 'POST', 'OPTIONS'],
         allow_headers=['Content-Type', 'Authorization'],
         supports_credentials=True,
         max_age=600)


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
if not app.debug and not config.testing:
    # Create logs directory if it doesn't exist
    os.makedirs(os.path.dirname(config.log_file), exist_ok=True)
    file_handler = RotatingFileHandler(config.log_file, maxBytes=config.log_max_bytes, backupCount=config.log_backup_count)
    file_handler.setLevel(getattr(logging, config.log_level))
    file_formatter = logging.Formatter(
        '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
    )
    file_handler.setFormatter(file_formatter)
    logger.addHandler(file_handler)
    logger.info('ScotRail Train Travel Advisor startup')

# Configure HTTPS enforcement with Talisman (disabled in debug/testing mode)
# Only enforces HTTPS in production environments
import sys
debug_mode = '--debug' in sys.argv or config.flask_debug

if not config.testing and not debug_mode and config.https_enabled:
    Talisman(
        app,
        force_https=True,
        strict_transport_security=True,
        strict_transport_security_max_age=31536000,  # 1 year
        content_security_policy={
            'default-src': ["'self'"],
            'script-src': ["'self'", "'unsafe-inline'"],
            'style-src': ["'self'", "'unsafe-inline'"],
            'img-src': ["'self'", 'data:', 'https:'],
            'connect-src': ["'self'", 'https://api.openai.com'],
        },
        content_security_policy_nonce_in=['script-src']
    )
    logger.info('HTTPS enforcement enabled with Talisman (strict transport security, CSP headers)')
else:
    if config.testing:
        logger.debug('HTTPS enforcement disabled (testing mode)')
    elif debug_mode:
        logger.info('HTTPS enforcement disabled (debug mode)')
    else:
        logger.info('HTTPS enforcement disabled by configuration (HTTPS_ENABLED=false)')


# Store agent instances per session with LRU eviction
agents = OrderedDict()
session_metadata = {}  # Track last access time
agents_lock = Lock()


# Initialize health monitoring system
setup_health_monitoring(app, config, agents)


def validate_message_content(message: str) -> tuple[bool, str]:
    """Validate message content and return (is_valid, error_message)."""
    if not message or not message.strip():
        return False, "Message cannot be empty"
    
    if len(message) > config.max_message_length:
        return False, f"Message too long (max {config.max_message_length} characters)"
    
    if len(message.strip()) < config.min_message_length:
        return False, f"Message too short (min {config.min_message_length} character)"
    
    # Check for suspicious patterns (basic XSS prevention)
    suspicious_patterns = ['<script', 'javascript:', 'onerror=', 'onclick=', 'onload=']
    message_lower = message.lower()
    for pattern in suspicious_patterns:
        if pattern in message_lower:
            return False, "Message contains invalid content"
    
    return True, ""


def _cleanup_expired_sessions():
    """Remove sessions older than configured TTL."""
    now = datetime.now()
    expired = [
        sid for sid, last_access in session_metadata.items()
        if now - last_access > timedelta(hours=config.session_ttl_hours)
    ]
    if expired:
        logger.info(f"Cleaning up {len(expired)} expired sessions")
        # Update health monitoring with cleaned agents dict
        update_agents_health_monitoring(app, agents)
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
        
        # Create new agent - use DI container for both production and testing
        try:
            if len(agents) >= config.max_sessions:
                # Remove oldest session (LRU eviction)
                oldest_id, _ = agents.popitem(last=False)
                session_metadata.pop(oldest_id, None)
                logger.info(f"LRU eviction: removed session {oldest_id[:8]}... (total sessions: {len(agents)})")
                # Update health monitoring with new agents dict
                update_agents_health_monitoring(app, agents)
            
            # Always use DI container - this allows test mocks to be injected
            container = get_container()
            agents[session_id] = container.create_agent(ScotRailAgent)
            
            session_metadata[session_id] = datetime.now()
            logger.info(f"Created new agent for session {session_id[:8]}... (total sessions: {len(agents)})")
            
            # Update health monitoring with new agents dict
            update_agents_health_monitoring(app, agents)
            
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
@limiter.limit(config.rate_limit_chat, exempt_when=lambda: app.config.get('TESTING', False))
def chat():
    """Handle chat messages from the user."""
    start_time = time.time()
    session_id = session.get('session_id', 'unknown')
    
    try:
        # Validate content type
        if not request.is_json:
            logger.warning(f"Invalid content type from session {session_id[:8]}...")
            return jsonify({'error': 'Content-Type must be application/json'}), 400
        
        # Validate JSON structure
        data = request.get_json()
        if not isinstance(data, dict):
            logger.warning(f"Invalid JSON format from session {session_id[:8]}...")
            return jsonify({'error': 'Invalid JSON format'}), 400
        
        # Get and validate message
        user_message = data.get('message', '')
        if not isinstance(user_message, str):
            logger.warning(f"Non-string message from session {session_id[:8]}...")
            return jsonify({'error': 'Message must be a string'}), 400
        
        user_message = user_message.strip()
        
        logger.info(f"Chat request from session {session_id[:8]}..., message length: {len(user_message)} chars")
        
        # Validate message content
        is_valid, error_msg = validate_message_content(user_message)
        if not is_valid:
            logger.warning(f"Invalid message from session {session_id[:8]}...: {error_msg}")
            return jsonify({'error': error_msg}), 400
        
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
        
        # Return response with optional timetable data
        result = {
            'response': response,
            'success': True
        }
        
        # Include timetable data if available
        if hasattr(agent, 'last_timetable_data') and agent.last_timetable_data:
            result['timetable'] = agent.last_timetable_data
            logger.info(f"Including timetable data: {agent.last_timetable_data.get('type')} with {len(agent.last_timetable_data.get('trains', []))} trains")
        else:
            logger.info(f"No timetable data available (hasattr: {hasattr(agent, 'last_timetable_data')}, value: {getattr(agent, 'last_timetable_data', None)})")
        
        return jsonify(result)
    
    except Exception as e:
        duration = time.time() - start_time
        logger.error(f"Chat error for session {session_id[:8]}... after {duration:.2f}s: {str(e)}", exc_info=True)
        return jsonify({
            'error': f'An error occurred: {str(e)}',
            'success': False
        }), 500


@app.route('/api/reset', methods=['POST'])
@limiter.limit(config.rate_limit_chat, exempt_when=lambda: app.config.get('TESTING', False))
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


if __name__ == '__main__':
    import sys
    
    # Suppress werkzeug TLS handshake errors (happens when browsers try HTTPS on HTTP server)
    werkzeug_logger = logging.getLogger('werkzeug')
    
    class TLSErrorFilter(logging.Filter):
        def filter(self, record):
            # Filter out "Bad request version" errors which are TLS handshakes
            return 'Bad request version' not in record.getMessage()
    
    werkzeug_logger.addFilter(TLSErrorFilter())
    
    # Parse command line arguments
    debug_mode = '--debug' in sys.argv or config.flask_debug
    
    logger.info(f'Starting ScotRail Train Travel Advisor on http://{config.flask_host}:{config.flask_port}')
    logger.info(f'Debug mode: {debug_mode}')
    logger.info(f'Session limits: MAX_SESSIONS={config.max_sessions}, SESSION_TTL_HOURS={config.session_ttl_hours}')
    
    if debug_mode:
        logger.warning('Running in DEBUG mode - not suitable for production!')
    
    # Validate configuration
    missing_keys = config.validate_required_keys()
    if missing_keys:
        logger.warning(f'Missing recommended configuration: {", ".join(missing_keys)}')
    
    app.run(debug=debug_mode, host=config.flask_host, port=config.flask_port)
