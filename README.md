# Train Departure AI Agent

A helpful, polite AI agent that provides information about train departures from UK railway stations using the OpenAI Agents SDK and the National Rail Enquiries Darwin Web Service.

## Features

- 🚂 Get real-time train departure information
- 🤖 Natural language interaction with AI assistant
- 🏛️ Supports all UK railway stations
- 💬 Polite and helpful responses
- 🔄 Built on OpenAI Agents SDK

## Prerequisites

- Python 3.10+
- OpenAI API Key
- National Rail Enquiries (NRE) token (optional - defaults to demo token)

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

Run the train agent:

```bash
python3 train_agent.py
```

### Example Interactions

```
You: What trains are leaving from Euston in the next hour?
Train Assistant: [Provides detailed departure information]

You: Show me departures from Victoria
Train Assistant: [Lists trains from Victoria station]

You: What's the next train to Manchester?
Train Assistant: [Shows fastest departures to Manchester]
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

### get_departures(station_code, num_rows=10)

Fetches departure board information for a station.

**Parameters:**
- `station_code` (str): UK rail station CRS code (e.g., 'EUS', 'VIC')
- `num_rows` (int): Number of departures to retrieve (default: 10)

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

1. **Agent**: OpenAI Agents SDK agent with custom instructions
2. **Tools**: `get_departures` function to fetch train data
3. **Data Source**: National Rail Enquiries Darwin Web Service (SOAP API via Zeep)
4. **LLM**: OpenAI GPT-4 or GPT-3.5 Turbo

## File Structure

```
.
├── train_agent.py          # Main agent implementation
├── traindepart.py          # Original example code
├── requirements.txt        # Python dependencies
├── README.md              # This file
└── .env                   # Environment variables (not committed)
```

## Troubleshooting

### "OPENAI_API_KEY not set"
Set your OpenAI API key:
```bash
export OPENAI_API_KEY="sk-..."
```

### "Unable to fetch departure information"
- Verify the station code is correct
- Check your internet connection
- Ensure the NRE service is available

### "Connection timeout"
The NRE service might be temporarily unavailable. Try again in a few moments.

## References

- [OpenAI Agents SDK Documentation](https://openai.github.io/openai-agents-python/)
- [National Rail Enquiries Darwin Web Service](https://wiki.openraildata.com/index.php/NRE_Darwin_Web_Service_(Public))
- [UK Railway Station Codes](https://en.wikipedia.org/wiki/UK_railway_station_code)

## License

This project is provided as-is. The original example code follows the GNU General Public License v3.0.

## Notes

- This agent uses a demo NRE token by default. For production use, obtain your own token.
- The agent requires an OpenAI API key to function.
- Station codes are case-insensitive but should be provided in uppercase format.
