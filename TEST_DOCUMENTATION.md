# Train Agent Test Suite Documentation

## Overview

The test suite for `train_agent.py` uses the **pytest** framework with comprehensive coverage of all major components. The tests use mocking to isolate units and test them independently.

## Test Structure

### Test File: `test_train_agent.py`

The test suite is organized into 5 main test classes:

#### 1. **TestFormatDepartures** (5 tests)
Tests the `format_departures()` function which formats API responses into readable output.

- `test_format_departures_with_error`: Validates error message display
- `test_format_departures_with_no_trains`: Verifies "no trains" message
- `test_format_departures_with_single_train`: Tests single train formatting
- `test_format_departures_with_multiple_trains`: Tests multiple trains display
- `test_format_departures_output_structure`: Verifies output format (headers, separators)

#### 2. **TestGetDepartureBoard** (8 tests)
Tests the `get_departure_board()` function which fetches data from the Darwin Web Service.

- `test_get_departure_board_success`: Validates successful API call and response parsing
- `test_get_departure_board_no_trains`: Tests when no trains are available
- `test_get_departure_board_exception_handling`: Verifies error handling and recovery
- `test_get_departure_board_station_code_uppercase`: Confirms station codes are uppercased
- `test_get_departure_board_default_num_rows`: Validates default parameter (10)
- `test_get_departure_board_custom_num_rows`: Tests custom num_rows parameter
- `test_get_departure_board_missing_destination`: Tests missing destination handling
- `test_get_departure_board_missing_platform`: Tests missing platform handling

#### 3. **TestTrainAgent** (5 tests)
Tests the agent configuration and initialization.

- `test_agent_exists`: Confirms agent is instantiated
- `test_agent_name`: Validates agent name
- `test_agent_has_instructions`: Verifies agent instructions are present
- `test_agent_has_tools`: Confirms tools are defined
- `test_agent_tool_configuration`: Validates get_departures tool schema

#### 4. **TestEnvironmentVariables** (2 tests)
Tests environment variable handling.

- `test_ldb_token_from_env`: Confirms LDB_TOKEN is read from environment
- `test_wsdl_endpoint_configured`: Validates WSDL endpoint is properly set

#### 5. **TestIntegration** (1 test)
Tests complete workflows combining multiple components.

- `test_format_and_display_flow`: Tests API call → parsing → formatting pipeline

## Running Tests

### Run all tests:
```bash
source venv/bin/activate
pytest test_train_agent.py -v
```

### Run specific test class:
```bash
pytest test_train_agent.py::TestFormatDepartures -v
```

### Run specific test:
```bash
pytest test_train_agent.py::TestFormatDepartures::test_format_departures_with_error -v
```

### Run with coverage:
```bash
pytest test_train_agent.py --cov=train_agent --cov-report=html
```

### Run tests matching pattern:
```bash
pytest test_train_agent.py -k "format" -v
```

## Mocking Strategy

The tests use `unittest.mock` to isolate components:

### Mock Objects Used:
- **Mock**: Generic mock object for simple scenarios
- **MagicMock**: For complex object simulations with method chaining
- **patch**: To replace imports and function implementations

### Example Mocking Pattern:
```python
@patch('train_agent.Client')
def test_get_departure_board_success(self, mock_client_class):
    # Setup mock response
    mock_client = MagicMock()
    mock_client_class.return_value = mock_client
    
    # Configure mock behavior
    mock_response = MagicMock()
    mock_response.locationName = 'Euston'
    mock_client.service.GetDepartureBoard.return_value = mock_response
    
    # Call function being tested
    result = train_agent.get_departure_board('EUS')
    
    # Verify results
    assert result['station'] == 'Euston'
```

## Test Coverage

Current test coverage includes:
- ✅ Format output function with various data scenarios
- ✅ API call with successful response
- ✅ API call with no results
- ✅ Exception handling
- ✅ Parameter validation
- ✅ Missing data handling (graceful degradation)
- ✅ Agent configuration
- ✅ Environment variable loading
- ✅ Integration workflows

## Adding New Tests

### Template for new test:
```python
class TestNewFeature:
    """Tests for new_feature function."""
    
    def test_new_feature_basic(self):
        """Test basic functionality."""
        result = train_agent.new_feature()
        assert result is not None
    
    @patch('train_agent.SomeDependency')
    def test_new_feature_with_mock(self, mock_dependency):
        """Test with mocked dependency."""
        mock_dependency.return_value = "mocked value"
        result = train_agent.new_feature()
        assert result == "mocked value"
```

## Common Issues and Solutions

### Issue: Tests fail with "ModuleNotFoundError: No module named 'train_agent'"
**Solution**: Run tests from project root with virtual environment activated:
```bash
cd /Users/kenny.w.philp/training/myprojects
source venv/bin/activate
pytest
```

### Issue: Mock patches aren't working
**Solution**: Ensure patch decorator targets the import location, not the original module:
```python
# Correct
@patch('train_agent.Client')  # Where it's used

# Incorrect  
@patch('zeep.Client')  # Where it's defined
```

### Issue: Tests hang or timeout
**Solution**: Use `@patch` instead of trying to make actual API calls. Ensure no real network calls are made in tests.

## Test Execution Output Example

```
test_train_agent.py::TestFormatDepartures::test_format_departures_with_error PASSED [  4%]
test_train_agent.py::TestFormatDepartures::test_format_departures_with_no_trains PASSED [  9%]
test_train_agent.py::TestFormatDepartures::test_format_departures_with_single_train PASSED [ 14%]
...
21 passed in 1.51s
```

## Dependencies for Testing

These packages are required for testing (already in requirements.txt):
- `pytest>=9.0.1` - Testing framework
- `pytest-mock>=3.15.1` - Mocking support

## CI/CD Integration

To run tests in CI/CD pipeline:
```bash
pip install -r requirements.txt
pytest test_train_agent.py -v --junit-xml=test-results.xml
```

## Future Improvements

Potential areas for expanded testing:
- 🔄 Async test cases using pytest-asyncio
- 📊 Performance/load testing with pytest-benchmark
- 🐛 Property-based testing with hypothesis
- 🔒 Security testing for token handling
- 🌐 End-to-end tests with real API (with VCR cassettes)
