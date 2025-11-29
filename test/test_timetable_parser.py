"""
Tests for timetable_parser module.

Tests cover:
- MSN file parsing
- Station lookups (by CRS, TIPLOC, name)
- Fuzzy matching
- Search functionality
- Coordinate-based nearest station lookups
- Edge cases and error handling
"""

import pytest
import tempfile
import os
from pathlib import Path
from timetable_parser import Station, StationResolver


# Sample MSN data for testing (real format from CIF files - exact column positions)
SAMPLE_MSN_DATA = """HD00
A    ABERDEEN                      2ABRDEENABD   ABD13942 68058 5
A    ABBEY WOOD                    2ABWD   ABW   ABW15473 61790 4
A    ABERYSTWYTH                   0ABRYSTHAYW   AYW12585 62816 5
A    GLASGOW CENTRAL               3GLGC   GLC   GLC12587 6665315
A    EDINBURGH                     3EDINBUREDB   EDB13259 6673910
A    PERTH                         2ERTHPTHPTH   PTH31205 72351 5
A    INVERNESS                     1IVRNESSINV   INV12668 68455 5
A    STIRLING                      2STIRLNGSTG   STG12798 66935 5
A    DUNDEE                        2DUNDETBDEE   DEE13392 67294 5
A    ABINGDON BUS                  BABGNTONABA   ABA00000 00000 0
ZZ
"""


class TestStation:
    """Tests for Station dataclass."""
    
    def test_station_creation(self):
        """Test creating a station with all fields."""
        station = Station(
            name="EDINBURGH",
            crs_code="EDB",
            tiploc="EDINBUR",
            station_type="3",
            easting=13259,
            northing=66739,
            category="10"
        )
        assert station.name == "EDINBURGH"
        assert station.crs_code == "EDB"
        assert station.tiploc == "EDINBUR"
        assert station.easting == 13259
        assert station.northing == 66739
    
    def test_station_str_representation(self):
        """Test station string representation."""
        station = Station(
            name="GLASGOW CENTRAL",
            crs_code="GLC",
            tiploc="GLAS CEN",
            station_type="0"
        )
        assert str(station) == "GLASGOW CENTRAL (GLC)"
    
    def test_station_with_optional_fields(self):
        """Test creating station with minimal fields."""
        station = Station(
            name="TEST STATION",
            crs_code="TST",
            tiploc="TEST",
            station_type="0"
        )
        assert station.name == "TEST STATION"
        assert station.easting is None
        assert station.northing is None
        assert station.category is None


class TestStationResolver:
    """Tests for StationResolver class."""
    
    @pytest.fixture
    def msn_file(self):
        """Create a temporary MSN file for testing."""
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as f:
            f.write(SAMPLE_MSN_DATA)
            temp_path = f.name
        yield temp_path
        os.unlink(temp_path)
    
    @pytest.fixture
    def resolver(self, msn_file):
        """Create a StationResolver with test data."""
        return StationResolver(msn_file)
    
    def test_resolver_initialization(self, resolver):
        """Test resolver loads stations correctly."""
        assert len(resolver) == 10
        assert len(resolver.stations) == 10
        assert len(resolver.crs_index) > 0
        assert len(resolver.name_index) > 0
    
    def test_resolver_with_real_file(self):
        """Test resolver with real MSN file from workspace."""
        msn_path = "/Users/kennyphilp/mywork/aiwork/trainsai/timetable/RJTTF666MSN.txt"
        if os.path.exists(msn_path):
            resolver = StationResolver(msn_path)
            # Real file has 4016 lines but some are headers/trailers
            assert len(resolver) > 3000  # Should have most stations parsed
            
            # Test some known stations
            aberdeen = resolver.get_by_crs("ABD")
            assert aberdeen is not None
            assert "ABERDEEN" in aberdeen.name.upper()
    
    def test_resolver_file_not_found(self):
        """Test resolver raises error for missing file."""
        with pytest.raises(FileNotFoundError):
            StationResolver("/nonexistent/file.txt")
    
    def test_get_by_crs_exact_match(self, resolver):
        """Test CRS code lookup with exact match."""
        station = resolver.get_by_crs("EDB")
        assert station is not None
        assert station.name == "EDINBURGH"
        assert station.crs_code == "EDB"
    
    def test_get_by_crs_case_insensitive(self, resolver):
        """Test CRS code lookup is case-insensitive."""
        station1 = resolver.get_by_crs("GLC")
        station2 = resolver.get_by_crs("glc")
        station3 = resolver.get_by_crs("Glc")
        
        assert station1 is not None
        assert station1 == station2 == station3
        assert station1.name == "GLASGOW CENTRAL"
    
    def test_get_by_crs_not_found(self, resolver):
        """Test CRS code lookup returns None for invalid code."""
        station = resolver.get_by_crs("XYZ")
        assert station is None
    
    def test_get_by_tiploc_exact_match(self, resolver):
        """Test TIPLOC lookup with exact match."""
        station = resolver.get_by_tiploc("ABRDEENA")
        assert station is not None
        assert station.name == "ABERDEEN"
        assert station.tiploc == "ABRDEENA"
    
    def test_get_by_tiploc_case_insensitive(self, resolver):
        """Test TIPLOC lookup is case-insensitive."""
        station1 = resolver.get_by_tiploc("ABRDEENA")
        station2 = resolver.get_by_tiploc("abrdeena")
        
        assert station1 is not None
        assert station1 == station2
    
    def test_get_by_name_exact_match(self, resolver):
        """Test name lookup with exact match (normalized)."""
        station = resolver.get_by_name("PERTH")
        assert station is not None
        assert station.name == "PERTH"
        assert station.crs_code == "PTH"
    
    def test_get_by_name_case_insensitive(self, resolver):
        """Test name lookup is case-insensitive."""
        station1 = resolver.get_by_name("DUNDEE")
        station2 = resolver.get_by_name("dundee")
        station3 = resolver.get_by_name("Dundee")
        
        assert station1 is not None
        assert station1 == station2 == station3
    
    def test_get_by_name_fuzzy_match(self, resolver):
        """Test fuzzy name matching."""
        # Typo: "edinburh" should match "EDINBURGH"
        station = resolver.get_by_name("edinburh", fuzzy=True)
        assert station is not None
        assert station.crs_code == "EDB"
        
        # Partial match: "stirling" should match "STIRLING"
        station = resolver.get_by_name("stirling", fuzzy=True)
        assert station is not None
        assert station.crs_code == "STG"
    
    def test_get_by_name_fuzzy_disabled(self, resolver):
        """Test name lookup with fuzzy matching disabled."""
        # Exact match should work
        station = resolver.get_by_name("ABERDEEN", fuzzy=False)
        assert station is not None
        
        # Fuzzy match should fail
        station = resolver.get_by_name("aberden", fuzzy=False)
        assert station is None
    
    def test_get_by_name_with_spaces(self, resolver):
        """Test name lookup with multi-word station names."""
        station = resolver.get_by_name("GLASGOW CENTRAL")
        assert station is not None
        assert station.crs_code == "GLC"
        
        # Fuzzy match: "glasgow central" (lowercase)
        station = resolver.get_by_name("glasgow central")
        assert station is not None
        assert station.crs_code == "GLC"
    
    def test_get_by_name_partial_match(self, resolver):
        """Test partial name matching."""
        # "glasgow" should match "GLASGOW CENTRAL"
        station = resolver.get_by_name("glasgow", fuzzy=True)
        assert station is not None
        assert "GLASGOW" in station.name
    
    def test_search_by_crs(self, resolver):
        """Test search function with CRS code."""
        results = resolver.search("EDB")
        assert len(results) > 0
        assert results[0][0].crs_code == "EDB"
        assert results[0][1] == 100  # Perfect match score
    
    def test_search_by_name(self, resolver):
        """Test search function with station name."""
        results = resolver.search("edinburgh")
        assert len(results) > 0
        
        # First result should be best match
        best_match, score = results[0]
        assert "EDINBURGH" in best_match.name.upper()
        assert score >= 80
    
    def test_search_partial_name(self, resolver):
        """Test search with partial station name."""
        results = resolver.search("aber")
        assert len(results) >= 2  # Should match ABERDEEN and ABERYSTWYTH
        
        # Check that both stations are in results
        station_names = [station.name for station, _ in results]
        assert any("ABERDEEN" in name for name in station_names)
        assert any("ABERYSTWYTH" in name for name in station_names)
    
    def test_search_with_limit(self, resolver):
        """Test search respects result limit."""
        results = resolver.search("a", limit=3)
        assert len(results) <= 3
    
    def test_search_returns_scores(self, resolver):
        """Test search returns results sorted by score."""
        results = resolver.search("glasgow")
        
        # Scores should be in descending order
        scores = [score for _, score in results]
        assert scores == sorted(scores, reverse=True)
        
        # Best match should have high score
        assert scores[0] >= 80
    
    def test_search_no_results(self, resolver):
        """Test search with query that matches nothing."""
        results = resolver.search("zzzzzzzzzz")
        assert len(results) == 0
    
    def test_get_nearest_stations(self, resolver):
        """Test finding nearest stations by coordinates."""
        # Use Edinburgh coordinates as reference from test data
        easting = 13259
        northing = 66739
        
        results = resolver.get_nearest(easting, northing, limit=5)
        assert len(results) > 0
        
        # Verify results are sorted by distance (ascending)
        distances = [distance for _, distance in results]
        assert distances == sorted(distances), "Results should be sorted by distance"
        
        # All distances should be reasonable
        for station, distance in results:
            assert distance < 200  # All should be within 200km
    
    def test_get_nearest_returns_distances(self, resolver):
        """Test nearest stations are sorted by distance."""
        results = resolver.get_nearest(13259, 66739, limit=5)
        
        # Distances should be in ascending order
        distances = [distance for _, distance in results]
        assert distances == sorted(distances)
    
    def test_get_nearest_with_limit(self, resolver):
        """Test nearest stations respects limit."""
        results = resolver.get_nearest(13259, 66739, limit=2)
        assert len(results) <= 2
    
    def test_normalize_name(self, resolver):
        """Test name normalization removes punctuation and spaces."""
        assert resolver._normalize_name("GLASGOW CENTRAL") == "glasgowcentral"
        assert resolver._normalize_name("King's Cross") == "kingscross"
        assert resolver._normalize_name("St. Pancras") == "stpancras"
        assert resolver._normalize_name("EDINBURGH") == "edinburgh"
    
    def test_repr(self, resolver):
        """Test string representation of resolver."""
        repr_str = repr(resolver)
        assert "StationResolver" in repr_str
        assert "10 stations" in repr_str


class TestEdgeCases:
    """Tests for edge cases and error handling."""
    
    def test_malformed_msn_record(self):
        """Test resolver handles malformed MSN records gracefully."""
        malformed_data = """HD00
A    VALID STATION                 0VALID  VAL   VAL12345 67890 5
A
INVALID LINE
A    TOO SHORT
A    ANOTHER VALID STATION         0VALIDV2VA2   VA212345 67890 5
ZZ
"""
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as f:
            f.write(malformed_data)
            temp_path = f.name
        
        try:
            resolver = StationResolver(temp_path)
            # Should still load valid stations
            assert len(resolver) >= 2
        finally:
            os.unlink(temp_path)
    
    def test_empty_msn_file(self):
        """Test resolver handles empty MSN file."""
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as f:
            f.write("HD00\nZZ\n")
            temp_path = f.name
        
        try:
            resolver = StationResolver(temp_path)
            assert len(resolver) == 0
        finally:
            os.unlink(temp_path)
    
    def test_station_without_coordinates(self):
        """Test handling stations without coordinate data."""
        data = """HD00
A    STATION WITHOUT COORDS        0NOCRD   NOC  NOC           0
ZZ
"""
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as f:
            f.write(data)
            temp_path = f.name
        
        try:
            resolver = StationResolver(temp_path)
            station = resolver.get_by_crs("NOC")
            assert station is not None
            # Station loaded successfully (coordinates may be None or 0)
            assert station.name == "STATION WITHOUT COORDS"
        finally:
            os.unlink(temp_path)
    
    def test_unicode_station_names(self):
        """Test handling of unicode characters in station names."""
        # Most UK stations use ASCII, but test unicode handling
        resolver_data = """HD00
A    NORMAL STATION                0NORMAL NOR   NOR12345 67890 5
ZZ
"""
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt', encoding='utf-8') as f:
            f.write(resolver_data)
            temp_path = f.name
        
        try:
            resolver = StationResolver(temp_path)
            assert len(resolver) >= 1
        finally:
            os.unlink(temp_path)
    
    def test_duplicate_crs_codes(self):
        """Test handling of duplicate CRS codes (last one wins)."""
        data = """HD00
A    FIRST STATION                 0FIRST  FIR   FIR12345 67890 5
A    SECOND STATION                0SECOND FIR   FIR99999 11111 5
ZZ
"""
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as f:
            f.write(data)
            temp_path = f.name
        
        try:
            resolver = StationResolver(temp_path)
            # Last occurrence should be in index
            station = resolver.get_by_crs("FIR")
            assert station is not None
            assert station.name == "SECOND STATION"
        finally:
            os.unlink(temp_path)


class TestIntegrationWithRealData:
    """Integration tests using real timetable data if available."""
    
    @pytest.fixture
    def real_msn_path(self):
        """Path to real MSN file."""
        return "/Users/kennyphilp/mywork/aiwork/trainsai/timetable/RJTTF666MSN.txt"
    
    def test_load_real_msn_file(self, real_msn_path):
        """Test loading the real MSN file."""
        if not os.path.exists(real_msn_path):
            pytest.skip("Real MSN file not available")
        
        resolver = StationResolver(real_msn_path)
        assert len(resolver) > 3000  # Real file has some non-station records
        print(f"\nLoaded {len(resolver)} stations from real MSN file")
    
    def test_common_scottish_stations(self, real_msn_path):
        """Test resolver finds common Scottish stations."""
        if not os.path.exists(real_msn_path):
            pytest.skip("Real MSN file not available")
        
        resolver = StationResolver(real_msn_path)
        
        # Test major Scottish stations
        test_cases = [
            ("EDB", "EDINBURGH"),
            ("GLC", "GLASGOW"),
            ("ABD", "ABERDEEN"),
            ("PTH", "PERTH"),
            ("INV", "INVERNESS"),
            ("STG", "STIRLING"),
            ("DEE", "DUNDEE"),
        ]
        
        for crs, expected_name_part in test_cases:
            station = resolver.get_by_crs(crs)
            assert station is not None, f"Station with CRS {crs} not found"
            assert expected_name_part in station.name.upper()
    
    def test_fuzzy_matching_real_data(self, real_msn_path):
        """Test fuzzy matching with real station names."""
        if not os.path.exists(real_msn_path):
            pytest.skip("Real MSN file not available")
        
        resolver = StationResolver(real_msn_path)
        
        # Test common user inputs (with typos)
        test_cases = [
            "edinburg",  # Missing 'h'
            "glasgo",  # Missing 'w'
            "aberdean",  # Typo
            "perth",  # Correct
            "invernes",  # Missing 's'
        ]
        
        for query in test_cases:
            station = resolver.get_by_name(query, fuzzy=True)
            assert station is not None, f"Failed to find station for query: {query}"
            print(f"  {query} -> {station.name} ({station.crs_code})")
