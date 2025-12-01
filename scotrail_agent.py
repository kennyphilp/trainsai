"""
ScotRail AI Agent - A helpful and humorous assistant for ScotRail train queries.

This agent uses OpenAI's GPT-4o-mini model to answer questions about ScotRail trains,
including departure times and service interruptions. The agent is designed to be
extended with additional tools in the future.
"""

import os
import json
import logging
from datetime import datetime
from openai import OpenAI, APIError, BadRequestError, RateLimitError
from dotenv import load_dotenv
from config import get_config
try:
    import tiktoken
    TIKTOKEN_AVAILABLE = True
except ImportError:
    TIKTOKEN_AVAILABLE = False
    print("Warning: tiktoken not available. Token counting will use estimation.")
from train_tools import TrainTools
from timetable_parser import StationResolver
from timetable_tools import TimetableTools
from models import (
    DepartureBoardResponse,
    DetailedDeparturesResponse,
    ServiceDetailsResponse,
    StationMessagesResponse
)

# Load environment variables
load_dotenv()

# Get configuration
config = get_config()

# Configure logging
logger = logging.getLogger(__name__)

# Use configuration constants
MAX_CONVERSATION_HISTORY = config.max_conversation_history
MAX_TOKENS_PER_RESPONSE = config.max_tokens_per_response
CONTEXT_WARNING_THRESHOLD = 100000  # Warn when approaching token limit (for estimation)
MAX_CONTEXT_TOKENS = config.max_context_tokens
SAFETY_MARGIN_TOKENS = config.safety_margin_tokens


class ScotRailAgent:
    """
    An AI agent for answering questions about ScotRail trains.
    
    The agent is helpful and humorous, specializing in:
    - Train departure times
    - Service interruptions and delays
    - General ScotRail information
    
    The agent has access to live train data tools including:
    - get_departure_board: Basic departure information
    - get_next_departures_with_details: Detailed departures with cancellations/delays
    - get_service_details: Full calling pattern for a specific service
    - get_station_messages: Network-wide incident and disruption information
    """
    
    def __init__(self):
        """Initialize the ScotRail agent with OpenAI client and train tools."""
        api_key = config.openai_api_key
        if not api_key:
            raise ValueError("OPENAI_API_KEY not found in configuration")
        
        self.client = OpenAI(api_key=api_key)
        self.model = config.openai_model
        self.conversation_history = []
        self.last_timetable_data = None  # Store structured timetable data from last query
        
        # Initialize TrainTools for live data access
        self.train_tools = TrainTools()
        
        # Initialize StationResolver for fuzzy station name matching
        try:
            msn_path = os.path.join(os.path.dirname(__file__), config.timetable_msn_path)
            if os.path.exists(msn_path):
                self.station_resolver = StationResolver(msn_path)
                print(f"Station resolver initialized with {len(self.station_resolver)} stations")
            else:
                self.station_resolver = None
                print(f"Warning: MSN file not found at {msn_path}. Station name resolution disabled.")
        except Exception as e:
            self.station_resolver = None
            print(f"Warning: Could not initialize station resolver: {e}")
        
        # Initialize TimetableTools for schedule data access
        try:
            db_path = os.path.join(os.path.dirname(__file__), config.timetable_db_path)
            self.timetable_tools = TimetableTools(db_path=db_path, msn_path=msn_path if os.path.exists(msn_path) else None)
            print("Timetable tools initialized for schedule queries")
        except Exception as e:
            self.timetable_tools = None
            print(f"Warning: Could not initialize timetable tools: {e}")
        
        # Define tools for the agent
        self.tools = [
            {
                "type": "function",
                "function": {
                    "name": "get_departure_board",
                    "description": "Fetch basic departure board information for a station. Returns scheduled time, estimated time, destination, platform, and operating company for upcoming trains.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "station_code": {
                                "type": "string",
                                "description": "Three-letter CRS station code (e.g., 'EDB' for Edinburgh, 'GLC' for Glasgow Central, 'ABD' for Aberdeen, 'PYL' for Perth)"
                            },
                            "num_rows": {
                                "type": "integer",
                                "description": "Maximum number of departures to return (default: 10)",
                                "default": 10
                            }
                        },
                        "required": ["station_code"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_next_departures_with_details",
                    "description": "Fetch comprehensive departure information with service details including cancellation status, delay reasons, service IDs, and train characteristics. Supports filtering to specific destinations.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "station_code": {
                                "type": "string",
                                "description": "Three-letter CRS station code (e.g., 'EDB', 'GLC', 'ABD')"
                            },
                            "filter_list": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Optional list of destination CRS codes to filter results. Omit for all departures."
                            },
                            "time_offset": {
                                "type": "integer",
                                "description": "Minutes from now to start search (default: 0)",
                                "default": 0
                            },
                            "time_window": {
                                "type": "integer",
                                "description": "Search window in minutes (default: 120)",
                                "default": 120
                            }
                        },
                        "required": ["station_code"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_service_details",
                    "description": "Retrieve detailed information about a specific train service including the complete calling pattern (all stops), real-time status, cancellations, delays, and operator information. Requires a service_id obtained from get_next_departures_with_details.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "service_id": {
                                "type": "string",
                                "description": "Unique service identifier obtained from get_next_departures_with_details"
                            }
                        },
                        "required": ["service_id"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_station_messages",
                    "description": "Retrieve service disruption messages and incident information. Returns delays, cancellations, engineering works, and other service disruptions. Can filter by station or return all network-wide incidents.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "station_code": {
                                "type": "string",
                                "description": "Optional three-letter CRS code to filter incidents. Omit for network-wide incidents."
                            }
                        },
                        "required": []
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_current_time",
                    "description": "Get the current date and time. Use this to understand what time it is now when users ask about trains leaving 'now', 'soon', 'today', or any time-relative questions.",
                    "parameters": {
                        "type": "object",
                        "properties": {},
                        "required": []
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "resolve_station_name",
                    "description": "Resolve a station name or partial name to its official 3-letter CRS code. Supports fuzzy matching for typos and partial names (e.g., 'edinburgh' → 'EDB', 'glasgow central' → 'GLC'). Use this when users provide station names instead of codes, or when you're unsure of the exact CRS code.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "station_name": {
                                "type": "string",
                                "description": "Station name or partial name to search for (e.g., 'edinburgh', 'glasgow central', 'inverness')"
                            },
                            "max_results": {
                                "type": "integer",
                                "description": "Maximum number of matching stations to return (default: 5)",
                                "default": 5
                            }
                        },
                        "required": ["station_name"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_scheduled_trains",
                    "description": "Find scheduled trains between two stations on a specific date. Use this to see all scheduled services, journey times, and plan ahead. Complements real-time data which only shows ~2 hours ahead.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "from_station": {
                                "type": "string",
                                "description": "Departure station name or CRS code (e.g., 'Edinburgh' or 'EDB')"
                            },
                            "to_station": {
                                "type": "string",
                                "description": "Arrival station name or CRS code (e.g., 'Glasgow' or 'GLC')"
                            },
                            "travel_date": {
                                "type": "string",
                                "description": "Date of travel in YYYY-MM-DD format (e.g., '2025-12-01')"
                            },
                            "departure_time": {
                                "type": "string",
                                "description": "Optional minimum departure time in HH:MM format (e.g., '09:30')"
                            }
                        },
                        "required": ["from_station", "to_station", "travel_date"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "find_journey_route",
                    "description": "Plan a journey with connections between stations. Finds optimal routes considering interchange times and connection possibilities.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "from_station": {
                                "type": "string",
                                "description": "Departure station name or CRS code"
                            },
                            "to_station": {
                                "type": "string",
                                "description": "Arrival station name or CRS code"
                            },
                            "travel_date": {
                                "type": "string",
                                "description": "Date of travel in YYYY-MM-DD format"
                            },
                            "departure_time": {
                                "type": "string",
                                "description": "Minimum departure time in HH:MM format"
                            },
                            "max_changes": {
                                "type": "integer",
                                "description": "Maximum number of connections/changes (default: 2)"
                            }
                        },
                        "required": ["from_station", "to_station", "travel_date"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "compare_schedule_vs_actual",
                    "description": "Compare scheduled train times with real-time data to identify delays, cancellations, and platform changes.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "train_uid": {
                                "type": "string",
                                "description": "Train unique identifier"
                            },
                            "travel_date": {
                                "type": "string",
                                "description": "Date of travel in YYYY-MM-DD format"
                            },
                            "real_time_data": {
                                "type": "object",
                                "description": "Real-time data from LDBWS API (from get_service_details)"
                            }
                        },
                        "required": ["train_uid", "travel_date", "real_time_data"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "find_alternative_route",
                    "description": "Find alternative routes when a train is delayed, cancelled, or full. Suggests next available trains and different connections.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "from_station": {
                                "type": "string",
                                "description": "Departure station name or CRS code"
                            },
                            "to_station": {
                                "type": "string",
                                "description": "Arrival station name or CRS code"
                            },
                            "original_train_uid": {
                                "type": "string",
                                "description": "UID of the disrupted train"
                            },
                            "travel_date": {
                                "type": "string",
                                "description": "Date of travel in YYYY-MM-DD format"
                            },
                            "reason": {
                                "type": "string",
                                "description": "Reason for alternative (e.g., 'delayed', 'cancelled', 'full')"
                            }
                        },
                        "required": ["from_station", "to_station", "travel_date"]
                    }
                }
            }
        ]
        
        # System prompt that defines the agent's personality and role
        self.system_prompt = f"""You are a helpful and humorous AI assistant specializing in ScotRail trains in Scotland.

Current Date and Time: {datetime.now().strftime('%A, %B %d, %Y at %I:%M %p')}

CRITICAL RULES:
- You MUST use the provided tools to fetch ALL train data
- NEVER fabricate, guess, or make up train times, platforms, destinations, or service information
- If a user asks about trains, departures, arrivals, or journeys, you MUST call the appropriate tool
- Only provide information that comes from actual tool responses

Your responsibilities:
1. Answer questions about ScotRail train departures and arrival times USING TOOLS
2. Provide information about service interruptions, delays, and cancellations USING TOOLS
3. Share general information about ScotRail services
4. Be friendly, helpful, and inject appropriate Scottish humor into your responses
5. Be aware of the current time when discussing train schedules

Your personality:
- Helpful and knowledgeable about Scottish trains
- Add a touch of Scottish charm and wit to your responses
- Use occasional Scottish expressions naturally (but don't overdo it)
- Be empathetic when trains are delayed or cancelled
- Keep responses concise but informative
- When users ask about "now" or "soon", use get_current_time to confirm the exact time

Tools you have access to:

REAL-TIME DATA (for immediate/current information):
- get_current_time: Get the current date and time (use when users ask about "now", "today", "soon", etc.)
- resolve_station_name: Convert station names to CRS codes (use when users provide station names or you're unsure of the code)
- get_departure_board: Get basic departure information for any Scottish station
- get_next_departures_with_details: Get detailed departure info including cancellations and delays
- get_service_details: Get complete journey details with all stops for a specific service
- get_station_messages: Get network-wide or station-specific incident and disruption information

SCHEDULE DATA (for future planning and historical reference):
- get_scheduled_trains: Find all scheduled trains between two stations on a specific date (use for planning future journeys)
- find_journey_route: Plan journeys with connections between stations (use when no direct trains available)
- compare_schedule_vs_actual: Compare scheduled times with real-time data to identify delays and platform changes
- find_alternative_route: Find alternative routes when trains are delayed, cancelled, or full

When to use which tools:
- For "now" or "next 2 hours": Use real-time tools (get_next_departures_with_details)
- For "tomorrow" or "next week": Use schedule tools (get_scheduled_trains)
- For journey planning with changes: Use find_journey_route
- When trains are disrupted: Use find_alternative_route

Important Scottish station codes:
- EDB: Edinburgh Waverley
- GLC: Glasgow Central
- GLQ: Glasgow Queen Street
- ABD: Aberdeen
- PYL: Perth
- DND: Dundee
- INV: Inverness
- STG: Stirling
- HOZ: Howwood

When answering questions:
1. ALWAYS call the appropriate tool - NEVER provide train information without using a tool
2. If a user provides a station name (not a CRS code), use resolve_station_name first to find the correct code
3. For ANY query about trains between stations, you MUST use resolve_station_name for both stations, then call get_next_departures_with_details
4. Choose the right data source:
   - For immediate/current info ("now", "next", within 2 hours): MUST use real-time tools (get_next_departures_with_details)
   - For future planning (tomorrow, next week): MUST use schedule tools (get_scheduled_trains)
   - For complex journeys with changes: MUST use find_journey_route
5. Always specify which station you're checking (use the CRS code)
6. Present information clearly and add a touch of humor when appropriate
7. If trains are delayed or cancelled, be empathetic and use find_alternative_route to suggest alternatives
8. When showing service details, explain the complete journey to help passengers plan
9. If comparing scheduled vs actual times, use compare_schedule_vs_actual to highlight delays

REMEMBER: You must CALL TOOLS for every train query. The times and platforms in your responses MUST come from tool results, not from your training data or imagination.

Example tone: "Right, let me check the departures from Edinburgh Waverley for ye... *checks live board* Och, good news! The next train to Glasgow leaves at 14:30 from Platform 12 and it's running on time. That's the fast service, so ye'll be in Glasgow Central in about 50 minutes. Mind the gap!"
"""
        
        # Initialize conversation with system prompt
        self.conversation_history.append({
            "role": "system",
            "content": self.system_prompt
        })
        
        # Initialize token encoder for accurate token counting
        if TIKTOKEN_AVAILABLE:
            try:
                self.encoding = tiktoken.encoding_for_model("gpt-4o-mini")
                logger.info("Token encoder initialized for gpt-4o-mini")
            except KeyError:
                # Fallback to cl100k_base (GPT-4 encoding)
                self.encoding = tiktoken.get_encoding("cl100k_base")
                logger.info("Token encoder initialized with cl100k_base (fallback)")
        else:
            self.encoding = None
            logger.warning("tiktoken not available, using token estimation")
        
        # Token limits
        self.max_context_tokens = MAX_CONTEXT_TOKENS
        self.max_response_tokens = MAX_TOKENS_PER_RESPONSE
        self.safety_margin = SAFETY_MARGIN_TOKENS
    
    def count_tokens(self, messages: list) -> int:
        """
        Count tokens in conversation history using tiktoken.
        
        Args:
            messages: List of message dictionaries
            
        Returns:
            Accurate token count if tiktoken available, otherwise rough estimate
        """
        if not TIKTOKEN_AVAILABLE or self.encoding is None:
            # Fallback to character-based estimation (1 token ≈ 4 characters)
            total_chars = sum(
                len(str(msg.get('content', ''))) +
                len(json.dumps(msg.get('tool_calls', []))) +
                len(str(msg.get('name', '')))
                for msg in messages
            )
            return total_chars // 4
        
        num_tokens = 0
        for message in messages:
            # Every message has metadata overhead (role, etc.)
            num_tokens += 4
            
            # Count tokens in content
            if 'content' in message and message['content']:
                num_tokens += len(self.encoding.encode(str(message['content'])))
            
            # Count tokens in tool calls
            if 'tool_calls' in message and message['tool_calls']:
                for tool_call in message['tool_calls']:
                    num_tokens += len(self.encoding.encode(
                        json.dumps(tool_call['function'])
                    ))
            
            # Count tokens in function results
            if message.get('role') == 'tool':
                content = message.get('content', '')
                num_tokens += len(self.encoding.encode(str(content)))
            
            # Count tokens in name field
            if 'name' in message:
                num_tokens += len(self.encoding.encode(message['name']))
        
        num_tokens += 2  # Every reply is primed with assistant role
        return num_tokens
    
    def should_truncate(self) -> bool:
        """
        Check if conversation should be truncated based on token count.
        
        Returns:
            True if conversation needs truncation, False otherwise
        """
        current_tokens = self.count_tokens(self.conversation_history)
        available = self.max_context_tokens - self.max_response_tokens - self.safety_margin
        
        # Log token usage periodically
        logger.debug(f"Token count: {current_tokens}/{available} "
                    f"(limit: {self.max_context_tokens}, "
                    f"response: {self.max_response_tokens}, "
                    f"safety: {self.safety_margin})")
        
        if current_tokens > available:
            logger.warning(f"Token limit approaching: {current_tokens}/{available} tokens used")
            return True
        
        # Also warn when getting close (80% of available)
        if current_tokens > available * 0.8:
            logger.info(f"Token usage at 80%: {current_tokens}/{available} tokens")
        
        return False
    
    def _truncate_conversation(self) -> None:
        """
        Smart truncation that preserves:
        1. System prompt (always keep)
        2. Recent tool calls and their results (context for LLM)
        3. Most recent user messages
        
        This maintains conversation coherence while staying under token limit.
        """
        if len(self.conversation_history) <= 1:
            logger.debug("No truncation needed: only system prompt exists")
            return  # Only system prompt, nothing to truncate
        
        system_prompt = self.conversation_history[0]
        messages = self.conversation_history[1:]
        
        # Strategy: Keep last 15 messages (preserves ~3-4 turns with tool calls)
        keep_count = 15
        
        if len(messages) <= keep_count:
            logger.debug(f"No truncation needed: {len(messages)} messages <= {keep_count}")
            return  # Already small enough
        
        # Keep the most recent messages
        truncated = [system_prompt] + messages[-keep_count:]
        
        removed_count = len(self.conversation_history) - len(truncated)
        tokens_before = self.count_tokens(self.conversation_history)
        tokens_after = self.count_tokens(truncated)
        
        logger.info(f"Truncated conversation: removed {removed_count} messages, "
                   f"kept {len(truncated)} messages. "
                   f"Tokens: {tokens_before} → {tokens_after} "
                   f"(saved {tokens_before - tokens_after} tokens)")
        
        self.conversation_history = truncated
    
    def _execute_tool(self, tool_name: str, tool_args: dict) -> str:
        """
        Execute a tool function and return the result as a formatted string.
        
        Args:
            tool_name: Name of the tool to execute
            tool_args: Dictionary of arguments for the tool
            
        Returns:
            Formatted string with tool results
        """
        try:
            logger.info(f"Executing tool: {tool_name} with args: {tool_args}")
            
            if tool_name == "get_current_time":
                now = datetime.now()
                return f"Current date and time: {now.strftime('%A, %B %d, %Y at %I:%M:%S %p')} (24-hour: {now.strftime('%H:%M:%S')})"
            
            elif tool_name == "resolve_station_name":
                if not self.station_resolver:
                    return "Station name resolution is not available (timetable data not loaded)."
                
                station_name = tool_args["station_name"]
                max_results = tool_args.get("max_results", 5)
                
                # Try to find matching stations
                results = self.station_resolver.search(station_name, limit=max_results)
                
                if not results:
                    return f"No stations found matching '{station_name}'."
                
                output = f"Stations matching '{station_name}':\n"
                for station, score in results:
                    output += f"- {station.name} (CRS: {station.crs_code}) - Match score: {score}%\n"
                
                # If there's a clear best match (score >= 90), highlight it
                if results[0][1] >= 90:
                    best = results[0][0]
                    output += f"\nBest match: {best.name} (CRS: {best.crs_code})\n"
                
                return output
            
            elif tool_name == "get_departure_board":
                result = self.train_tools.get_departure_board(
                    station_code=tool_args["station_code"],
                    num_rows=tool_args.get("num_rows", 10)
                )
                if isinstance(result, DepartureBoardResponse):
                    # Store structured timetable data
                    self.last_timetable_data = {
                        "type": "departure_board",
                        "station": result.station,
                        "trains": [
                            {
                                "std": train.std,
                                "etd": train.etd,
                                "destination": train.destination,
                                "platform": train.platform,
                                "operator": train.operator
                            }
                            for train in result.trains
                        ]
                    }
                    
                    output = f"Departure board for {result.station}:\n"
                    for train in result.trains:
                        output += f"- {train.std} to {train.destination}, Platform {train.platform}, ETD: {train.etd} ({train.operator})\n"
                    return output
                else:
                    return f"Error: {result.message}"
            
            elif tool_name == "get_next_departures_with_details":
                filter_list = tool_args.get("filter_list")
                result = self.train_tools.get_next_departures_with_details(
                    station_code=tool_args["station_code"],
                    filter_list=filter_list,
                    time_offset=tool_args.get("time_offset", 0),
                    time_window=tool_args.get("time_window", 120)
                )
                if isinstance(result, DetailedDeparturesResponse):
                    # Store structured timetable data
                    self.last_timetable_data = {
                        "type": "detailed_departures",
                        "station": result.station,
                        "trains": [
                            {
                                "std": train.std,
                                "etd": train.etd,
                                "destination": train.destination,
                                "platform": train.platform,
                                "operator": train.operator,
                                "is_cancelled": train.is_cancelled,
                                "cancel_reason": train.cancel_reason,
                                "delay_reason": train.delay_reason,
                                "service_id": train.service_id
                            }
                            for train in result.trains
                        ]
                    }
                    
                    output = f"Detailed departures from {result.station}:\n"
                    for train in result.trains:
                        status = "CANCELLED" if train.is_cancelled else f"ETD: {train.etd}"
                        output += f"- {train.std} to {train.destination}, Platform {train.platform}, {status}"
                        if train.service_id:
                            output += f" [Service ID: {train.service_id}]"
                        if train.cancel_reason:
                            output += f"\n  Cancellation: {train.cancel_reason}"
                        if train.delay_reason:
                            output += f"\n  Delay: {train.delay_reason}"
                        output += f" (Operator: {train.operator})\n"
                    return output
                else:
                    return f"Error: {result.message}"
            
            elif tool_name == "get_service_details":
                result = self.train_tools.get_service_details(service_id=tool_args["service_id"])
                if isinstance(result, ServiceDetailsResponse):
                    output = f"Service Details for {tool_args['service_id']}:\n"
                    output += f"Route: {result.origin} → {result.destination}\n"
                    output += f"Operator: {result.operator}\n"
                    if result.is_cancelled:
                        output += f"STATUS: CANCELLED\n"
                        if result.cancel_reason:
                            output += f"Reason: {result.cancel_reason}\n"
                    output += f"\nCalling at ({len(result.calling_points)} stops):\n"
                    for stop in result.calling_points:
                        time = stop.actual_time or stop.estimated_time or stop.scheduled_time
                        cancelled = " [CANCELLED]" if stop.is_cancelled else ""
                        output += f"- {stop.location_name} ({stop.crs}): {time}, Platform {stop.platform or 'TBA'}{cancelled}\n"
                    return output
                else:
                    return f"Error: {result.message}"
            
            elif tool_name == "get_station_messages":
                station_code = tool_args.get("station_code")
                result = self.train_tools.get_station_messages(station_code=station_code)
                if isinstance(result, StationMessagesResponse):
                    if not result.messages:
                        return "No service disruptions or incidents reported."
                    output = f"Service disruptions and incidents ({len(result.messages)} found):\n"
                    for incident in result.messages:
                        work_type = "Planned Engineering Work" if incident.is_planned else "Unplanned Disruption"
                        output += f"\n[{work_type}] {incident.title or 'No title'}\n"
                        if incident.message:
                            output += f"Details: {incident.message[:200]}...\n" if len(incident.message) > 200 else f"Details: {incident.message}\n"
                        if incident.routes_affected:
                            output += f"Routes: {incident.routes_affected}\n"
                        if incident.start_time:
                            output += f"Start: {incident.start_time}\n"
                        if incident.end_time:
                            output += f"Expected end: {incident.end_time}\n"
                    return output
                else:
                    return f"Error: {result.message}"
            
            # Timetable tools (schedule data)
            elif tool_name == "get_scheduled_trains" and self.timetable_tools:
                result = self.timetable_tools.get_scheduled_trains(**tool_args)
                if result.get('success'):
                    trains = result.get('trains', [])
                    if not trains:
                        return f"No scheduled trains found from {result['from']} to {result['to']} on {result['date']}."
                    
                    # Store structured timetable data
                    self.last_timetable_data = {
                        "type": "scheduled_trains",
                        "station": f"{result['from']} to {result['to']}",
                        "trains": [
                            {
                                "std": train['departure_time'],
                                "etd": train['arrival_time'],
                                "destination": result['to'],
                                "platform": train.get('departure_platform', 'TBA'),
                                "operator": train['operator'],
                                "is_cancelled": False
                            }
                            for train in trains
                        ]
                    }
                    
                    output = f"Scheduled trains from {result['from']} to {result['to']} on {result['date']} ({result['count']} found):\n"
                    for train in trains:
                        output += f"- Departs {train['departure_time']}, arrives {train['arrival_time']} ({train['duration_minutes']} mins)\n"
                        output += f"  Train: {train['headcode']}, Operator: {train['operator']}, Platform {train.get('departure_platform', 'TBA')}\n"
                    return output
                else:
                    return f"Error: {result.get('error', 'Unknown error')}"
            
            elif tool_name == "find_journey_route" and self.timetable_tools:
                result = self.timetable_tools.find_journey_route(**tool_args)
                if result.get('success'):
                    routes = result.get('routes', [])
                    if not routes:
                        return f"No routes found from {result['from']} to {result['to']} on {result['date']}."
                    
                    # Store structured timetable data from first route (most relevant)
                    if routes:
                        first_route = routes[0]
                        self.last_timetable_data = {
                            "type": "journey_route",
                            "station": f"{result['from']} to {result['to']}",
                            "trains": [
                                {
                                    "std": leg['departure'],
                                    "etd": leg['arrival'],
                                    "destination": leg['to'],
                                    "platform": leg.get('departure_platform', 'TBA'),
                                    "operator": leg['operator'],
                                    "is_cancelled": False
                                }
                                for leg in first_route['legs']
                            ]
                        }
                    
                    output = f"Journey options from {result['from']} to {result['to']} on {result['date']} ({result['count']} found):\n\n"
                    for idx, route in enumerate(routes, 1):
                        output += f"Route {idx} ({route['type']}, {route['total_duration']} mins, {route['changes']} changes):\n"
                        for leg_idx, leg in enumerate(route['legs'], 1):
                            output += f"  Leg {leg_idx}: {leg['from']} → {leg['to']}\n"
                            output += f"  Train {leg['headcode']} ({leg['operator']}), departs {leg['departure']}, arrives {leg['arrival']}\n"
                        output += "\n"
                    return output
                else:
                    return f"Error: {result.get('error', 'Unknown error')}"
            
            elif tool_name == "compare_schedule_vs_actual" and self.timetable_tools:
                result = self.timetable_tools.compare_schedule_vs_actual(**tool_args)
                if result.get('success'):
                    comparison = result.get('comparison', [])
                    output = f"Schedule vs Actual for train {result['train_uid']} on {result['date']}:\n"
                    for stop in comparison:
                        output += f"\n{stop['station']}:\n"
                        output += f"  Scheduled: arr {stop.get('scheduled_arrival', 'N/A')}, dep {stop.get('scheduled_departure', 'N/A')}\n"
                        if stop.get('actual_arrival') or stop.get('actual_departure'):
                            output += f"  Actual: arr {stop.get('actual_arrival', 'N/A')}, dep {stop.get('actual_departure', 'N/A')}\n"
                        if stop.get('delay_minutes', 0) > 0:
                            output += f"  DELAYED: {stop['delay_minutes']} minutes\n"
                        if stop.get('cancelled'):
                            output += f"  STATUS: CANCELLED\n"
                        if stop.get('platform_changed'):
                            output += f"  Platform changed: {stop['scheduled_platform']} → {stop['actual_platform']}\n"
                    return output
                else:
                    return f"Error: {result.get('error', 'Unknown error')}"
            
            elif tool_name == "find_alternative_route" and self.timetable_tools:
                result = self.timetable_tools.find_alternative_route(**tool_args)
                if result.get('success'):
                    alternatives = result.get('alternatives', [])
                    if not alternatives:
                        return f"No alternative routes found for the disrupted train {result['original_train']}."
                    output = f"Alternative routes (reason: {result['reason']}, {result['count']} found):\n\n"
                    for idx, alt in enumerate(alternatives, 1):
                        output += f"Alternative {idx}:\n"
                        output += f"  Train {alt['headcode']} ({alt['operator']})\n"
                        output += f"  Departs {alt['departure_time']}, arrives {alt['arrival_time']} ({alt['duration_minutes']} mins)\n"
                        output += f"  Platform {alt.get('departure_platform', 'TBA')}\n\n"
                    return output
                else:
                    return f"Error: {result.get('error', 'Unknown error')}"
            
            else:
                return f"Unknown tool: {tool_name}"
                
        except Exception as e:
            return f"Error executing {tool_name}: {str(e)}"
    
    def chat(self, user_message: str) -> str:
        """
        Send a message to the agent and get a response.
        
        Args:
            user_message: The user's question or message
            
        Returns:
            The agent's response as a string
        """
        try:
            # Clear previous timetable data
            self.last_timetable_data = None
            
            # Add user message to conversation history
            self.conversation_history.append({
                "role": "user",
                "content": user_message
            })
            
            # Proactive truncation check based on token count
            if self.should_truncate():
                logger.warning("Token limit approaching, truncating conversation proactively")
                self._truncate_conversation()
            
            # Log current token usage
            current_tokens = self.count_tokens(self.conversation_history)
            logger.info(f"Chat request - Current tokens: {current_tokens}, "
                       f"Messages: {len(self.conversation_history)}, "
                       f"Using {'tiktoken' if TIKTOKEN_AVAILABLE else 'estimation'}")
            
            # Get response from OpenAI with tools
            response = self.client.chat.completions.create(
                model=self.model,
                messages=self.conversation_history,
                tools=self.tools,
                tool_choice="auto",
                temperature=0.7,
                max_tokens=MAX_TOKENS_PER_RESPONSE
            )
            
            response_message = response.choices[0].message
            tool_calls = response_message.tool_calls
            
            # Handle tool calls
            if tool_calls:
                # Add assistant's tool call message to history
                self.conversation_history.append({
                    "role": "assistant",
                    "content": response_message.content,
                    "tool_calls": [
                        {
                            "id": tc.id,
                            "type": tc.type,
                            "function": {
                                "name": tc.function.name,
                                "arguments": tc.function.arguments
                            }
                        }
                        for tc in tool_calls
                    ]
                })
                
                # Execute each tool call
                for tool_call in tool_calls:
                    function_name = tool_call.function.name
                    function_args = json.loads(tool_call.function.arguments)
                    
                    # Execute the tool
                    function_response = self._execute_tool(function_name, function_args)
                    
                    # Add tool response to history
                    self.conversation_history.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "name": function_name,
                        "content": function_response
                    })
                
                # Get final response with tool results
                try:
                    second_response = self.client.chat.completions.create(
                        model=self.model,
                        messages=self.conversation_history,
                        temperature=0.7,
                        max_tokens=MAX_TOKENS_PER_RESPONSE
                    )
                    
                    final_message = second_response.choices[0].message.content
                    
                    # Add final assistant response to history
                    self.conversation_history.append({
                        "role": "assistant",
                        "content": final_message
                    })
                    
                    return final_message
                
                except BadRequestError as e:
                    if "context_length_exceeded" in str(e):
                        # Context overflow - truncate and retry once
                        logger.warning("Context limit exceeded, truncating conversation history and retrying")
                        self._truncate_conversation()
                        # Try one more time with truncated history
                        retry_response = self.client.chat.completions.create(
                            model=self.model,
                            messages=self.conversation_history,
                            temperature=0.7,
                            max_tokens=MAX_TOKENS_PER_RESPONSE
                        )
                        final_message = retry_response.choices[0].message.content
                        self.conversation_history.append({
                            "role": "assistant",
                            "content": final_message
                        })
                        return final_message
                    else:
                        raise
            
            else:
                # No tool calls, just return the response
                assistant_message = response_message.content
                
                # Add assistant response to conversation history
                self.conversation_history.append({
                    "role": "assistant",
                    "content": assistant_message
                })
                
                return assistant_message
        
        except BadRequestError as e:
            if "context_length_exceeded" in str(e):
                # Remove the user message we just added
                self.conversation_history.pop()
                # Truncate history
                logger.warning("Context length exceeded on initial request, truncating")
                self._truncate_conversation()
                # Add user message back
                self.conversation_history.append({
                    "role": "user",
                    "content": user_message
                })
                return "Och, sorry! The conversation got a wee bit too long there. I've cleared some of the older messages. Could ye ask that again?"
            else:
                error_msg = str(e)
                return f"Sorry, I encountered an error with the AI service: {error_msg}. Please try again."
        
        except RateLimitError:
            return "Och, I'm getting too many requests right now! Could ye give me a moment and try again?"
        
        except APIError as e:
            return f"Sorry, there was a problem connecting to the AI service: {str(e)}. Please try again in a moment."
        
        except Exception as e:
            return f"Och no! Something unexpected happened: {str(e)}. Please try again."
    
    def reset_conversation(self):
        """Reset the conversation history, keeping only the system prompt."""
        self.conversation_history = [self.conversation_history[0]]
        self.approximate_tokens = len(self.system_prompt) // 4
    
    def get_conversation_history(self) -> list:
        """
        Get the full conversation history.
        
        Returns:
            List of conversation messages (excluding system prompt)
        """
        return self.conversation_history[1:]  # Exclude system prompt


def main():
    """
    Demo the ScotRail agent with some example queries.
    """
    print("=" * 70)
    print("ScotRail AI Agent Demo")
    print("=" * 70)
    print()
    
    try:
        agent = ScotRailAgent()
    except ValueError as e:
        print(f"Error: {e}")
        print("Please ensure OPENAI_API_KEY is set in your .env file.")
        return
    except Exception as e:
        print(f"Failed to initialize agent: {e}")
        return
    
    # Example queries to demonstrate the agent with live tools
    example_queries = [
        "When is the next train from Edinburgh to Glasgow?",
        "Are there any delays on trains from Glasgow Central right now?",
        "Can you show me all the stops for the next train from Edinburgh?",
    ]
    
    for i, query in enumerate(example_queries, 1):
        print(f"Query {i}: {query}")
        print("-" * 70)
        response = agent.chat(query)
        print(f"Agent: {response}")
        print()
        print("=" * 70)
        print()
    
    # Interactive mode
    print("\nInteractive Mode - Type 'quit' to exit, 'reset' to start new conversation")
    print("=" * 70)
    print()
    
    while True:
        user_input = input("You: ").strip()
        
        if user_input.lower() == 'quit':
            print("Thanks for chatting! Safe travels on ScotRail!")
            break
        
        if user_input.lower() == 'reset':
            agent.reset_conversation()
            print("Conversation reset. Starting fresh!")
            continue
        
        if not user_input:
            continue
        
        try:
            response = agent.chat(user_input)
            print(f"\nAgent: {response}\n")
        except KeyboardInterrupt:
            print("\n\nInterrupted. Type 'quit' to exit or continue chatting.")
            continue
        except Exception as e:
            print(f"\nError: {e}\n")
            print("Please try again or type 'quit' to exit.\n")


if __name__ == "__main__":
    main()
