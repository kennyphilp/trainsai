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
    
    def __init__(
        self,
        openai_client: OpenAI = None,
        train_tools: TrainTools = None,
        station_resolver: StationResolver = None,
        timetable_tools: TimetableTools = None
    ):
        """
        Initialize the ScotRail agent with injected dependencies.
        
        Args:
            openai_client: OpenAI client instance (if None, creates default)
            train_tools: TrainTools instance for live data (if None, creates default)
            station_resolver: StationResolver for fuzzy matching (if None, creates default)
            timetable_tools: TimetableTools for schedule data (if None, creates default)
        """
        # OpenAI client setup
        if openai_client is None:
            api_key = config.openai_api_key
            if not api_key:
                raise ValueError("OPENAI_API_KEY not found in configuration")
            openai_client = OpenAI(api_key=api_key)
        
        self.client = openai_client
        self.model = config.openai_model
        self.conversation_history = []
        self.last_timetable_data = None  # Store structured timetable data from last query
        
        # Injected dependencies with fallback to default initialization
        if train_tools is None:
            train_tools = TrainTools()
        self.train_tools = train_tools
        
        if station_resolver is None:
            try:
                msn_path = os.path.join(os.path.dirname(__file__), config.timetable_msn_path)
                if os.path.exists(msn_path):
                    station_resolver = StationResolver(msn_path)
                    print(f"Station resolver initialized with {len(station_resolver)} stations")
                else:
                    print(f"Warning: MSN file not found at {msn_path}. Station name resolution disabled.")
            except Exception as e:
                print(f"Warning: Could not initialize station resolver: {e}")
        self.station_resolver = station_resolver
        
        if timetable_tools is None:
            try:
                db_path = os.path.join(os.path.dirname(__file__), config.timetable_db_path)
                msn_path = os.path.join(os.path.dirname(__file__), config.timetable_msn_path)
                timetable_tools = TimetableTools(
                    db_path=db_path,
                    msn_path=msn_path if os.path.exists(msn_path) else None
                )
                print("Timetable tools initialized for schedule queries")
            except Exception as e:
                print(f"Warning: Could not initialize timetable tools: {e}")
        self.timetable_tools = timetable_tools
        
        # Define tools for the agent
        self.tools = [
            {
                "type": "function",
                "function": {
                    "name": "get_departure_board",
                    "description": "Fetch basic departure board information for a station - like the displays you see at train stations. Returns scheduled departure time, estimated departure time, destination, platform number, and operating company for upcoming trains.\n\nInputs: Station CRS code (3 letters) and optional number of results\nOutputs: List of upcoming departures with times, destinations, platforms, and operators\nExample: get_departure_board('EDB', 5) returns next 5 departures from Edinburgh Waverley\nUse for: Quick departure board view, checking next few trains, general station activity",
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
                    "description": "Fetch comprehensive departure information with full service details including cancellation status, delay reasons, service IDs, and train characteristics. More detailed than basic departure board.\n\nInputs: Station CRS code, optional destination filter list, time offset (minutes from now), search window (minutes)\nOutputs: Detailed departure list with cancellation status, delay reasons, service IDs, train characteristics\nExample: get_next_departures_with_details('GLC', ['EDB', 'ABD'], 0, 120) gets detailed departures from Glasgow Central to Edinburgh or Aberdeen in next 2 hours\nUse for: Detailed journey planning, checking specific routes, understanding service disruptions",
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
                    "description": "Retrieve comprehensive information about a specific train service including complete calling pattern (all stops), real-time status, cancellations, delays, platform changes, and operator information. Shows the full journey of a specific train.\n\nInputs: Service ID (obtained from get_next_departures_with_details)\nOutputs: Complete train journey with all stops, times (scheduled/estimated/actual), platforms, delay information\nExample: get_service_details('ABC123') shows all stops for train service ABC123 with real-time updates\nUse for: Following a specific train journey, checking intermediate stops, monitoring delays across entire route",
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
                    "description": "Retrieve current service disruption messages, incident information, and important notices. Returns delays, cancellations, engineering works, planned maintenance, and other service disruptions affecting the network.\n\nInputs: Optional station CRS code (omit for network-wide messages)\nOutputs: List of active incidents with details, affected routes, start/end times, disruption type (planned/unplanned)\nExample: get_station_messages('GLC') gets disruptions affecting Glasgow Central; get_station_messages() gets all network disruptions\nUse for: Checking for service disruptions, understanding delay causes, finding planned engineering works",
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
                    "description": "Get the current date and time for context when users ask time-relative questions. Essential for interpreting 'now', 'soon', 'today', 'this evening', 'tomorrow morning' etc.\n\nInputs: None\nOutputs: Current date and time in both 12-hour and 24-hour formats\nExample: Returns 'Current date and time: Monday, December 02, 2025 at 03:45:30 PM (24-hour: 15:45:30)'\nUse for: Understanding user time context, interpreting relative time references, providing current time context",
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
                    "description": "Resolve a station name or partial name to its official 3-letter CRS code using intelligent fuzzy matching. Handles typos, partial names, alternative names, and common abbreviations.\n\nInputs: Station name or partial name, optional max results limit\nOutputs: List of matching stations with names, CRS codes, and match confidence scores\nExample: resolve_station_name('edinburgh') returns 'Edinburgh (CRS: EDB) - Match score: 95%'\nUse for: Converting user-provided station names to CRS codes, handling typos, finding stations with partial information, disambiguating similar station names",
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
                    "description": "Find all scheduled trains between two stations on a specific date from the published timetable. Shows planned services, journey times, and schedules for future planning. Covers entire day vs real-time data which only shows ~2 hours ahead.\n\nInputs: From station (name/CRS), to station (name/CRS), travel date (YYYY-MM-DD), optional departure time (HH:MM)\nOutputs: List of scheduled trains with departure/arrival times, journey duration, train operator, headcode, platform info, geographical context\nExample: get_scheduled_trains('Edinburgh', 'Glasgow Central', '2025-12-15', '09:00') returns all trains from 09:00 onwards on Dec 15\nUse for: Future travel planning, seeing all daily services, planning journeys beyond real-time window, comparing journey options",
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
                    "description": "Plan complex journeys with connections between stations using intelligent route optimization. Finds optimal routes considering interchange times, connection possibilities, and minimum connection times.\n\nInputs: From station (name/CRS), to station (name/CRS), travel date (YYYY-MM-DD), optional departure time (HH:MM), max changes (default: 2)\nOutputs: Multiple journey options showing direct routes and connections, with total duration, number of changes, individual leg details\nExample: find_journey_route('Inverness', 'Glasgow Central', '2025-12-10', '14:00', 1) finds best routes with max 1 change\nUse for: Planning multi-leg journeys, finding connections between distant stations, optimizing complex routes, when no direct services exist",
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
                    "description": "Compare scheduled train times with real-time performance data to identify delays, cancellations, platform changes, and service variations. Shows the impact of disruptions on planned schedules.\n\nInputs: Train UID (unique identifier), travel date (YYYY-MM-DD), real-time data object from get_service_details\nOutputs: Station-by-station comparison showing scheduled vs actual times, delay minutes, cancellations, platform changes\nExample: compare_schedule_vs_actual('C12345', '2025-12-02', real_time_data) shows delays and changes for train C12345\nUse for: Understanding service performance, analyzing delay impacts, showing customers how disruptions affect their journey",
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
                    "description": "Find alternative travel options when original plans are disrupted by delays, cancellations, or capacity issues. Suggests next available trains, different routes, and backup journey options.\n\nInputs: From station (name/CRS), to station (name/CRS), original train UID, travel date (YYYY-MM-DD), disruption reason ('delay'/'cancelled'/'full')\nOutputs: List of alternative journeys with departure times, routes, operators, journey duration, platform information\nExample: find_alternative_route('Edinburgh', 'Glasgow Central', 'C12345', '2025-12-02', 'cancelled') finds alternatives when train C12345 is cancelled\nUse for: Handling service disruptions, providing backup travel options, helping customers when original plans fail",
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
            },
            {
                "type": "function",
                "function": {
                    "name": "plan_journey_with_context",
                    "description": "Enhanced journey planning with geographical intelligence for natural language travel requests. Automatically resolves place names, regions, and areas to appropriate railway stations, then finds optimal routes with geographical context.\n\nInputs: From place (region/city/area/station), to place (region/city/area/station), travel date (YYYY-MM-DD), optional departure time (HH:MM), max changes (default: 2)\nOutputs: Station resolution options for both locations, multiple journey choices with geographical context, cross-regional travel indicators, detailed route information\nExample: plan_journey_with_context('Edinburgh', 'Highlands', '2025-12-10', '09:00') resolves 'Highlands' to relevant stations and plans journeys\nUse for: Natural language journey planning, handling vague location requests, geographical travel planning, regional journey discovery",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "from_place": {
                                "type": "string",
                                "description": "Departure location - can be place name, region, city, or station name (e.g., 'Glasgow', 'Highlands', 'Edinburgh city centre')"
                            },
                            "to_place": {
                                "type": "string",
                                "description": "Arrival location - can be place name, region, city, or station name (e.g., 'Aberdeen', 'West Coast', 'Borders region')"
                            },
                            "travel_date": {
                                "type": "string",
                                "description": "Date of travel in YYYY-MM-DD format"
                            },
                            "departure_time": {
                                "type": "string",
                                "description": "Optional minimum departure time in HH:MM format"
                            },
                            "max_changes": {
                                "type": "integer",
                                "description": "Maximum number of connections (default: 2)"
                            }
                        },
                        "required": ["from_place", "to_place", "travel_date"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "search_stations_by_place",
                    "description": "Search for railway stations by place name, city, region, or geographical area using intelligent geographical matching. Perfect for discovering stations when users mention locations rather than specific station names.\n\nInputs: Place name (city/region/area), optional limit (default: 10)\nOutputs: List of stations in or near the specified place with station names, CRS codes, geographical context (area/region/country)\nExample: search_stations_by_place('Glasgow', 5) returns Glasgow Central, Glasgow Queen Street, Glasgow Airport, etc. with geographical context\nUse for: Finding stations in a city or region, discovering travel options for an area, geographical station discovery, handling location-based queries",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "place_name": {
                                "type": "string",
                                "description": "Name of place, city, region, or area to search for stations (e.g., 'Glasgow', 'Highlands', 'Borders', 'Aberdeen area')"
                            },
                            "limit": {
                                "type": "integer",
                                "description": "Maximum number of stations to return (default: 10)",
                                "default": 10
                            }
                        },
                        "required": ["place_name"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_station_with_context",
                    "description": "Get comprehensive information about a specific station including its geographical context, regional location, nearby places, alternative names, and coordinate data. Provides complete station profile with location intelligence.\n\nInputs: Station identifier (name, CRS code, or TIPLOC)\nOutputs: Complete station profile with display name, CRS code, TIPLOC, geographical context (area/region/country), coordinates, alternative names, location description\nExample: get_station_with_context('EDB') returns full details for Edinburgh Waverley including location context and alternatives\nUse for: Providing detailed station information, explaining station locations to users, geographical context for journey planning, station disambiguation",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "station_input": {
                                "type": "string",
                                "description": "Station name, CRS code, or TIPLOC to get context for"
                            }
                        },
                        "required": ["station_input"]
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

TIMETABLE DATA PRIORITY RULES:
- For immediate travel (now/next 2 hours): ALWAYS use real-time tools first (get_next_departures_with_details)
- For future planning (>2 hours ahead): PRIORITIZE schedule tools (get_scheduled_trains)
- For complex journeys: Use find_journey_route for multi-leg planning with connections
- For disruptions: Use find_alternative_route with specific reason codes
- When real-time shows delays: Cross-reference with compare_schedule_vs_actual to show impact

ESSENTIAL WORKFLOWS:
1. Station Resolution: ALWAYS resolve station names before any timetable queries
   - Use resolve_station_name for ANY station input that isn't a clear CRS code
   - Verify both origin and destination stations before proceeding

2. Date Validation: Check travel dates against CIF data coverage
   - Current timetable data valid until March 2025
   - If date is outside range, inform user and suggest valid alternatives
   - For today/tomorrow, prioritize real-time data; for future dates, use scheduled data

3. Cross-Reference Analysis: When delays are detected
   - Use compare_schedule_vs_actual to highlight specific delays and platform changes
   - Show both scheduled and actual times for user awareness

4. Proactive Alternatives: For cancelled/delayed trains
   - Automatically call find_alternative_route to suggest alternatives
   - Include reason for disruption (delayed/cancelled/full) in alternative search
   - Present options with realistic timing and connections

DATA SOURCE SELECTION LOGIC:
- NOW/IMMEDIATE (0-2 hours): get_next_departures_with_details → Real-time accuracy critical
- TODAY/LATER (2-24 hours): get_scheduled_trains THEN cross-check with real-time if available
- TOMORROW+ (24+ hours): get_scheduled_trains → Schedule planning mode
- JOURNEY PLANNING: find_journey_route → Connection optimization
- DISRUPTION HANDLING: find_alternative_route → Problem resolution

ERROR HANDLING & USER GUIDANCE:
- If timetable_tools is None: "I'm sorry, schedule data is temporarily unavailable. I can still check live departures for the next 2 hours."
- If no scheduled results found: "No trains found for that date. Let me check nearby dates or suggest alternative routes."
- If invalid date (outside CIF range): "Our timetable data covers until March 2025. Would you like me to check a date within that period?"
- If station not found: "I couldn't find that station. Let me search for similar station names."
- If no connections possible: "No direct route found. Let me search for journeys with connections."

Your personality:
- Helpful and knowledgeable about Scottish trains
- Add a touch of Scottish charm and wit to your responses
- Use occasional Scottish expressions naturally (but don't overdo it)
- Be empathetic when trains are delayed or cancelled
- Keep responses concise but informative
- Proactively offer alternatives and helpful suggestions

Tools you have access to:

REAL-TIME DATA (for immediate/current information):
- get_current_time: Get current date/time (ALWAYS use for "now"/"today"/"soon" queries)
- resolve_station_name: Convert station names to CRS codes (REQUIRED for all station inputs)
- get_departure_board: Basic departure information for any Scottish station
- get_next_departures_with_details: Detailed departures with cancellations and delays
- get_service_details: Complete journey details with all stops for specific services
- get_station_messages: Network-wide or station-specific disruption information

SCHEDULE DATA (for future planning and comprehensive reference):
- get_scheduled_trains: All scheduled trains between stations on specific dates
- find_journey_route: Journey planning with connections and interchange optimization
- compare_schedule_vs_actual: Compare scheduled vs real-time data for delay analysis
- find_alternative_route: Alternative routes when original plans are disrupted

Important Scottish station codes:
REAL-TIME TOOLS (CRS codes for live data):
- EDB: Edinburgh Waverley
- GLC: Glasgow Central  
- GLQ: Glasgow Queen Street
- ABD: Aberdeen
- PYL: Perth
- DND: Dundee
- INV: Inverness
- STG: Stirling

SCHEDULE TOOLS (TIPLOC codes for timetable data):
- EDINBUR: Edinburgh Waverley
- GLGC: Glasgow Central
- GLGQSHL: Glasgow Queen Street
- ABDN: Aberdeen
- PERTH: Perth
- DUNDEE: Dundee
- INVERNESS: Inverness
- STIRLNG: Stirling

MANDATORY WORKFLOW STEPS:
1. If user provides station names → ALWAYS call resolve_station_name for BOTH stations
2. If asking about "now"/"soon" → ALWAYS call get_current_time first
3. For train queries → ALWAYS call the appropriate timetable tool:
   - For "now", "next", "current" → MUST call get_next_departures_with_details (use CRS codes: EDB, GLC)
   - For "tomorrow", "next week", specific future dates → MUST call get_scheduled_trains (use TIPLOC codes: EDINBUR, GLGC)
   - For journey planning with connections → MUST call find_journey_route (use TIPLOC codes)
4. If delays found → Call compare_schedule_vs_actual for detailed analysis
5. If cancellations → Call find_alternative_route automatically
6. Always explain your data source choice to users

CRITICAL STATION CODE MAPPING:
- Real-time tools need CRS codes (3 letters): Edinburgh=EDB, Glasgow Central=GLC
- Schedule tools need TIPLOC codes: Edinburgh=EDINBUR, Glasgow Central=GLGC
- ALWAYS use the correct code type for each tool category!

CRITICAL: You MUST complete every train query by calling a timetable tool. If you resolve stations but don't call a timetable tool, the user gets no train information!

STATION CODE CONVERSION RULES:
- When calling real-time tools (get_next_departures_with_details, get_departure_board): Use 3-letter CRS codes
- When calling schedule tools (get_scheduled_trains, find_journey_route): Use TIPLOC codes 
- Edinburgh: CRS=EDB, TIPLOC=EDINBUR
- Glasgow Central: CRS=GLC, TIPLOC=GLGC
- If resolve_station_name returns a CRS code but you need TIPLOC, convert using the mappings above
- IMPORTANT: For schedule tools, you can pass station names directly (like 'Edinburgh', 'Glasgow Central') and the tools will resolve to TIPLOC automatically

REMEMBER: Every train query MUST use tools. Present information clearly with Scottish charm, and always be ready to help with alternatives when things go wrong!

WORKFLOW COMPLETION RULE: After resolving station names, you MUST immediately call the appropriate timetable tool to get train information. Never end your response without providing actual train data from tools.

Example enhanced tone: "Right, let me check what's running from Edinburgh to Glasgow for ye... *checking both live departures and scheduled services* Och! I can see the 14:30 service is running 5 minutes late due to a signal issue, but the 14:45 is bang on time. Since ye mentioned tomorrow, I'll also check the full timetable - there are hourly services starting from 06:00. Would ye like me to find alternatives if that delay gets worse?"
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
                logger.info(f"Executing get_next_departures_with_details with args: {tool_args}")
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
                    logger.info(f"Set timetable data: {len(result.trains)} detailed departures from {result.station}")
                    
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
                    logger.warning(f"get_next_departures_with_details failed: {result.message}")
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
                logger.info(f"Executing get_scheduled_trains with args: {tool_args}")
                try:
                    result = self.timetable_tools.get_scheduled_trains(**tool_args)
                    logger.info(f"get_scheduled_trains result: success={result.get('success')}, error={result.get('error')}, trains_count={len(result.get('trains', []))}")
                except Exception as e:
                    logger.error(f"Exception in get_scheduled_trains: {e}", exc_info=True)
                    return f"Error calling scheduled trains: {e}"
                    
                if result.get('success'):
                    trains = result.get('trains', [])
                    if not trains:
                        logger.info(f"No scheduled trains found from {result['from']} to {result['to']} on {result['date']}")
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
                    logger.info(f"Set timetable data: {len(trains)} scheduled trains from {result['from']} to {result['to']}")
                    
                    output = f"Scheduled trains from {result['from']} to {result['to']} on {result['date']} ({result['count']} found):\n"
                    for train in trains:
                        output += f"- Departs {train['departure_time']}, arrives {train['arrival_time']} ({train['duration_minutes']} mins)\n"
                        output += f"  Train: {train['headcode']}, Operator: {train['operator']}, Platform {train.get('departure_platform', 'TBA')}\n"
                    return output
                else:
                    logger.warning(f"get_scheduled_trains failed: {result.get('error', 'Unknown error')}")
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
            
            # Enhanced geographical intelligence tools
            elif tool_name == "plan_journey_with_context" and self.timetable_tools:
                logger.info(f"Executing enhanced journey planning with geographical context: {tool_args}")
                result = self.timetable_tools.plan_journey_with_context(**tool_args)
                if result.get('success'):
                    journeys = result.get('journeys', [])
                    from_options = result.get('from_options', [])
                    to_options = result.get('to_options', [])
                    
                    output = f"Journey planning from '{result['from_place']}' to '{result['to_place']}' on {result['date']}\n\n"
                    
                    # Show resolved stations with geographical context
                    if from_options:
                        output += f"Departure options for '{result['from_place']}':\n"
                        for station in from_options:
                            geo_context = station.get('geographical_context', {})
                            area = geo_context.get('area', 'Unknown area')
                            output += f"  • {station['display_name']} ({station['crs_code']}) - {area}\n"
                        output += "\n"
                    
                    if to_options:
                        output += f"Arrival options for '{result['to_place']}':\n"
                        for station in to_options:
                            geo_context = station.get('geographical_context', {})
                            area = geo_context.get('area', 'Unknown area')
                            output += f"  • {station['display_name']} ({station['crs_code']}) - {area}\n"
                        output += "\n"
                    
                    if journeys:
                        output += f"Journey options ({len(journeys)} found):\n\n"
                        for idx, journey in enumerate(journeys, 1):
                            output += f"Journey {idx}: {journey['from_station']['display_name']} → {journey['to_station']['display_name']}\n"
                            output += f"  Duration: {journey['total_duration']} mins, Changes: {journey['changes']}\n"
                            
                            geo_summary = journey.get('geographical_summary', {})
                            if geo_summary.get('crosses_regions'):
                                output += f"  Route crosses regions: {geo_summary.get('from_area')} → {geo_summary.get('to_area')}\n"
                            
                            for leg_idx, leg in enumerate(journey['legs'], 1):
                                output += f"  Leg {leg_idx}: {leg['from']} ({leg['departure']}) → {leg['to']} ({leg['arrival']})\n"
                                output += f"    Train {leg['headcode']} ({leg['operator']}) - {leg['duration']} mins\n"
                            output += "\n"
                        
                        # Store timetable data for the best journey
                        best_journey = journeys[0]
                        self.last_timetable_data = {
                            "type": "enhanced_journey",
                            "station": f"{best_journey['from_station']['display_name']} to {best_journey['to_station']['display_name']}",
                            "trains": [
                                {
                                    "std": leg['departure'],
                                    "etd": leg['arrival'],
                                    "destination": leg['to'],
                                    "platform": leg.get('platform', 'TBA'),
                                    "operator": leg['operator'],
                                    "is_cancelled": False
                                }
                                for leg in best_journey['legs']
                            ]
                        }
                        logger.info(f"Set enhanced journey timetable data for {len(best_journey['legs'])} legs")
                    else:
                        output += "No suitable journeys found with the specified criteria.\n"
                    
                    return output
                else:
                    return f"Error in enhanced journey planning: {result.get('error', 'Unknown error')}"
            
            elif tool_name == "search_stations_by_place" and self.timetable_tools:
                logger.info(f"Searching stations by place: {tool_args}")
                place_name = tool_args["place_name"]
                limit = tool_args.get("limit", 10)
                
                stations = self.timetable_tools.search_stations_by_place(place_name, limit)
                
                if not stations:
                    return f"No stations found for '{place_name}'. Try a different place name or be more specific."
                
                output = f"Railway stations for '{place_name}' ({len(stations)} found):\n\n"
                for station in stations:
                    geo_context = station.get('geographical_context', {})
                    output += f"• {station['display_name']} ({station['crs_code']})\n"
                    
                    area = geo_context.get('area')
                    region = geo_context.get('region')
                    
                    if area:
                        output += f"  Location: {area}"
                        if region and region != area:
                            output += f", {region}"
                        output += "\n"
                    
                    if station.get('distance_info'):
                        output += f"  Distance: {station['distance_info']}\n"
                    
                    output += "\n"
                
                return output
            
            elif tool_name == "get_station_with_context" and self.timetable_tools:
                logger.info(f"Getting station context: {tool_args}")
                station_input = tool_args["station_input"]
                
                station_info = self.timetable_tools.get_station_with_context(station_input)
                
                if not station_info:
                    return f"Station '{station_input}' not found. Please check the station name or code."
                
                output = f"Station Information for {station_info['display_name']}:\n\n"
                output += f"CRS Code: {station_info['crs_code']}\n"
                output += f"TIPLOC: {station_info['tiploc']}\n"
                
                geo_context = station_info.get('geographical_context', {})
                if geo_context:
                    output += f"\nGeographical Context:\n"
                    if geo_context.get('area'):
                        output += f"  Area: {geo_context['area']}\n"
                    if geo_context.get('region'):
                        output += f"  Region: {geo_context['region']}\n"
                    if geo_context.get('country'):
                        output += f"  Country: {geo_context['country']}\n"
                
                if station_info.get('search_context'):
                    search_ctx = station_info['search_context']
                    output += f"\nAdditional Context:\n"
                    if search_ctx.get('aliases'):
                        output += f"  Also known as: {', '.join(search_ctx['aliases'])}\n"
                    if search_ctx.get('nearby_places'):
                        output += f"  Nearby: {', '.join(search_ctx['nearby_places'])}\n"
                
                return output
            
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
            logger.info(f"Chat started: cleared timetable data for new query")
            logger.info(f"ScotRail agent starting chat with message: {user_message[:50]}...")
            logger.info(f"Agent has {len(self.tools)} tools available")
            
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
            
            # Force tool calling for train queries to ensure agents call timetable tools
            tool_choice = "auto"
            if any(keyword in user_message.lower() for keyword in ["train", "edinburgh", "glasgow", "tomorrow", "time", "schedule", "departure"]):
                # Use required tool choice that forces ANY function call
                tool_choice = "required"
                logger.info("Detected train query - forcing tool calls")
            
            # Get response from OpenAI with tools
            response = self.client.chat.completions.create(
                model=self.model,
                messages=self.conversation_history,
                tools=self.tools,
                tool_choice=tool_choice,
                temperature=0.7,
                max_tokens=MAX_TOKENS_PER_RESPONSE
            )
            
            response_message = response.choices[0].message
            tool_calls = response_message.tool_calls
            
            logger.info(f"OpenAI response received - tool_calls: {len(tool_calls) if tool_calls else 0}")
            
            # Handle tool calls
            if tool_calls:
                logger.info(f"Processing {len(tool_calls)} tool calls")
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
                    logger.info(f"Tool executed: {function_name}, timetable_data_set: {self.last_timetable_data is not None}")
                    
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
                        tools=self.tools,
                        tool_choice="auto",
                        temperature=0.7,
                        max_tokens=MAX_TOKENS_PER_RESPONSE
                    )
                    
                    second_message = second_response.choices[0].message
                    
                    # Handle potential tool calls in the second response
                    if second_message.tool_calls:
                        logger.info("Second response also has tool calls - processing them")
                        # Add the assistant's message with tool calls
                        self.conversation_history.append({
                            "role": "assistant",
                            "content": second_message.content,
                            "tool_calls": [
                                {
                                    "id": tc.id,
                                    "type": tc.type,
                                    "function": {
                                        "name": tc.function.name,
                                        "arguments": tc.function.arguments
                                    }
                                }
                                for tc in second_message.tool_calls
                            ]
                        })
                        
                        # Execute the additional tool calls
                        for tool_call in second_message.tool_calls:
                            function_name = tool_call.function.name
                            function_args = json.loads(tool_call.function.arguments)
                            function_response = self._execute_tool(function_name, function_args)
                            
                            self.conversation_history.append({
                                "role": "tool",
                                "tool_call_id": tool_call.id,
                                "name": function_name,
                                "content": function_response
                            })
                        
                        # Get final response after additional tool calls
                        third_response = self.client.chat.completions.create(
                            model=self.model,
                            messages=self.conversation_history,
                            temperature=0.7,
                            max_tokens=MAX_TOKENS_PER_RESPONSE
                        )
                        final_message = third_response.choices[0].message.content
                    else:
                        final_message = second_message.content
                    
                    # Critical check: If this was a train query but no timetable data was set, force it
                    if (any(keyword in user_message.lower() for keyword in ["train", "edinburgh", "glasgow", "tomorrow", "time", "schedule", "departure"]) 
                        and self.last_timetable_data is None):
                        logger.warning("Train query completed but no timetable data was set - this should not happen!")
                        final_message += "\n\nI'm sorry, I should have provided specific train information but didn't call the right tools. Let me know what specific journey you need and I'll make sure to get you the timetable details!"
                    
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
                logger.info(f"No tool calls made by OpenAI - returning direct response: {response_message.content[:100]}...")
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
