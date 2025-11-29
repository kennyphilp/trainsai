# ScotRail Train Travel Advisor - Web Application

A Flask-based web interface for the ScotRail AI chatbot assistant.

## Features

- **Interactive Chat Interface**: Jupyter-like notebook style with alternating user/agent messages
- **Real-time Train Data**: Access to live departure boards, service details, and disruptions
- **Session Management**: Each user gets their own isolated chat session
- **Conversation History**: Maintains context throughout the conversation
- **Reset Capability**: Clear conversation history and start fresh
- **Responsive Design**: Works on desktop and mobile devices

## Installation

1. Ensure all dependencies are installed:
```bash
pip install -r requirements.txt
```

2. Make sure your `.env` file contains the required API keys:
```
OPENAI_API_KEY=your_openai_api_key
LDB_TOKEN=your_national_rail_token
DISRUPTIONS_API_KEY=your_rdg_api_key
```

## Running the Application

### Development Mode

```bash
python app.py
```

The application will start on `http://127.0.0.1:5001`

### Production Mode

For production, use a WSGI server like Gunicorn:

```bash
pip install gunicorn
gunicorn -w 4 -b 0.0.0.0:5001 app:app
```

## Application Routes

- `/` - Welcome page with introduction
- `/traintraveladvisor` - Main chat interface
- `/api/chat` (POST) - Send messages to the AI agent
- `/api/reset` (POST) - Reset conversation history
- `/api/health` (GET) - Health check endpoint

## API Endpoints

### POST /api/chat

Send a message to the AI agent.

**Request:**
```json
{
  "message": "When is the next train from Edinburgh to Glasgow?"
}
```

**Response:**
```json
{
  "response": "Let me check that for you...",
  "success": true
}
```

### POST /api/reset

Reset the conversation history for the current session.

**Response:**
```json
{
  "success": true,
  "message": "Conversation reset successfully"
}
```

### GET /api/health

Check if the service is running.

**Response:**
```json
{
  "status": "healthy",
  "service": "ScotRail Train Travel Advisor"
}
```

## Architecture

The application consists of:

1. **Flask Backend** (`app.py`): Handles routing, session management, and agent orchestration
2. **ScotRailAgent** (`scotrail_agent.py`): OpenAI-powered chatbot with tool integration
3. **TrainTools** (`train_tools.py`): API client for National Rail services
4. **Templates**: HTML/CSS/JavaScript for the web interface

## User Interface

The chat interface features:

- **Message Blocks**: Each message appears in a distinct block with a header (You/ScotRail Assistant)
- **Read-only Responses**: Agent messages cannot be edited
- **New Input Fields**: A fresh textarea appears after each response
- **Visual Distinction**: User messages and agent responses have different styling
- **Loading Indicators**: Shows when the agent is thinking
- **Error Handling**: Graceful error messages for API failures

## Example Queries

Try asking:
- "When is the next train from Edinburgh to Glasgow?"
- "Are there any delays on trains from Glasgow Central?"
- "Show me all the stops for the next train from Aberdeen"
- "What engineering works are planned this weekend?"

## Technical Details

- **Session Management**: Uses Flask sessions with secure tokens
- **Agent Instances**: One agent instance per session stored in memory
- **Context Management**: Automatically truncates conversation history to prevent token overflow
- **Error Recovery**: Comprehensive error handling for API failures and network issues

## Styling

The interface uses a dark theme inspired by VS Code and Jupyter notebooks:
- Dark background (#1e1e1e)
- Syntax highlighting colors for headers
- Gradient accents (purple/blue theme)
- Rounded corners and subtle shadows
- Responsive layout for mobile devices

## Security Notes

- Set `FLASK_SECRET_KEY` environment variable for production
- Uses HTTPS in production
- Session tokens are cryptographically secure
- Input validation on all API endpoints

## Future Enhancements

- Message history persistence (database)
- User authentication
- Multi-user support with persistent accounts
- Export conversation history
- Voice input/output
- Station autocomplete
- Map integration
