# Darwin Rail AI System Architecture

## System Overview

The Darwin Rail AI system is a comprehensive real-time rail disruption management platform built on a microservices architecture. The system processes live Darwin feed data, enriches it with schedule information, and provides intelligent passenger-facing services through multiple interfaces.

## Architecture Layers

### 1. External Data Sources Layer

#### Darwin Push Port (Real-time Rail Data)
- **Source**: National Rail Darwin Push Port (Port 61613)
- **Data Type**: Real-time schedule updates, cancellations, delays
- **Protocol**: STOMP messaging protocol
- **Frequency**: Real-time continuous stream

#### National Rail Enquiries API
- **Purpose**: Station information, static schedule data
- **Usage**: Station validation, route planning
- **Integration**: RESTful API calls

#### Alternative Transport APIs
- **Sources**: Bus, Underground, alternative transport providers
- **Purpose**: Multi-modal journey planning
- **Usage**: Alternative route suggestions during disruptions

### 2. Phase 1: Core Darwin Processing Layer

#### Darwin Schedule Service
- **File**: `darwin_schedule_prototype.py`
- **Purpose**: Real-time feed processing and storage
- **Features**:
  - STOMP client for Darwin Push Port connection
  - SQLite database for schedule storage
  - Real-time cancellation detection
  - Automatic data cleanup (7-day retention)
- **Database**: `demo_detailed.db` (SQLite)
- **Logging**: Comprehensive activity logging

#### Enhanced API Service
- **File**: `enhanced_api.py` 
- **Port**: 8080
- **Purpose**: Data enrichment and API gateway
- **Features**:
  - Schedule-based enrichment engine
  - RESTful API endpoints
  - Real-time statistics and analytics
  - Dashboard interface (Port 5001)
- **Endpoints**:
  - `GET /cancellations` - Recent cancellations with enrichment
  - `GET /cancellations/enriched` - Only enriched cancellations
  - `GET /cancellations/stats` - Service statistics
  - `GET /cancellations/by-route` - Route-grouped cancellations

### 3. Phase 2: Passenger-Facing Microservices Layer

#### Mobile API Service
- **File**: `mobile_api.py`
- **Port**: 5002
- **Purpose**: Mobile-optimized API for app integration
- **Features**:
  - Push notification support
  - Mobile-optimized data formatting
  - Severity analysis and classification
  - Simplified JSON responses

#### Smart Notifications Service
- **File**: `smart_notifications.py`
- **Port**: 5003
- **Purpose**: Proactive passenger alerting system
- **Features**:
  - Multi-threaded notification engine
  - Impact analysis algorithms
  - Proactive alert generation
  - Platform-specific notifications

#### Alternative Routing Service
- **File**: `alternative_routing.py`
- **Port**: 5004
- **Purpose**: Intelligent route optimization
- **Features**:
  - Disruption-aware routing
  - Multi-modal journey planning
  - Real-time route suggestions
  - Alternative transport integration

#### Station Displays Service
- **File**: `station_displays.py`
- **Port**: 5005
- **Purpose**: Enhanced station departure boards
- **Features**:
  - Real-time departure information
  - Platform-specific data
  - Auto-refresh web interface
  - Disruption-aware displays

#### Passenger Web Portal
- **File**: `passenger_portal.py`
- **Port**: 5006
- **Purpose**: Unified passenger interface
- **Features**:
  - Service orchestration hub
  - Real-time dashboard
  - Journey planning interface
  - Integration with all Phase 2 services

### 4. Data Storage Layer

#### SQLite Database (`demo_detailed.db`)
- **Purpose**: Primary data storage for schedules and enrichment
- **Tables**:
  - Schedule messages and updates
  - Cancellation records
  - Enrichment cache
  - Historical data (7-day retention)
- **Performance**: Optimized for real-time read/write operations

### 5. User Interface Layer

#### Web Dashboard
- **Access**: Integrated with Enhanced API (Port 5001)
- **Purpose**: Administrative monitoring and control
- **Features**: Real-time statistics, cancellation tracking

#### Mobile Applications
- **Integration**: Mobile API Service (Port 5002)
- **Features**: Push notifications, journey planning

#### Station Display UI
- **Integration**: Station Displays Service (Port 5005)
- **Purpose**: Public information displays

#### Passenger Portal UI
- **Integration**: Passenger Web Portal (Port 5006)
- **Purpose**: Unified passenger experience

### 6. System Integration & Monitoring

#### Configuration Management
- **Environment Variables**: API keys, database paths
- **Service Discovery**: Port and endpoint configuration
- **Feature Flags**: Runtime behavior control

#### Monitoring & Analytics
- **Health Checks**: Service availability monitoring
- **Performance Metrics**: Response times, throughput
- **Error Tracking**: Exception logging and alerting
- **Usage Analytics**: API usage patterns

#### Logging & Audit
- **Centralized Logging**: Structured log aggregation
- **Audit Trails**: User action tracking
- **Debug Information**: Development and troubleshooting
- **Compliance**: Data processing compliance

#### Security & Authentication
- **API Authentication**: Service-to-service security
- **Rate Limiting**: API usage control
- **Data Encryption**: Sensitive data protection
- **Access Control**: User permission management

## Data Flow Architecture

### Real-time Processing Pipeline

1. **Data Ingestion**: Darwin Push Port → Schedule Service
2. **Processing**: Schedule Service → Enhanced API
3. **Enrichment**: Enhanced API ↔ SQLite Database
4. **Distribution**: Enhanced API → Phase 2 Services
5. **Presentation**: Phase 2 Services → User Interfaces

### API Communication Patterns

- **Synchronous**: RESTful HTTP APIs for real-time queries
- **Asynchronous**: Background processing for enrichment
- **Event-driven**: Real-time notifications and updates

## Service Dependencies

```
External APIs → Phase 1 Services → Database ← Phase 2 Services → UIs
                      ↓                              ↓
                 Monitoring ← → Logging → Security → Config
```

## Deployment Architecture

### Development Environment
- **Platform**: Local development (macOS/zsh)
- **Python**: Virtual environment (.venv)
- **Database**: Local SQLite
- **Networking**: localhost with port-based service discovery

### Port Allocation
- **5001**: Enhanced API Dashboard
- **5002**: Mobile API Service
- **5003**: Smart Notifications Service
- **5004**: Alternative Routing Service
- **5005**: Station Displays Service
- **5006**: Passenger Web Portal
- **8080**: Enhanced API Service
- **61613**: Darwin Push Port (external)

## Scalability Considerations

### Horizontal Scaling
- Microservices can be independently scaled
- Load balancing across service instances
- Database read replicas for high-traffic endpoints

### Vertical Scaling
- Memory optimization for real-time processing
- CPU scaling for enrichment algorithms
- Storage scaling for historical data

### Performance Optimization
- Caching strategies for frequent queries
- Database indexing for fast lookups
- Connection pooling for external APIs

## Security Architecture

### Data Protection
- Encrypted connections to external APIs
- Secure storage of sensitive configuration
- Data anonymization for analytics

### Access Control
- API key authentication
- Rate limiting per service
- Request validation and sanitization

### Monitoring & Alerting
- Security event logging
- Anomaly detection
- Automated incident response

## Future Enhancements

### Planned Features
- Machine learning for predictive analytics
- Enhanced mobile application features
- Advanced routing algorithms
- Real-time passenger density tracking

### Infrastructure Improvements
- Container orchestration (Docker/Kubernetes)
- Cloud deployment options
- Enhanced monitoring and alerting
- Automated testing and deployment pipelines

## Technical Stack Summary

- **Language**: Python 3.12
- **Web Framework**: Flask
- **Database**: SQLite
- **Messaging**: STOMP protocol
- **Frontend**: HTML/CSS/JavaScript with Jinja2 templating
- **APIs**: RESTful architecture
- **Monitoring**: Built-in logging and health checks
- **Development**: Virtual environment with pip dependencies