"""
Timetable data parser for UK rail CIF (Common Interface Format) files.

This module provides parsing capabilities for:
- MSN (Master Station Names): Station names, codes, and coordinates
- ZTR (Schedule): Train schedules and timing data
- ALF (Additional Fixed Links): Station connections and interchanges

The CIF format is a fixed-width text format used by UK rail industry.
"""

from dataclasses import dataclass
from typing import Optional, List, Dict, Tuple
from pathlib import Path
import re


@dataclass
class Station:
    """Represents a UK rail station with all its identifiers and metadata."""
    name: str
    crs_code: str  # 3-letter CRS code (e.g., 'EDR' for Edinburgh)
    tiploc: str  # TIPLOC code (timing point location)
    station_type: str  # Station type code
    easting: Optional[int] = None  # Ordnance Survey easting coordinate
    northing: Optional[int] = None  # Ordnance Survey northing coordinate
    category: Optional[str] = None  # Station category
    
    def __str__(self) -> str:
        return f"{self.name} ({self.crs_code})"


class StationResolver:
    """
    Resolves station names to CRS codes using fuzzy matching.
    
    Supports lookups by:
    - Full or partial station name (fuzzy matching)
    - CRS code (exact match)
    - TIPLOC code (exact match)
    - Geographic coordinates (nearest station)
    """
    
    def __init__(self, msn_file_path: str):
        """
        Initialize the station resolver by parsing the MSN file.
        
        Args:
            msn_file_path: Path to the Master Station Names (MSN) CIF file
        """
        self.stations: List[Station] = []
        self.crs_index: Dict[str, Station] = {}
        self.tiploc_index: Dict[str, Station] = {}
        self.name_index: Dict[str, Station] = {}
        
        self._parse_msn_file(msn_file_path)
        self._build_indexes()
    
    def _parse_msn_file(self, file_path: str) -> None:
        """
        Parse the MSN (Master Station Names) CIF file.
        
        Format: A [Station Name] [Type][CRS][TIPLOC][Easting][Northing][Category]
        Example: A    ABERDEEN                      2ABRDEENABD   ABD13942 68058 5
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"MSN file not found: {file_path}")
        
        with open(file_path, 'r', encoding='utf-8') as f:
            for line in f:
                if not line.startswith('A'):
                    continue  # Skip header/trailer records
                
                try:
                    station = self._parse_msn_record(line)
                    if station:
                        self.stations.append(station)
                except Exception as e:
                    # Log parsing errors but continue processing
                    print(f"Warning: Failed to parse MSN record: {line.strip()}, Error: {e}")
    
    def _parse_msn_record(self, line: str) -> Optional[Station]:
        """
        Parse a single MSN record line.
        
        Fixed-width format (verified CIF format after careful analysis):
        - Position 0: Record type ('A')
        - Position 5-34: Station name (30 chars, padded)
        - Position 35: Station type (1 char)
        - Position 36-43: TIPLOC (8 chars, padded)
        - Position 44-51: CRS code repeated twice (8 chars, "XXX   XXX")
          The actual 3-letter CRS code appears at positions 49-51
        - Position 53-57: Easting (5 digits)
        - Position 58-63: Northing (6 digits)
        - Position 64: Category (1 char)
        
        Example: "A    ABBEY WOOD                    2ABWD   ABW   ABW15473 61790 4"
                  0    5                             35 36     43 44     48 49  51
        """
        if len(line) < 51:
            return None
        
        name = line[5:35].strip()
        if not name:
            return None
        
        station_type = line[35:36] if len(line) > 35 else ''
        tiploc = line[36:44].strip() if len(line) > 44 else ''
        # Extract CRS code from position 49-51 (the second occurrence)
        crs_code = line[49:52].strip() if len(line) > 52 else ''
        
        # Parse coordinates (optional)
        easting = None
        northing = None
        category = None
        
        if len(line) > 57:
            try:
                easting_str = line[53:58].strip()
                if easting_str and easting_str.replace('E', '').isdigit():
                    # Some eastings have 'E' suffix
                    easting = int(easting_str.replace('E', ''))
            except ValueError:
                pass
        
        if len(line) > 63:
            try:
                northing_str = line[58:64].strip()
                if northing_str and northing_str.isdigit():
                    northing = int(northing_str)
            except ValueError:
                pass
        
        if len(line) > 64:
            category = line[64:65].strip()
        
        return Station(
            name=name,
            crs_code=crs_code,
            tiploc=tiploc,
            station_type=station_type,
            easting=easting,
            northing=northing,
            category=category
        )
    
    def _build_indexes(self) -> None:
        """Build lookup indexes for fast station resolution."""
        for station in self.stations:
            if station.crs_code:
                self.crs_index[station.crs_code.upper()] = station
            if station.tiploc:
                self.tiploc_index[station.tiploc.upper()] = station
            # Normalize name for index (lowercase, no punctuation)
            normalized_name = self._normalize_name(station.name)
            self.name_index[normalized_name] = station
    
    def _normalize_name(self, name: str) -> str:
        """Normalize station name for matching (lowercase, alphanumeric only)."""
        return re.sub(r'[^a-z0-9]', '', name.lower())
    
    def get_by_crs(self, crs_code: str) -> Optional[Station]:
        """
        Get station by exact CRS code match.
        
        Args:
            crs_code: 3-letter CRS code (case-insensitive)
            
        Returns:
            Station object if found, None otherwise
        """
        return self.crs_index.get(crs_code.upper())
    
    def get_by_tiploc(self, tiploc: str) -> Optional[Station]:
        """
        Get station by exact TIPLOC match.
        
        Args:
            tiploc: TIPLOC code (case-insensitive)
            
        Returns:
            Station object if found, None otherwise
        """
        return self.tiploc_index.get(tiploc.upper())
    
    def get_by_name(self, name: str, fuzzy: bool = True) -> Optional[Station]:
        """
        Get station by name with optional fuzzy matching.
        
        Args:
            name: Station name or partial name
            fuzzy: Whether to use fuzzy matching (default: True)
            
        Returns:
            Station object if found, None otherwise
        """
        # Try exact match first (normalized)
        normalized = self._normalize_name(name)
        if normalized in self.name_index:
            return self.name_index[normalized]
        
        if not fuzzy:
            return None
        
        # Fuzzy matching: find best match
        best_match = None
        best_score = 0
        
        try:
            from fuzzywuzzy import fuzz
            
            for station in self.stations:
                # Try multiple matching strategies
                score = max(
                    fuzz.ratio(normalized, self._normalize_name(station.name)),
                    fuzz.partial_ratio(normalized, self._normalize_name(station.name)),
                    fuzz.token_set_ratio(name.lower(), station.name.lower())
                )
                
                if score > best_score:
                    best_score = score
                    best_match = station
            
            # Only return if confidence is high enough
            if best_score >= 80:
                return best_match
                
        except ImportError:
            # Fallback to simple substring matching if fuzzywuzzy not available
            for station in self.stations:
                if normalized in self._normalize_name(station.name):
                    return station
        
        return None
    
    def search(self, query: str, limit: int = 10) -> List[Tuple[Station, int]]:
        """
        Search for stations matching the query with fuzzy matching.
        
        Args:
            query: Search query (name, CRS code, or TIPLOC)
            limit: Maximum number of results to return
            
        Returns:
            List of (Station, score) tuples sorted by relevance
        """
        # Check if query is a CRS code (3 letters)
        if len(query) == 3 and query.isalpha():
            station = self.get_by_crs(query)
            if station:
                return [(station, 100)]
        
        results = []
        normalized_query = self._normalize_name(query)
        
        try:
            from fuzzywuzzy import fuzz
            
            for station in self.stations:
                score = max(
                    fuzz.ratio(normalized_query, self._normalize_name(station.name)),
                    fuzz.partial_ratio(normalized_query, self._normalize_name(station.name)),
                    fuzz.token_set_ratio(query.lower(), station.name.lower())
                )
                
                if score >= 60:  # Lower threshold for search
                    results.append((station, score))
        
        except ImportError:
            # Fallback to substring matching
            for station in self.stations:
                if normalized_query in self._normalize_name(station.name):
                    # Simple scoring: longer match = better score
                    score = int((len(normalized_query) / len(station.name)) * 100)
                    results.append((station, score))
        
        # Sort by score descending
        results.sort(key=lambda x: x[1], reverse=True)
        return results[:limit]
    
    def get_nearest(self, easting: int, northing: int, limit: int = 5) -> List[Tuple[Station, float]]:
        """
        Find nearest stations to given coordinates.
        
        Args:
            easting: Ordnance Survey easting coordinate
            northing: Ordnance Survey northing coordinate
            limit: Maximum number of results to return
            
        Returns:
            List of (Station, distance_km) tuples sorted by distance
        """
        results = []
        
        for station in self.stations:
            if station.easting is None or station.northing is None:
                continue
            
            # Calculate Euclidean distance (approximate)
            dx = station.easting - easting
            dy = station.northing - northing
            distance_meters = (dx**2 + dy**2) ** 0.5
            distance_km = distance_meters / 1000
            
            results.append((station, distance_km))
        
        # Sort by distance
        results.sort(key=lambda x: x[1])
        return results[:limit]
    
    def __len__(self) -> int:
        """Return the number of stations loaded."""
        return len(self.stations)
    
    def __repr__(self) -> str:
        return f"StationResolver({len(self.stations)} stations loaded)"


class CIFScheduleParser:
    """
    Parser for CIF (Common Interface Format) schedule files (ZTR format).
    
    Parses fixed-width records containing:
    - BS: Basic Schedule (train service header)
    - BX: Basic Schedule Extra Details  
    - LO: Location Origin (starting point)
    - LI: Location Intermediate (stops along route)
    - LT: Location Terminating (end point)
    - LN: Location passing (non-stop)
    
    CIF format specification: Rail Delivery Group RDG-TSI-CIF-0055
    """
    
    def __init__(self):
        """Initialize the CIF schedule parser."""
        self.current_schedule = None
        self.current_locations = []
        
    def parse_file(self, file_path: str) -> List[Tuple[Dict, List[Dict]]]:
        """
        Parse a complete CIF schedule file.
        
        Args:
            file_path: Path to .cif or .mca file
            
        Returns:
            List of (schedule_dict, locations_list) tuples
        """
        schedules = []
        
        with open(file_path, 'r', encoding='utf-8') as f:
            for line in f:
                record_type = line[0:2]
                
                if record_type == 'BS':
                    # Save previous schedule if exists
                    if self.current_schedule:
                        schedules.append((self.current_schedule, self.current_locations))
                    
                    # Start new schedule
                    self.current_schedule = self._parse_bs_record(line)
                    self.current_locations = []
                    
                elif record_type == 'BX':
                    # Additional schedule details
                    if self.current_schedule:
                        self.current_schedule.update(self._parse_bx_record(line))
                        
                elif record_type in ('LO', 'LI', 'LT', 'LN'):
                    # Location records
                    if self.current_schedule:
                        location = self._parse_location_record(line, record_type)
                        self.current_locations.append(location)
        
        # Don't forget the last schedule
        if self.current_schedule:
            schedules.append((self.current_schedule, self.current_locations))
            
        return schedules
    
    def _parse_bs_record(self, line: str) -> Dict:
        """
        Parse BS (Basic Schedule) record.
        
        Format (positions are 0-indexed):
        0-1: 'BS' 
        2-7: Transaction type (NRCDOP)
        7-13: Train UID
        13-19: Date runs from (YYMMDD)
        19-25: Date runs to (YYMMDD)
        25-32: Days run (7 bits: 1=runs, 0=doesn't)
        ...
        """
        return {
            'train_uid': line[3:9].strip(),
            'start_date': self._parse_date(line[9:15]),
            'end_date': self._parse_date(line[15:21]),
            'days_run': line[21:28],  # 7-char string
            'bank_holiday_running': line[28:29],
            'train_status': line[29:30],  # P=passenger, F=freight, etc.
            'train_category': line[30:32].strip(),
            'train_identity': line[32:36].strip(),  # Headcode
            'headcode': line[32:36].strip(),
            'service_code': line[41:49].strip(),
            'portion_id': line[49:50],
            'power_type': line[50:53].strip(),
            'timing_load': line[53:57].strip(),
            'speed': self._parse_int(line[57:60]),
            'operating_chars': line[60:66].strip(),
            'train_class': line[66:67],  # B=both, S=standard
            'sleepers': line[67:68],  # B=berths, S=seats
            'reservations': line[68:69],  # A=compulsory, R=recommended
            'catering': line[69:73].strip(),
            'service_branding': line[73:77].strip(),
            'stp_indicator': line[79:80],  # C=cancelled, N=new, O=overlay, P=permanent
            'operator_code': line[11:13] if len(line) > 13 else ''
        }
    
    def _parse_bx_record(self, line: str) -> Dict:
        """
        Parse BX (Basic Schedule Extra Details) record.
        
        Additional attributes like UIC code, ATOC code, ATS code.
        """
        return {
            'uic_code': line[6:11].strip(),
            'atoc_code': line[11:13].strip(),
            'applicable_timetable': line[13:14]
        }
    
    def _parse_location_record(self, line: str, record_type: str) -> Dict:
        """
        Parse location record (LO/LI/LT/LN).
        
        Args:
            line: Record line
            record_type: 'LO', 'LI', 'LT', or 'LN'
            
        Returns:
            Dictionary with location details
        """
        location = {
            'type': record_type,
            'tiploc': line[2:9].strip(),
            'tiploc_suffix': line[9:10].strip(),
            'scheduled_arrival': self._parse_time(line[10:15]) if record_type in ('LI', 'LT') else None,
            'scheduled_departure': self._parse_time(line[15:20]) if record_type in ('LO', 'LI') else None,
            'scheduled_pass': self._parse_time(line[20:25]) if record_type == 'LN' else None,
            'public_arrival': self._parse_time(line[25:29]) if record_type in ('LI', 'LT') else None,
            'public_departure': self._parse_time(line[29:33]) if record_type in ('LO', 'LI') else None,
            'platform': line[33:36].strip(),
            'line': line[36:39].strip(),
            'path': line[39:42].strip(),
            'activity': line[42:54].strip(),
            'engineering_allowance': line[54:56].strip(),
            'pathing_allowance': line[56:58].strip(),
            'performance_allowance': line[58:60].strip()
        }
        
        return location
    
    def _parse_date(self, date_str: str) -> Optional[str]:
        """
        Parse CIF date format (YYMMDD) to ISO format (YYYY-MM-DD).
        
        Args:
            date_str: Date in YYMMDD format
            
        Returns:
            ISO format date string or None
        """
        if not date_str or date_str.strip() == '':
            return None
            
        try:
            year = int(date_str[0:2])
            month = int(date_str[2:4])
            day = int(date_str[4:6])
            
            # Handle Y2K: 00-49 = 2000-2049, 50-99 = 1950-1999
            if year < 50:
                year += 2000
            else:
                year += 1900
                
            return f"{year:04d}-{month:02d}-{day:02d}"
        except (ValueError, IndexError):
            return None
    
    def _parse_time(self, time_str: str) -> Optional[str]:
        """
        Parse CIF time format (HHMM or HHMMh) to HH:MM format.
        
        The 'h' suffix indicates half-minute (30 seconds).
        
        Args:
            time_str: Time in HHMM or HHMMh format
            
        Returns:
            Time in HH:MM format or None
        """
        if not time_str or time_str.strip() == '':
            return None
            
        time_str = time_str.strip()
        
        try:
            if time_str.endswith('H') or time_str.endswith('h'):
                # Half-minute time (we'll ignore the 30 seconds)
                hours = int(time_str[0:2])
                minutes = int(time_str[2:4])
            else:
                hours = int(time_str[0:2])
                minutes = int(time_str[2:4])
                
            return f"{hours:02d}:{minutes:02d}"
        except (ValueError, IndexError):
            return None
    
    def _parse_int(self, int_str: str) -> Optional[int]:
        """Parse integer from string, return None if empty or invalid."""
        try:
            return int(int_str.strip()) if int_str.strip() else None
        except ValueError:
            return None


class ALFParser:
    """
    Parser for ALF (Additional Fixed Links) files.
    
    ALF files define connections between stations and platforms:
    - Interchange times between platforms at same station
    - Walking links between nearby stations
    - Step-free access routes
    
    These are used for journey planning with connections.
    """
    
    def parse_file(self, file_path: str) -> List[Dict]:
        """
        Parse an ALF file containing station connections.
        
        Args:
            file_path: Path to .alf file
            
        Returns:
            List of connection dictionaries
        """
        connections = []
        
        with open(file_path, 'r', encoding='utf-8') as f:
            for line in f:
                # Skip comment lines and headers
                if line.startswith('*') or line.startswith('/'):
                    continue
                    
                # ALF records are fixed-width
                if len(line) < 20:
                    continue
                    
                connection = self._parse_alf_record(line)
                if connection:
                    connections.append(connection)
                    
        return connections
    
    def _parse_alf_record(self, line: str) -> Optional[Dict]:
        """
        Parse a single ALF record.
        
        Format varies but typically:
        - Mode (I=interchange, W=walking, etc.)
        - From TIPLOC
        - To TIPLOC  
        - Duration in minutes
        - Start/end times (when connection is available)
        """
        try:
            return {
                'mode': line[0:1].strip(),
                'from_tiploc': line[1:8].strip(),
                'to_tiploc': line[8:15].strip(),
                'duration': int(line[15:18].strip()) if line[15:18].strip() else 5,
                'start_time': line[18:22].strip() if len(line) > 22 else None,
                'end_time': line[22:26].strip() if len(line) > 26 else None,
                'priority': int(line[26:27]) if len(line) > 27 and line[26:27].strip() else 0
            }
        except (ValueError, IndexError) as e:
            # Skip malformed records
            return None
