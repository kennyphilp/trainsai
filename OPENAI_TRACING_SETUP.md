# OpenAI Request Tracking and Debugging

**Date:** December 1, 2025  
**Status:** ✅ Enhanced Logging Enabled in Debug Mode

## Important Note About OpenAI Traces Dashboard

**The OpenAI Traces dashboard (https://platform.openai.com/traces) is for organizations using specific enterprise features.** For standard API usage, you can track requests using:

1. **Request IDs** - Logged for each API call (search in Usage dashboard)
2. **Enhanced Debug Logging** - Full request/response details in application logs
3. **OpenAI Usage Dashboard** - View all API calls at https://platform.openai.com/usage

## What's Implemented

### Enhanced Debug Logging

When `FLASK_DEBUG=true`, the application logs detailed information about every OpenAI API call:

#### Request Details
- Model used
- Number of messages in conversation
- Number of tools available
- Request timestamp

#### Response Details
- **Request ID** (use this to find the request in OpenAI dashboard)
- Model that processed the request
- Token usage (prompt + completion = total)
- Response timestamp

#### Tool/Function Calls
- Function name called
- Arguments passed
- Response length
- Execution order

### Where to View API Activity

#### 1. Application Logs (Real-time)
```bash
# Start application and see detailed logs
python app.py

# Example log output:
INFO - Chat request - Current tokens: 1234, Messages: 5
DEBUG - OpenAI API Call - Model: gpt-4o-mini, Messages: 5, Tools: 4
DEBUG - Tool Call - Function: get_departure_board, Args: {'station_code': 'GLC'}
DEBUG - Tool Response - Function: get_departure_board, Response length: 1523 chars
DEBUG - OpenAI Response - ID: chatcmpl-ABC123xyz, Usage: 2156 tokens
INFO - Request ID: chatcmpl-ABC123xyz - Check OpenAI dashboard
```

#### 2. OpenAI Usage Dashboard
Visit: **https://platform.openai.com/usage**
- View all API requests by date
- Search by Request ID (from logs)
- See token usage and costs
- Filter by model, date range
- Export usage data

#### 3. OpenAI Playground (Recreate Requests)
Visit: **https://platform.openai.com/playground/chat**
- Not automatic - manually recreate requests
- Test prompts and tools
- Experiment with parameters

## Implementation Details

### Changes Made

#### 1. `scotrail_agent.py` - Enhanced Debug Logging

**Lines 22-40:** HTTP request/response logging
```python
# Enable OpenAI detailed logging in debug mode
try:
    debug_mode = os.getenv('FLASK_DEBUG', 'False').lower() in ('true', '1', 'yes')
    if debug_mode:
        # Enable httpx logging to see full request/response details
        import httpx
        import logging as stdlib_logging
        httpx_logger = stdlib_logging.getLogger("httpx")
        httpx_logger.setLevel(stdlib_logging.DEBUG)
        
        print("✓ OpenAI request/response logging enabled for debugging")
except Exception as e:
    print(f"Note: Could not enable OpenAI debug logging: {e}")
```

**Lines 78-96:** Client initialization with custom headers
```python
def __init__(self):
    self.debug_mode = os.getenv('FLASK_DEBUG', 'False').lower() in ('true', '1', 'yes')
    
    extra_headers = {}
    if self.debug_mode:
        extra_headers["X-Custom-Project"] = "ScotRail-TrainAI"
        logger.info("OpenAI client initialized with debug mode and request tracking")
    
    self.client = OpenAI(
        api_key=api_key,
        default_headers=extra_headers if extra_headers else None
    )
```

**Chat Method:** Request ID logging
```python
response = self.client.chat.completions.create(...)

if self.debug_mode:
    logger.debug(f"OpenAI Response - ID: {response.id}, Model: {response.model}, "
               f"Usage: {response.usage.total_tokens} tokens")
    logger.info(f"Request ID: {response.id} - Check OpenAI dashboard for details")
```

## How to Track Your Requests

### Step 1: Run Application in Debug Mode
```bash
# Ensure FLASK_DEBUG=true in .env
python app.py
```

You'll see:
```
✓ OpenAI request/response logging enabled for debugging
```

### Step 2: Make a Request
```bash
curl -X POST http://localhost:8080/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "What trains are leaving Glasgow Central?"}'
```

### Step 3: Find Request ID in Logs
Look for lines like:
```
INFO - Request ID: chatcmpl-ABC123xyz - Check OpenAI dashboard for details
```

### Step 4: Search in OpenAI Dashboard
1. Go to https://platform.openai.com/usage
2. Click on "Request ID" filter
3. Paste your Request ID: `chatcmpl-ABC123xyz`
4. View full request details including:
   - Exact timestamp
   - Token usage breakdown
   - Model used
   - Request/response (if enabled in your org settings)

### Alternative: Browse by Date
1. Go to https://platform.openai.com/usage
2. Select the date of your requests
3. Filter by model: `gpt-4o-mini`
4. Look for requests from your IP or with custom headers

## What You Can Track

### In Application Logs (Immediately Available)
✅ **Request IDs** - Unique identifier for each API call  
✅ **Token counts** - Prompt, completion, and total tokens  
✅ **Tool/function calls** - Which functions were called and with what arguments  
✅ **Response times** - How long each request took  
✅ **Error messages** - Full error details if requests fail  
✅ **Conversation context** - Number of messages in history  

### In OpenAI Usage Dashboard (https://platform.openai.com/usage)
✅ **All API requests** - Complete history of calls  
✅ **Cost breakdown** - How much each request cost  
✅ **Token usage trends** - Daily/weekly usage patterns  
✅ **Request filtering** - Search by ID, date, model  
✅ **Export data** - Download usage reports  

### NOT Available (Enterprise Feature)
❌ **Real-time trace viewer** at platform.openai.com/traces  
❌ **Automatic span/trace collection** (requires enterprise observability)  
❌ **Distributed tracing** across services  

**Note:** The `/traces` endpoint is for organizations using OpenAI's enterprise observability features or third-party integrations like LangSmith, Weights & Biases, etc.

## Verification

### Startup Message
When tracing is enabled, you'll see:
```
✓ OpenAI tracing enabled - view traces at https://platform.openai.com/traces
```

### Log Message
In the application logs:
```
INFO - OpenAI client initialized with tracing enabled
```

## Viewing Traces

### Access Traces Dashboard
1. Visit: https://platform.openai.com/traces
2. Log in with your OpenAI account
3. View real-time traces of API calls

### Trace Information Includes
- **Request Details**
  - Model used (gpt-4o-mini)
  - Messages sent
  - Tools/functions called
  - Parameters (temperature, max_tokens, etc.)

- **Response Details**
  - Completion content
  - Token usage
  - Tool call results
  - Response time

- **Function Calls**
  - Tool name
  - Arguments passed
  - Results returned
  - Execution order

### Example Traced API Calls

1. **Initial Chat Request**
   - User message
   - System prompt
   - Available tools list
   - Tool selection decision

2. **Tool Execution**
   - `get_departure_board(station_code="GLC")`
   - API response with train data
   - Function result formatting

3. **Final Response**
   - Synthesized answer
   - Token counts
   - Complete conversation history

## Benefits

### Development & Debugging
- ✅ See exactly what's sent to OpenAI API
- ✅ Debug tool calling behavior
- ✅ Monitor token usage per request
- ✅ Identify performance bottlenecks
- ✅ Trace conversation history management

### Quality Analysis
- ✅ Validate prompt effectiveness
- ✅ Check tool call accuracy
- ✅ Analyze response patterns
- ✅ Monitor context window usage

### Cost Optimization
- ✅ Track token consumption
- ✅ Identify expensive operations
- ✅ Optimize conversation truncation

## Important Notes

### Security
- ⚠️ Traces may contain user queries and responses
- ⚠️ Do NOT enable in production with sensitive data
- ⚠️ Traces are visible in your OpenAI dashboard

### Performance
- Minimal overhead - header addition only
- No significant latency impact
- Traces processed asynchronously by OpenAI

### Production Use
- **Recommended:** Disable tracing in production (`FLASK_DEBUG=false`)
- Tracing is development/testing feature only
- Use for debugging and analysis, not production monitoring

## Testing Tracing

### Test the Application
```bash
# Start the application (tracing auto-enabled with FLASK_DEBUG=true)
python app.py

# Make a test request
curl -X POST http://localhost:8080/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "What trains are leaving Glasgow Central?"}'

# Check traces at: https://platform.openai.com/traces
```

### Expected Trace Flow
1. User query: "What trains are leaving Glasgow Central?"
2. Tool call: `get_departure_board(station_code="GLC", num_rows=10)`
3. Tool response: JSON with train departures
4. Final response: Formatted answer about Glasgow Central departures

## Troubleshooting

### Tracing Not Appearing
1. **Check FLASK_DEBUG setting**
   ```bash
   grep FLASK_DEBUG .env
   # Should show: FLASK_DEBUG=true
   ```

2. **Verify startup message**
   ```
   ✓ OpenAI tracing enabled - view traces at https://platform.openai.com/traces
   ```

3. **Check OpenAI account permissions**
   - Ensure API key has access to traces feature
   - Some organizational accounts may have restrictions

### Traces Not Visible in Dashboard
- Wait 30-60 seconds for traces to appear
- Ensure you're logged into correct OpenAI account
- Check that API key matches the logged-in account

## Related Files

- `scotrail_agent.py` - Main agent with tracing implementation
- `app.py` - Flask application (debug mode detection)
- `.env` - Configuration (FLASK_DEBUG setting)

## References

- [OpenAI Traces Dashboard](https://platform.openai.com/traces)
- [OpenAI API Documentation](https://platform.openai.com/docs/)
- [Flask Debug Mode](https://flask.palletsprojects.com/en/latest/config/#DEBUG)
