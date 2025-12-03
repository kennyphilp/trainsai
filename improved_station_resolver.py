"""
Improved Station Resolver using enhanced database architecture with smart search
"""
import sqlite3
from typing import Optional, List, Tuple, Dict, Any
import logging

logger = logging.getLogger(__name__)
sql_logger = logging.getLogger('sql_queries')
sql_logger.setLevel(logging.DEBUG)

class ImprovedStationResolver:
    """
    Enhanced station resolver using smart_station_search view with geographical context.
    Provides optimized station resolution and place-name search capabilities.
    """
    
    def __init__(self, db_path: str = "timetable.db"):
        self.db_path = db_path
        
    def _get_connection(self) -> sqlite3.Connection:
        """Get database connection."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row  # Enable column access by name
        return conn
    
    def _execute_with_logging(self, cursor, query: str, params=None):
        """Execute SQL query with logging."""
        if params:
            sql_logger.info(f"SQL: {query} | PARAMS: {params}")
            return cursor.execute(query, params)
        else:
            sql_logger.info(f"SQL: {query}")
            return cursor.execute(query)
    
    def resolve_station(self, station_input: str) -> Optional[str]:
        """
        Resolve station name/code to canonical TIPLOC using smart search.
        Uses smart_station_search view with geographical context for enhanced matching.
        
        Args:
            station_input: Station name, CRS code, or TIPLOC code
            
        Returns:
            Canonical TIPLOC code or None if not found
        """
        if not station_input:
            return None
            
        station_upper = station_input.upper().strip()
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # 1. Check TIPLOC mappings first (handles data inconsistencies)
            self._execute_with_logging(cursor, '''
                SELECT canonical_tiploc FROM tiploc_mappings 
                WHERE source_tiploc = ?
            ''', (station_upper,))
            result = cursor.fetchone()
            if result:
                logger.debug(f"Resolved via TIPLOC mapping: {station_input} -> {result[0]}")
                return result[0]
            
            # 2. Use smart_station_search for enhanced matching with geographical context
            # CRITICAL: Only return passenger stations - exclude infrastructure/signaling points
            self._execute_with_logging(cursor, '''
                SELECT s.tiploc, s.station_name, s.display_name, s.city_name, s.region_name, s.country_name
                FROM smart_station_search s
                JOIN stations st ON s.tiploc = st.tiploc
                WHERE ((s.tiploc = ? OR s.crs_code = ?) 
                   OR (UPPER(s.station_name) = ? OR UPPER(s.display_name) = ?)
                   OR (UPPER(s.search_name) LIKE ? OR s.all_aliases LIKE ?))
                   AND s.crs_code IS NOT NULL AND s.crs_code != ''
                   AND st.station_category NOT IN ('CrossingOnly', 'NonPassengerOrOperational', 
                                                   'RoutingOnly', 'EngineeringLocation', 
                                                   'NonPassenger', 'FreightYard')
                   AND st.station_type NOT IN ('Maintenance', 'OptionalFreight', 'OptionalCrossing')
                   AND s.station_name NOT LIKE '%Gantry%'
                   AND s.station_name NOT LIKE '%Siding%'
                   AND s.station_name NOT LIKE '%Signal%'
                   AND s.station_name NOT LIKE '%Works%'
                   AND s.station_name NOT LIKE '%(OOU)%'
                   AND s.station_name NOT LIKE '%Loop%'
                   AND s.station_name NOT LIKE '%Junction%'
                ORDER BY 
                    CASE 
                        WHEN s.tiploc = ? THEN 1
                        WHEN s.crs_code = ? THEN 2  
                        WHEN UPPER(s.station_name) = ? THEN 3
                        WHEN UPPER(s.display_name) = ? THEN 4
                        ELSE 5
                    END
                LIMIT 1
            ''', (station_upper, station_upper, station_upper, station_upper, 
                  f'%{station_upper}%', f'%{station_upper}%',
                  station_upper, station_upper, station_upper, station_upper))
            
            result = cursor.fetchone()
            if result:
                tiploc, name, display_name, city, region, country = result
                geo_context = f"{city or ''}, {region or ''}, {country or ''}".strip(', ')
                logger.info(f"Smart search resolved: {station_input} -> {tiploc} ({display_name or name}) [{geo_context}]")
                return tiploc
            
            # 3. Fuzzy search fallback with geographical context
            logger.debug(f"No exact match for {station_input}, trying fuzzy search")
            return self._fuzzy_search_with_context(station_input, cursor)
    
    def _fuzzy_search_with_context(self, station_input: str, cursor) -> Optional[str]:
        """
        Perform fuzzy search with geographical context for disambiguation.
        
        Args:
            station_input: Original station input
            cursor: Database cursor
            
        Returns:
            Best matching TIPLOC or None
        """
        search_term = station_input.upper().strip()
        
        # Fuzzy search using smart_station_search view - PASSENGER STATIONS ONLY
        self._execute_with_logging(cursor, '''
            SELECT s.tiploc, s.station_name, s.display_name, s.city_name, s.region_name, s.country_name,
                   CASE 
                       WHEN UPPER(s.station_name) LIKE ? THEN 1
                       WHEN UPPER(s.display_name) LIKE ? THEN 2
                       WHEN s.all_aliases LIKE ? THEN 3
                       WHEN UPPER(s.search_name) LIKE ? THEN 4
                       ELSE 5
                   END as match_quality
            FROM smart_station_search s
            JOIN stations st ON s.tiploc = st.tiploc
            WHERE (UPPER(s.station_name) LIKE ? 
               OR UPPER(s.display_name) LIKE ?
               OR s.all_aliases LIKE ?
               OR UPPER(s.search_name) LIKE ?)
               AND s.crs_code IS NOT NULL AND s.crs_code != ''
               AND st.station_category NOT IN ('CrossingOnly', 'NonPassengerOrOperational', 
                                               'RoutingOnly', 'EngineeringLocation', 
                                               'NonPassenger', 'FreightYard')
               AND st.station_type NOT IN ('Maintenance', 'OptionalFreight', 'OptionalCrossing')
               AND s.station_name NOT LIKE '%Gantry%'
               AND s.station_name NOT LIKE '%Siding%'
               AND s.station_name NOT LIKE '%Signal%'
               AND s.station_name NOT LIKE '%Works%'
               AND s.station_name NOT LIKE '%(OOU)%'
               AND s.station_name NOT LIKE '%Loop%'
               AND s.station_name NOT LIKE '%Junction%'
            ORDER BY match_quality, s.station_name
            LIMIT 5
        ''', (f'%{search_term}%', f'%{search_term}%', f'%{search_term}%', f'%{search_term}%',
              f'%{search_term}%', f'%{search_term}%', f'%{search_term}%', f'%{search_term}%'))
        
        matches = cursor.fetchall()
        
        if not matches:
            logger.debug(f"No fuzzy matches found for {station_input}")
            return None
        
        # Return best match with geographical context logging
        best_match = matches[0]
        tiploc, name, display_name, city, region, country = best_match[:6]
        geo_context = f"{city or ''}, {region or ''}, {country or ''}".strip(', ')
        
        if len(matches) > 1:
            logger.info(f"Fuzzy search found {len(matches)} matches for '{station_input}', using: {display_name or name} [{geo_context}]")
        else:
            logger.debug(f"Fuzzy search resolved: {station_input} -> {tiploc} ({display_name or name}) [{geo_context}]")
        
        return tiploc
    
    def search_stations_by_place(self, place_name: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Search stations by place name using geographical hierarchy.
        
        Args:
            place_name: City, region, or area name
            limit: Maximum number of results
            
        Returns:
            List of stations with geographical context
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            search_term = place_name.upper().strip()
            
            self._execute_with_logging(cursor, '''
                SELECT s.tiploc, s.station_name, s.display_name, s.crs_code,
                       s.city_name, s.region_name, s.country_name, s.latitude, s.longitude
                FROM smart_station_search s
                JOIN stations st ON s.tiploc = st.tiploc
                WHERE (UPPER(s.city_name) LIKE ? 
                   OR UPPER(s.region_name) LIKE ?
                   OR UPPER(s.country_name) LIKE ?
                   OR UPPER(s.station_name) LIKE ?)
                   AND s.crs_code IS NOT NULL AND s.crs_code != ''
                   AND st.station_category NOT IN ('CrossingOnly', 'NonPassengerOrOperational', 
                                                   'RoutingOnly', 'EngineeringLocation', 
                                                   'NonPassenger', 'FreightYard')
                   AND st.station_type NOT IN ('Maintenance', 'OptionalFreight', 'OptionalCrossing')
                   AND s.station_name NOT LIKE '%Gantry%'
                   AND s.station_name NOT LIKE '%Siding%'
                   AND s.station_name NOT LIKE '%Signal%'
                   AND s.station_name NOT LIKE '%Works%'
                   AND s.station_name NOT LIKE '%(OOU)%'
                   AND s.station_name NOT LIKE '%Loop%'
                   AND s.station_name NOT LIKE '%Junction%'
                ORDER BY 
                    CASE 
                        WHEN UPPER(s.city_name) = ? THEN 1
                        WHEN UPPER(s.city_name) LIKE ? THEN 2
                        WHEN UPPER(s.region_name) LIKE ? THEN 3
                        ELSE 4
                    END,
                    s.station_name
                LIMIT ?
            ''', (f'%{search_term}%', f'%{search_term}%', f'%{search_term}%', f'%{search_term}%',
                  search_term, f'%{search_term}%', f'%{search_term}%', limit))
            
            results = []
            for row in cursor.fetchall():
                tiploc, name, display_name, crs, city, region, country, lat, lon = row
                geo_context = f"{city or ''}, {region or ''}, {country or ''}".strip(', ')
                
                results.append({
                    'tiploc': tiploc,
                    'name': display_name or name,
                    'crs_code': crs,
                    'city': city,
                    'region': region,
                    'country': country,
                    'geographical_context': geo_context,
                    'coordinates': {'latitude': lat, 'longitude': lon} if lat and lon else None
                })
            
            logger.info(f"Found {len(results)} stations matching place '{place_name}'")
            return results
    
    def get_station_info(self, tiploc: str) -> Optional[Dict[str, Any]]:
        """
        Get comprehensive information about a station using smart search.
        
        Args:
            tiploc: Station TIPLOC code
            
        Returns:
            Enhanced station information with geographical context
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            self._execute_with_logging(cursor, '''
                SELECT s.station_id, s.tiploc, s.crs_code, s.station_name, s.display_name, s.search_name,
                       s.country, s.region, s.city_name, s.region_name, s.country_name,
                       s.latitude, s.longitude, s.all_aliases
                FROM smart_station_search s
                JOIN stations st ON s.tiploc = st.tiploc
                WHERE s.tiploc = ?
                   AND s.crs_code IS NOT NULL AND s.crs_code != ''
                   AND st.station_category NOT IN ('CrossingOnly', 'NonPassengerOrOperational', 
                                                   'RoutingOnly', 'EngineeringLocation', 
                                                   'NonPassenger', 'FreightYard')
                   AND st.station_type NOT IN ('Maintenance', 'OptionalFreight', 'OptionalCrossing')
                   AND s.station_name NOT LIKE '%Gantry%'
                   AND s.station_name NOT LIKE '%Siding%'
                   AND s.station_name NOT LIKE '%Signal%'
                   AND s.station_name NOT LIKE '%Works%'
                   AND s.station_name NOT LIKE '%(OOU)%'
                   AND s.station_name NOT LIKE '%Loop%'
                   AND s.station_name NOT LIKE '%Junction%'
            ''', (tiploc,))
            
            station = cursor.fetchone()
            if not station:
                logger.warning(f"Station not found: {tiploc}")
                return None
            
            (station_id, tiploc, crs, name, display_name, search_name,
             country, region, city, region_full, country_full, lat, lon, aliases) = station
            
            # Create structured geographical context
            geographical_context = {
                'area': city,
                'region': region_full,
                'country': country_full,
                'city': city,
                'region_code': region,
                'country_code': country
            }
            
            return {
                'tiploc': tiploc,
                'crs_code': crs,
                'name': name,
                'display_name': display_name,
                'search_name': search_name,
                'geographical_context': geographical_context,
                'country': country,
                'region': region,
                'city': city,
                'coordinates': {
                    'latitude': lat,
                    'longitude': lon
                } if lat and lon else None,
                'aliases': aliases.split('|') if aliases else [],
                'enhanced_search': True  # Flag to indicate this uses enhanced search
            }
    
    def search_by_place(self, place_name: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Search for stations by place name with geographical intelligence.
        
        Args:
            place_name: Name of city, region, or area
            limit: Maximum number of results to return
            
        Returns:
            List of stations in or near the specified place
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            place_upper = place_name.upper()
            
            # Search across geographical hierarchies
            self._execute_with_logging(cursor, '''
                SELECT tiploc, station_name, display_name, city_name, region_name, country_name,
                       latitude, longitude, crs_code
                FROM smart_station_search 
                WHERE UPPER(city_name) LIKE ? 
                   OR UPPER(region_name) LIKE ? 
                   OR UPPER(country_name) LIKE ?
                   OR UPPER(search_name) LIKE ?
                ORDER BY 
                    CASE 
                        WHEN UPPER(city_name) = ? THEN 1
                        WHEN UPPER(city_name) LIKE ? THEN 2
                        WHEN UPPER(region_name) = ? THEN 3
                        WHEN UPPER(region_name) LIKE ? THEN 4
                        ELSE 5
                    END,
                    station_name
                LIMIT ?
            ''', (f'%{place_upper}%', f'%{place_upper}%', f'%{place_upper}%', f'%{place_upper}%',
                  place_upper, f'%{place_upper}%', place_upper, f'%{place_upper}%', limit))
            
            results = []
            for row in cursor.fetchall():
                tiploc, name, display_name, city, region, country, lat, lon, crs = row
                
                geographical_context = {
                    'area': city,
                    'region': region,
                    'country': country
                }
                
                results.append({
                    'tiploc': tiploc,
                    'crs_code': crs,
                    'name': name,
                    'display_name': display_name or name,
                    'geographical_context': geographical_context,
                    'coordinates': {
                        'latitude': lat,
                        'longitude': lon
                    } if lat and lon else None
                })
            
            return results
    
    def get_stations_in_area(self, area_name: str) -> List[Dict[str, Any]]:
        """
        Get all stations within a specific geographical area.
        
        Args:
            area_name: Name of geographical area/region
            
        Returns:
            List of stations in the specified area
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            area_upper = area_name.upper()
            
            # Find stations in the specified area - PASSENGER STATIONS ONLY
            self._execute_with_logging(cursor, '''
                SELECT s.tiploc, s.station_name, s.display_name, s.city_name, s.region_name, s.country_name,
                       s.latitude, s.longitude, s.crs_code
                FROM smart_station_search s
                JOIN stations st ON s.tiploc = st.tiploc
                WHERE (UPPER(s.region_name) = ? OR UPPER(s.city_name) = ?)
                   AND s.crs_code IS NOT NULL AND s.crs_code != ''
                   AND st.station_category NOT IN ('CrossingOnly', 'NonPassengerOrOperational', 
                                                   'RoutingOnly', 'EngineeringLocation', 
                                                   'NonPassenger', 'FreightYard')
                   AND st.station_type NOT IN ('Maintenance', 'OptionalFreight', 'OptionalCrossing')
                   AND s.station_name NOT LIKE '%Gantry%'
                   AND s.station_name NOT LIKE '%Siding%'
                   AND s.station_name NOT LIKE '%Signal%'
                   AND s.station_name NOT LIKE '%Works%'
                   AND s.station_name NOT LIKE '%(OOU)%'
                   AND s.station_name NOT LIKE '%Loop%'
                   AND s.station_name NOT LIKE '%Junction%'
                ORDER BY s.station_name
            ''', (area_upper, area_upper))
            
            results = []
            for row in cursor.fetchall():
                tiploc, name, display_name, city, region, country, lat, lon, crs = row
                
                geographical_context = {
                    'area': city,
                    'region': region,
                    'country': country
                }
                
                results.append({
                    'tiploc': tiploc,
                    'crs_code': crs,
                    'name': name,
                    'display_name': display_name or name,
                    'geographical_context': geographical_context,
                    'coordinates': {
                        'latitude': lat,
                        'longitude': lon
                    } if lat and lon else None
                })
            
            return results
    
    def find_stations_near(self, reference_tiploc: str, max_distance_km: float = 50) -> List[Dict[str, Any]]:
        """
        Find stations near a reference station using enhanced geographical data.
        
        Args:
            reference_tiploc: Reference station TIPLOC
            max_distance_km: Maximum distance in kilometers
            
        Returns:
            List of nearby stations with geographical context
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # Get reference coordinates from smart search
            self._execute_with_logging(cursor, '''
                SELECT latitude, longitude, city_name, region_name 
                FROM smart_station_search WHERE tiploc = ?
            ''', (reference_tiploc,))
            ref_result = cursor.fetchone()
            
            if not ref_result or not all(ref_result[:2]):
                logger.warning(f"No coordinates available for reference station {reference_tiploc}")
                return []
            
            ref_lat, ref_lon, ref_city, ref_region = ref_result
            
            # Find nearby stations using enhanced search with geographical context
            self._execute_with_logging(cursor, '''
                SELECT 
                    tiploc, station_name, display_name, crs_code, 
                    city_name, region_name, country_name, latitude, longitude,
                    (
                        6371 * acos(
                            cos(radians(?)) * cos(radians(latitude)) * 
                            cos(radians(longitude) - radians(?)) +
                            sin(radians(?)) * sin(radians(latitude))
                        )
                    ) AS distance_km
                FROM smart_station_search
                WHERE latitude IS NOT NULL 
                  AND longitude IS NOT NULL
                  AND tiploc != ?
                HAVING distance_km <= ?
                ORDER BY distance_km
                LIMIT 20
            ''', (ref_lat, ref_lon, ref_lat, reference_tiploc, max_distance_km))
            
            results = []
            for row in cursor.fetchall():
                tiploc, name, display_name, crs, city, region, country, lat, lon, distance = row
                geo_context = f"{city or ''}, {region or ''}, {country or ''}".strip(', ')
                
                results.append({
                    'tiploc': tiploc,
                    'name': display_name or name,
                    'crs_code': crs,
                    'geographical_context': geo_context,
                    'coordinates': {'latitude': lat, 'longitude': lon},
                    'distance_km': round(distance, 2)
                })
                
            logger.info(f"Found {len(results)} stations within {max_distance_km}km of {reference_tiploc} using smart search")
            return results
    
    # Backward compatibility methods
    def get_fuzzy_matches(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Backward compatibility wrapper for fuzzy search."""
        return self.search_stations_by_place(query, limit)
    
    def __len__(self) -> int:
        """Return total number of stations for compatibility."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM smart_station_search")
            return cursor.fetchone()[0]