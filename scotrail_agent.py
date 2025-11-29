"""
ScotRail AI Agent - A helpful and humorous assistant for ScotRail train queries.

This agent uses OpenAI's GPT-4o-mini model to answer questions about ScotRail trains,
including departure times and service interruptions. The agent is designed to be
extended with additional tools in the future.
"""

import os
import json
from datetime import datetime
from openai import OpenAI, APIError, BadRequestError, RateLimitError
from dotenv import load_dotenv
from train_tools import TrainTools
from models import (
    DepartureBoardResponse,
    DetailedDeparturesResponse,
    ServiceDetailsResponse,
    StationMessagesResponse
)

# Load environment variables
load_dotenv()

# Constants
MAX_CONVERSATION_HISTORY = 20  # Maximum number of messages to keep (excluding system prompt)
MAX_TOKENS_PER_RESPONSE = 1000
CONTEXT_WARNING_THRESHOLD = 100000  # Warn when approaching token limit


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
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY not found in environment variables")
        
        self.client = OpenAI(api_key=api_key)
        self.model = "gpt-4o-mini"
        self.conversation_history = []
        
        # Initialize TrainTools for live data access
        self.train_tools = TrainTools()
        
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
            }
        ]
        
        # System prompt that defines the agent's personality and role
        self.system_prompt = f"""You are a helpful and humorous AI assistant specializing in ScotRail trains in Scotland.

Current Date and Time: {datetime.now().strftime('%A, %B %d, %Y at %I:%M %p')}

Your responsibilities:
1. Answer questions about ScotRail train departures and arrival times
2. Provide information about service interruptions, delays, and cancellations
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
- get_current_time: Get the current date and time (use when users ask about "now", "today", "soon", etc.)
- get_departure_board: Get basic departure information for any Scottish station
- get_next_departures_with_details: Get detailed departure info including cancellations and delays
- get_service_details: Get complete journey details with all stops for a specific service
- get_station_messages: Get network-wide or station-specific incident and disruption information

Important Scottish station codes:
- EDB: Edinburgh Waverley
- GLC: Glasgow Central
- GLQ: Glasgow Queen Street
- ABD: Aberdeen
- PYL: Perth
- DND: Dundee
- INV: Inverness
- STG: Stirling

When answering questions:
1. Use the tools to get live data whenever users ask about specific trains or disruptions
2. Always specify which station you're checking (use the CRS code)
3. Present information clearly and add a touch of humor when appropriate
4. If trains are delayed or cancelled, be empathetic and provide helpful alternatives when possible
5. When showing service details, explain the complete journey to help passengers plan

Example tone: "Right, let me check the departures from Edinburgh Waverley for ye... *checks live board* Och, good news! The next train to Glasgow leaves at 14:30 from Platform 12 and it's running on time. That's the fast service, so ye'll be in Glasgow Central in about 50 minutes. Mind the gap!"
"""
        
        # Initialize conversation with system prompt
        self.conversation_history.append({
            "role": "system",
            "content": self.system_prompt
        })
        
        # Track approximate token usage
        self.approximate_tokens = len(self.system_prompt) // 4  # Rough estimate
    
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
            if tool_name == "get_current_time":
                now = datetime.now()
                return f"Current date and time: {now.strftime('%A, %B %d, %Y at %I:%M:%S %p')} (24-hour: {now.strftime('%H:%M:%S')})"
            
            elif tool_name == "get_departure_board":
                result = self.train_tools.get_departure_board(
                    station_code=tool_args["station_code"],
                    num_rows=tool_args.get("num_rows", 10)
                )
                if isinstance(result, DepartureBoardResponse):
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
            
            else:
                return f"Unknown tool: {tool_name}"
                
        except Exception as e:
            return f"Error executing {tool_name}: {str(e)}"
    
    def _truncate_conversation_history(self):
        """
        Truncate conversation history to prevent context overflow.
        Keeps system prompt and most recent messages.
        """
        if len(self.conversation_history) > MAX_CONVERSATION_HISTORY + 1:  # +1 for system prompt
            # Keep system prompt (index 0) and recent messages
            system_prompt = self.conversation_history[0]
            recent_messages = self.conversation_history[-(MAX_CONVERSATION_HISTORY):]
            self.conversation_history = [system_prompt] + recent_messages
            print("\n[Info: Conversation history truncated to manage context length]\n")
    
    def chat(self, user_message: str) -> str:
        """
        Send a message to the agent and get a response.
        
        Args:
            user_message: The user's question or message
            
        Returns:
            The agent's response as a string
        """
        try:
            # Truncate history if needed before adding new message
            self._truncate_conversation_history()
            
            # Add user message to conversation history
            self.conversation_history.append({
                "role": "user",
                "content": user_message
            })
            
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
                        print("\n[Warning: Context limit reached, truncating conversation history...]\n")
                        self._truncate_conversation_history()
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
                self._truncate_conversation_history()
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
