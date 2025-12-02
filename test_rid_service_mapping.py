#!/usr/bin/env python3
"""
Proof of Concept: RID to Service ID Mapping for Darwin Cancellations

This script tests the feasibility of enriching Darwin cancellation data 
(which only contains RID) by correlating it with National Rail API data
(which uses Service IDs) to get full train details.

The challenge: Darwin RID ≠ LDBWS Service ID
The goal: Find a reliable mapping method between these identifiers

Test approach:
1. Capture live Darwin RIDs from cancellations
2. Search LDBWS departure boards for potential matches
3. Test correlation patterns and success rates
4. Measure API performance impact

Usage: python test_rid_service_mapping.py
"""

import asyncio
import gzip
import json
import logging
import os
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set, Tuple

import stomp
from dotenv import load_dotenv

from train_tools import TrainTools

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('rid_mapping_test.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

class RIDServiceMapper:
    """
    Tests correlation between Darwin RIDs and LDBWS Service IDs.
    """
    
    def __init__(self):
        self.train_tools = TrainTools()
        self.mapping_cache = {}  # rid -> service_details
        self.failed_mappings = set()  # Track RIDs that couldn't be mapped
        self.success_patterns = []  # Store successful correlation patterns
        
        # Statistics
        self.stats = {
            'rids_received': 0,
            'mapping_attempts': 0,
            'successful_mappings': 0,
            'api_calls': 0,
            'cache_hits': 0,
            'correlation_patterns': {}
        }
    
    async def attempt_rid_mapping(self, rid: str, context: Dict) -> Optional[Dict]:
        """
        Attempt to map a Darwin RID to LDBWS service details.
        
        Args:
            rid: Darwin Route Identifier from cancellation message
            context: Additional context from Darwin message (toc, trainId, etc.)
        
        Returns:
            Service details if mapping successful, None otherwise
        """
        self.stats['mapping_attempts'] += 1
        
        # Check cache first
        if rid in self.mapping_cache:
            self.stats['cache_hits'] += 1
            logger.info(f"Cache hit for RID {rid}")
            return self.mapping_cache[rid]
        
        # Skip if previously failed
        if rid in self.failed_mappings:
            logger.debug(f"Skipping RID {rid} - previous mapping failure")
            return None
        
        logger.info(f"Attempting to map RID {rid} to Service ID...")
        
        # Strategy 1: Search multiple major stations for trains that might match
        major_stations = ['EUS', 'PAD', 'VIC', 'WAT', 'LBG', 'CHX', 'LST', 'KGX', 'STP', 'MYB']
        
        for station in major_stations[:3]:  # Limit to 3 stations for POC
            try:
                result = await self._search_station_for_rid(station, rid, context)
                if result:
                    self.mapping_cache[rid] = result
                    self.stats['successful_mappings'] += 1
                    logger.info(f"✅ Successfully mapped RID {rid} via station {station}")
                    return result
                    
                # Small delay to respect API limits
                await asyncio.sleep(0.1)
                
            except Exception as e:
                logger.error(f"Error searching station {station} for RID {rid}: {e}")
                continue
        
        # Strategy 2: Try Scottish stations if context suggests Scottish service
        if context.get('toc') in ['SR', 'SC', 'XC']:  # ScotRail, Caledonian Sleeper, CrossCountry
            scottish_stations = ['EDB', 'GLC', 'GLQ', 'ABD', 'PYL', 'DND']
            for station in scottish_stations[:2]:
                try:
                    result = await self._search_station_for_rid(station, rid, context)
                    if result:
                        self.mapping_cache[rid] = result
                        self.stats['successful_mappings'] += 1
                        logger.info(f"✅ Successfully mapped RID {rid} via Scottish station {station}")
                        return result
                        
                    await asyncio.sleep(0.1)
                    
                except Exception as e:
                    logger.error(f"Error searching Scottish station {station} for RID {rid}: {e}")
                    continue
        
        # Mark as failed to avoid repeated attempts
        self.failed_mappings.add(rid)
        logger.warning(f"❌ Failed to map RID {rid} to any Service ID")
        return None
    
    async def _search_station_for_rid(self, station: str, rid: str, context: Dict) -> Optional[Dict]:
        """
        Search a specific station's departure board for trains matching the RID.
        
        This is the experimental core - we're testing various correlation methods:
        1. Service ID contains RID substring
        2. Train timing correlation with Darwin schedule data
        3. Operator/TOC matching
        4. Route pattern matching
        """
        try:
            self.stats['api_calls'] += 1
            
            # Get detailed departures for correlation analysis
            departures = self.train_tools.get_next_departures_with_details(
                station_code=station,
                time_window=240  # 4 hours to catch delayed/cancelled services
            )
            
            if hasattr(departures, 'error'):
                logger.debug(f"API error for station {station}: {departures.message}")
                return None
            
            if not hasattr(departures, 'trains') or not departures.trains:
                logger.debug(f"No trains found at station {station}")
                return None
            
            logger.debug(f"Searching {len(departures.trains)} trains at {station} for RID {rid}")
            
            # Test correlation methods
            for train in departures.trains:
                correlation_score = self._calculate_correlation_score(train, rid, context)
                
                if correlation_score > 0.7:  # High confidence threshold
                    logger.info(f"High correlation (score: {correlation_score:.2f}) found for RID {rid}")
                    
                    # Get full service details
                    if train.service_id and train.service_id != 'N/A':
                        service_details = await self._get_service_details_safe(train.service_id)
                        if service_details:
                            # Record the correlation pattern for analysis
                            pattern = {
                                'rid': rid,
                                'service_id': train.service_id,
                                'correlation_score': correlation_score,
                                'station': station,
                                'method': 'detailed_correlation',
                                'context_match': self._analyze_context_match(train, context)
                            }
                            self.success_patterns.append(pattern)
                            
                            return {
                                **service_details,
                                'mapping_metadata': pattern
                            }
            
            return None
            
        except Exception as e:
            logger.error(f"Error searching station {station}: {e}")
            return None
    
    def _calculate_correlation_score(self, train, rid: str, context: Dict) -> float:
        """
        Calculate correlation score between LDBWS train and Darwin RID/context.
        
        Returns score 0.0-1.0 indicating likelihood of match.
        """
        score = 0.0
        
        # Method 1: Service ID substring matching
        if train.service_id and rid.lower() in train.service_id.lower():
            score += 0.4
            logger.debug(f"Service ID substring match: {train.service_id} contains {rid}")
        
        # Method 2: Operator matching
        if context.get('toc') and train.operator:
            toc_mappings = {
                'VT': ['Virgin Trains', 'Avanti West Coast'],
                'GW': ['Great Western Railway', 'GWR'],
                'SR': ['ScotRail'],
                'XC': ['CrossCountry'],
                'SW': ['South Western Railway', 'SWR']
            }
            
            expected_operators = toc_mappings.get(context['toc'], [context['toc']])
            if any(op.lower() in train.operator.lower() for op in expected_operators):
                score += 0.3
                logger.debug(f"Operator match: {train.operator} matches TOC {context['toc']}")
        
        # Method 3: Service ID pattern analysis
        if train.service_id:
            # Test if RID appears as numeric substring in Service ID
            rid_numeric = ''.join(filter(str.isdigit, rid))
            service_numeric = ''.join(filter(str.isdigit, train.service_id))
            
            if rid_numeric and len(rid_numeric) >= 6:  # Darwin RIDs are typically long numbers
                if rid_numeric[-6:] in service_numeric:  # Last 6 digits match
                    score += 0.4
                    logger.debug(f"Numeric pattern match: {rid_numeric[-6:]} found in {service_numeric}")
        
        # Method 4: Cancelled status correlation
        if train.is_cancelled and context.get('is_cancellation', True):
            score += 0.2
            logger.debug("Cancellation status correlation")
        
        # Method 5: Timing correlation (experimental)
        if context.get('ssd'):  # Schedule start date from Darwin
            try:
                darwin_date = datetime.strptime(context['ssd'], '%Y-%m-%d').date()
                today = datetime.now().date()
                if darwin_date == today:
                    score += 0.1
                    logger.debug("Date correlation match")
            except:
                pass
        
        logger.debug(f"Total correlation score for {train.service_id}: {score:.2f}")
        return score
    
    def _analyze_context_match(self, train, context: Dict) -> Dict:
        """Analyze which context elements matched for pattern learning."""
        matches = {}
        if context.get('toc') and train.operator:
            matches['operator'] = f"{context['toc']} -> {train.operator}"
        if train.is_cancelled:
            matches['cancellation_status'] = True
        return matches
    
    async def _get_service_details_safe(self, service_id: str) -> Optional[Dict]:
        """Safely get service details with error handling."""
        try:
            self.stats['api_calls'] += 1
            result = self.train_tools.get_service_details(service_id)
            
            if hasattr(result, 'error'):
                logger.debug(f"Service details error for {service_id}: {result.message}")
                return None
            
            # Convert to dict for easier handling
            return {
                'service_id': result.service_id,
                'operator': result.operator,
                'origin': result.origin,
                'destination': result.destination,
                'is_cancelled': result.is_cancelled,
                'cancel_reason': result.cancel_reason,
                'std': result.std,
                'eta': result.eta,
                'platform': result.platform,
                'calling_points_count': len(result.calling_points) if result.calling_points else 0
            }
            
        except Exception as e:
            logger.error(f"Error getting service details for {service_id}: {e}")
            return None
    
    def print_statistics(self):
        """Print mapping attempt statistics."""
        success_rate = (self.stats['successful_mappings'] / max(1, self.stats['mapping_attempts'])) * 100
        
        print("\n" + "="*60)
        print("🔍 RID→Service ID Mapping Statistics")
        print("="*60)
        print(f"RIDs Received:       {self.stats['rids_received']}")
        print(f"Mapping Attempts:    {self.stats['mapping_attempts']}")
        print(f"Successful Mappings: {self.stats['successful_mappings']}")
        print(f"Success Rate:        {success_rate:.1f}%")
        print(f"API Calls Made:      {self.stats['api_calls']}")
        print(f"Cache Hits:          {self.stats['cache_hits']}")
        print(f"Failed RIDs:         {len(self.failed_mappings)}")
        
        if self.success_patterns:
            print(f"\n📊 Successful Correlation Patterns:")
            for pattern in self.success_patterns[-5:]:  # Show last 5
                print(f"  RID {pattern['rid']} → Service {pattern['service_id']} "
                      f"(score: {pattern['correlation_score']:.2f}, via {pattern['station']})")
        
        print("="*60)


class DarwinRIDCollector(stomp.ConnectionListener):
    """
    Collects RIDs from Darwin feed and tests mapping to Service IDs.
    """
    
    def __init__(self, mapper: RIDServiceMapper):
        self.mapper = mapper
        self.message_count = 0
        self.test_limit = 20  # Limit for POC to avoid API overuse
    
    def on_connected(self, frame):
        logger.info("✅ Connected to Darwin - starting RID collection for mapping test")
    
    def on_disconnected(self):
        logger.warning("⚠️  Disconnected from Darwin")
    
    def on_error(self, frame):
        logger.error(f"STOMP error: {frame.body}")
    
    def on_message(self, frame):
        if self.mapper.stats['rids_received'] >= self.test_limit:
            logger.info(f"Reached test limit of {self.test_limit} RIDs - stopping collection")
            return
        
        try:
            self.message_count += 1
            
            # Decompress and parse
            body = frame.body
            if isinstance(body, str):
                body = body.encode('utf-8')
            
            decompressed = gzip.decompress(body)
            root = ET.fromstring(decompressed)
            
            # Find deactivated elements (cancellations)
            ns = {'ns': 'http://www.thalesgroup.com/rtti/PushPort/v16'}
            deactivated_elements = root.findall('.//ns:deactivated', ns)
            
            for d in deactivated_elements:
                rid = d.get('rid')
                if not rid:
                    continue
                
                self.mapper.stats['rids_received'] += 1
                
                # Extract context for correlation
                context = {
                    'rid': rid,
                    'uid': d.get('uid', 'UNKNOWN'),
                    'is_cancellation': True,
                    'timestamp': datetime.now().isoformat()
                }
                
                # Try to find parent context
                all_elements = root.findall('.//*')
                for elem in all_elements:
                    if elem.attrib.get('rid') == rid:
                        context.update({
                            'toc': elem.attrib.get('toc'),
                            'trainId': elem.attrib.get('trainId'),
                            'ssd': elem.attrib.get('ssd')
                        })
                        break
                
                print(f"\n🎯 Testing RID Mapping #{self.mapper.stats['rids_received']}: {rid}")
                print(f"   Context: TOC={context.get('toc')}, TrainID={context.get('trainId')}")
                
                # Test the mapping asynchronously
                asyncio.create_task(self._test_rid_mapping(rid, context))
        
        except Exception as e:
            logger.error(f"Error processing Darwin message: {e}")
    
    async def _test_rid_mapping(self, rid: str, context: Dict):
        """Test mapping for a single RID."""
        try:
            start_time = time.time()
            result = await self.mapper.attempt_rid_mapping(rid, context)
            elapsed = time.time() - start_time
            
            if result:
                print(f"   ✅ SUCCESS! Mapped to service: {result.get('service_id')}")
                print(f"   📍 Route: {result.get('origin')} → {result.get('destination')}")
                print(f"   🚂 Operator: {result.get('operator')}")
                print(f"   ⏱️  Mapping time: {elapsed:.2f}s")
                
                # Save successful mapping for analysis
                with open('successful_mappings.json', 'a') as f:
                    json.dump({
                        'rid': rid,
                        'context': context,
                        'result': result,
                        'mapping_time': elapsed,
                        'timestamp': datetime.now().isoformat()
                    }, f)
                    f.write('\n')
            else:
                print(f"   ❌ FAILED - No Service ID correlation found")
                print(f"   ⏱️  Attempt time: {elapsed:.2f}s")
        
        except Exception as e:
            logger.error(f"Error testing RID mapping for {rid}: {e}")


async def main():
    """Main POC runner."""
    print("="*80)
    print("🧪 RID→Service ID Mapping Proof of Concept")
    print("="*80)
    print("This test will:")
    print("1. Connect to Darwin Push Port to collect cancellation RIDs")
    print("2. Attempt to correlate each RID with LDBWS Service IDs")
    print("3. Test various correlation methods and measure success rates")
    print("4. Analyze patterns for viable mapping strategies")
    print(f"5. Stop after processing {20} RIDs to avoid API overuse")
    print()
    print("Press Ctrl+C to stop early and see results...")
    print("="*80)
    
    # Initialize components
    mapper = RIDServiceMapper()
    collector = DarwinRIDCollector(mapper)
    
    # Darwin connection setup
    host = "darwin-dist-44ae45.nationalrail.co.uk"
    port = 61613
    username = "DARWINc7af8eb3-ad92-4869-8682-af701f2ce953"
    password = "022d5ca4-c7b3-4190-a64e-a679c211f3eb"
    topic = "/topic/darwin.pushport-v16"
    
    # Connect to Darwin
    conn = stomp.Connection([(host, port)])
    conn.set_listener('', collector)
    conn.connect(username, password, wait=True)
    conn.subscribe(destination=topic, id=1, ack='auto')
    
    try:
        # Run collection loop
        start_time = time.time()
        while mapper.stats['rids_received'] < 20:
            await asyncio.sleep(1)
            
            # Progress update every 30 seconds
            if int(time.time() - start_time) % 30 == 0:
                print(f"\n📊 Progress: {mapper.stats['rids_received']}/20 RIDs collected, "
                      f"{mapper.stats['successful_mappings']} successful mappings")
        
        print(f"\n🏁 Collection complete! Processed {mapper.stats['rids_received']} RIDs")
        
    except KeyboardInterrupt:
        print(f"\n⏹️  Stopped by user after {mapper.stats['rids_received']} RIDs")
    
    finally:
        conn.disconnect()
        
        # Print final analysis
        mapper.print_statistics()
        
        # Generate recommendation
        success_rate = (mapper.stats['successful_mappings'] / max(1, mapper.stats['mapping_attempts'])) * 100
        
        print(f"\n🎯 PROOF OF CONCEPT RESULTS:")
        print("="*60)
        
        if success_rate >= 70:
            print("✅ HIGH FEASIBILITY - RID→Service mapping shows strong potential")
            print("   Recommendation: Proceed with Option 2 implementation")
        elif success_rate >= 40:
            print("⚠️  MODERATE FEASIBILITY - Partial success, needs optimization")
            print("   Recommendation: Hybrid approach (Option 1 + 2)")
        else:
            print("❌ LOW FEASIBILITY - RID→Service correlation insufficient")
            print("   Recommendation: Focus on Option 1 (Schedule Storage)")
        
        print(f"   Success Rate: {success_rate:.1f}%")
        print(f"   Avg API calls per RID: {mapper.stats['api_calls'] / max(1, mapper.stats['rids_received']):.1f}")
        
        if mapper.success_patterns:
            print(f"\n📈 Key Success Patterns:")
            for pattern in mapper.success_patterns:
                print(f"   - Method: {pattern.get('method', 'unknown')}")
                print(f"     Station: {pattern['station']}, Score: {pattern['correlation_score']:.2f}")


if __name__ == "__main__":
    asyncio.run(main())