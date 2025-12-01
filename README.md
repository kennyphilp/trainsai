# Train Departure AI Agent

A helpful, polite AI agent that provides comprehensive information about UK railway services using the OpenAI API and the National Rail Enquiries Darwin Web Service. Features both real-time data and schedule-based queries.

## Features

- 🚂 Get real-time train departure and arrival information
- 📅 Query scheduled trains and plan future journeys
- 🔄 Compare scheduled vs actual times to identify delays
- 🛤️ Find alternative routes when trains are disrupted
- 🤖 Natural language interaction with AI assistant
- 🏛️ Supports all UK railway stations (3267 stations with TIPLOC resolution)
- 💬 Polite and helpful responses with context-aware tool selection
- 🔄 Built on OpenAI GPT-4o-mini with function calling

## Prerequisites

- Python 3.10+
- OpenAI API Key
- National Rail Enquiries (NRE) token (optional - defaults to demo token)
- SQLite3 (included with Python)

## Setup

### 1. Create and Activate Virtual Environment

```bash
python3 -m venv venv
source venv/bin/activate
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure Environment Variables

Create a `.env` file in the project root:

```bash
# Required: Your OpenAI API key
export OPENAI_API_KEY="sk-your-api-key-here"

# Optional: Your NRE token (defaults to demo token if not provided)
export LDB_TOKEN="your-nre-token-here"
```

Or set them directly in your terminal:

```bash
export OPENAI_API_KEY="sk-your-api-key-here"
export LDB_TOKEN="your-nre-token-here"
```

## Usage

### Run the Flask Web Application

```bash
python3 app.py
```

The application will start on `http://127.0.0.1:5001` (or HTTPS if configured).

### Use the Command-Line Agent (Legacy)

```bash
python3 train_agent.py
```

### Example Interactions

```
You: What trains are leaving from Edinburgh to Glasgow in the next hour?
Train Assistant: [Provides real-time departure information with platforms and delays]

You: What trains are scheduled from Edinburgh to Glasgow tomorrow at 9am?
Train Assistant: [Shows scheduled trains from timetable database]

You: Is the 14:30 train from Edinburgh to Glasgow on time?
Train Assistant: [Compares schedule vs real-time data, shows any delays]

You: The 15:00 train is cancelled, what alternatives do I have?
Train Assistant: [Finds alternative routes and next available trains]
```

## Station Codes

Common UK railway station CRS codes:

- `EUS` - Euston (London)
- `VIC` - Victoria (London)
- `LST` - Liverpool Street (London)
- `KX` - King's Cross (London)
- `PAD` - Paddington (London)
- `WAT` - Waterloo (London)
- `MAN` - Manchester Piccadilly
- `BHM` - Birmingham New Street
- `LBA` - Leeds

For a complete list of station codes, visit: https://en.wikipedia.org/wiki/UK_railway_station_code

## API Reference

### Real-Time Data Tools (LDBWS API)

#### get_departures(station_name, num_rows=10, time_offset=0, time_window=120)
Fetches departure board information for a station.

**Parameters:**
- `station_name` (str): Station name or CRS code (e.g., 'Edinburgh', 'EDB')
- `num_rows` (int): Number of departures to retrieve (default: 10)
- `time_offset` (int): Minutes from now to start query (default: 0)
- `time_window` (int): Time window in minutes (default: 120)

#### get_arrivals(station_name, num_rows=10, time_offset=0, time_window=120)
Fetches arrival board information for a station.

#### get_service_details(service_id)
Gets detailed information about a specific train service.

#### get_disruptions()
Retrieves current network disruptions and incidents.

#### get_station_messages(station_name)
Gets important messages for a specific station.

#### resolve_station_name(station_name)
Resolves station names to CRS codes and TIPLOCs.

### Schedule Data Tools (Timetable Database)

#### get_scheduled_trains(from_station, to_station, date, time)
Query scheduled trains between two stations from the timetable database.

**Parameters:**
- `from_station` (str): Origin station name or code
- `to_station` (str): Destination station name or code
- `date` (str): Date in YYYY-MM-DD format
- `time` (str): Time in HH:MM format

#### find_journey_route(from_station, to_station, date, time, max_changes=2)
Plans multi-leg journeys with connections.

#### compare_schedule_vs_actual(train_uid, date, real_time_data)
Compares scheduled times with real-time data to identify delays.

#### find_alternative_route(from_station, to_station, original_train_uid, date, reason)
Finds alternative routes when trains are disrupted.

**Returns:**
```python
{
    'station': 'Station Name',
    'trains': [
        {
            'std': '14:30',           # Scheduled Time of Departure
            'etd': '14:32',           # Estimated Time of Departure
            'destination': 'Destination City',
            'platform': '5',
            'operator': 'Operator Name'
        },
        # ... more trains
    ],
    'message': 'Found X departing trains from Station Name'
}
```

## Architecture

The agent uses the following components:

### Core Components
1. **ScotRailAgent**: OpenAI GPT-4o-mini agent with function calling
2. **Dual Data Sources**:
   - **Real-Time**: National Rail Enquiries Darwin Web Service (LDBWS SOAP API)
   - **Schedule**: SQLite timetable database with CIF format data
3. **Station Resolution**: 3267 UK stations with CRS code and TIPLOC mapping
4. **Web Interface**: Flask application with chat interface
5. **Security**: HTTPS enforcement, token counting, rate limiting

### Data Flow
```
User Query → ScotRailAgent → Tool Selection → Data Source → Response
                    ↓
            Real-Time Tools (immediate/current)
            Schedule Tools (future/planning)
```

### Phase 1: Real-Time Data (Completed)
- LDBWS API integration with 6 tools
- Station name resolution (3267 stations)
- Departure/arrival boards, service details, disruptions

### Phase 2: Schedule Data (Completed)
- SQLite timetable database (schedules, locations, connections)
- CIF parser for ZTR schedule files and ALF connection files
- 4 new tools for schedule queries and journey planning
- Integration with real-time data for delay comparison

## File Structure

```
.
├── app.py                      # Flask web application
├── scotrail_agent.py          # Main AI agent with 10 tools
├── train_tools.py             # Real-time data tools (LDBWS API)
├── timetable_tools.py         # Schedule data tools
├── timetable_database.py      # SQLite ORM for timetable data
├── timetable_parser.py        # CIF/ALF parser and station resolver
├── train_agent.py             # Command-line interface (legacy)
├── traindepart.py             # Original example code
├── models/                    # Pydantic data models
│   ├── departure_board_response.py
│   ├── service_details_response.py
│   └── ...
├── timetable/                 # Timetable data files
│   ├── timetable.db          # SQLite database
│   ├── MSN_V124_111124.msn   # Station reference data
│   └── ...
├── test/                      # Comprehensive test suite
│   ├── test_scotrail_agent.py
│   ├── test_timetable_phase2.py
│   ├── test_train_tools_comprehensive.py
│   └── ...
├── requirements.txt           # Python dependencies
├── pytest.ini                # Test configuration
└── README.md                 # This file
```

## Troubleshooting

### "OPENAI_API_KEY not set"
Set your OpenAI API key:
```bash
export OPENAI_API_KEY="sk-..."
```

### "Unable to fetch departure information"
- Verify the station name or code is correct
- Check your internet connection
- Ensure the NRE service is available
- Try using the full station name (e.g., "Edinburgh" instead of "EDB")

### "Connection timeout"
The NRE service might be temporarily unavailable. Try again in a few moments.

### "Station not found"
Use the `resolve_station_name` tool or check the MSN file for valid station names.

### Database/Schedule Issues
- Ensure `timetable.db` exists (created automatically on first run)
- For schedule queries, CIF data must be loaded into the database
- Check database statistics: `python -c "from timetable_database import TimetableDatabase; db = TimetableDatabase(); print(db.get_statistics())"`

## Testing

Run the comprehensive test suite:

```bash
# Run all tests
pytest test/ -v

# Run with coverage
pytest test/ --cov=. --cov-report=term-missing

# Run specific test file
pytest test/test_timetable_phase2.py -v
```

Current test coverage: **225 tests, 90% coverage**

## References

- [OpenAI API Documentation](https://platform.openai.com/docs/)
- [National Rail Enquiries Darwin Web Service](https://wiki.openraildata.com/index.php/NRE_Darwin_Web_Service_(Public))
- [UK Railway Station Codes](https://en.wikipedia.org/wiki/UK_railway_station_code)
- [CIF Format Specification](https://wiki.openraildata.com/index.php/CIF_File_Format)
- [ATOC Timetable Data](https://www.raildeliverygroup.com/our-services/rail-data/timetable-data.html)

## Future Enhancements

- [ ] Load actual CIF timetable data files
- [ ] Implement connection-based routing with Dijkstra/A* algorithm
- [ ] Add support for real-time journey planning with live delays
- [ ] Implement caching for frequently accessed data
- [ ] Add support for season ticket calculations
- [ ] Enhanced mobile-responsive UI

## License

This project is provided as-is. The original example code follows the GNU General Public License v3.0.

## Notes

- This agent uses a demo NRE token by default. For production use, obtain your own token from National Rail Enquiries.
- The agent requires an OpenAI API key to function.
- Station codes are case-insensitive and the agent resolves names intelligently (e.g., "Edinburgh" → "EDB").
- Real-time data is for immediate queries; schedule data is for future planning.
- The timetable database requires CIF data files to be populated for schedule queries.
- HTTPS enforcement is enabled by default in production mode.

## Development

### Running in Debug Mode

```bash
python3 app.py --debug
```

### Code Quality

- Type hints throughout codebase
- Comprehensive unit tests (225 tests)
- Pydantic models for data validation
- Error handling and logging
- Token counting for cost monitoring
