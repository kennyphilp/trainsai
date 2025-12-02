#!/usr/bin/env python3
"""
ASCII Architecture Diagram Generator
Creates a text-based system architecture diagram
"""

def create_ascii_architecture():
    """Generate ASCII-based architecture diagram"""
    
    diagram = """
╔══════════════════════════════════════════════════════════════════════════════════════════╗
║                           DARWIN RAIL AI SYSTEM ARCHITECTURE                             ║
╚══════════════════════════════════════════════════════════════════════════════════════════╝

┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                                EXTERNAL DATA SOURCES                                    │
├─────────────────────┬─────────────────────┬─────────────────────────────────────────────┤
│  Darwin Push Port   │  National Rail API  │     Alternative Transport APIs              │
│   (Port 61613)      │   (Station Data)    │        (Bus/Tube APIs)                     │
│  Real-time Feed     │   Route Planning    │      Multi-modal Data                      │
└─────────┬───────────┴─────────────────────┴──────────────────────┬──────────────────────┘
          │                                                        │
          ▼                                                        ▼
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                              PHASE 1: DARWIN CORE PROCESSING                            │
├─────────────────────────────────┬───────────────────────────────┬───────────────────────┤
│     Darwin Schedule Service     │     Enhanced API Service      │    SQLite Database    │
│                                 │                               │                       │
│  • Real-time feed processing   │  • Data enrichment engine     │  • Schedule storage   │
│  • Schedule message storage    │  • RESTful API (Port 8080)    │  • Cancellations DB  │
│  • Cancellation detection      │  • Statistics & analytics     │  • Enrichment cache  │
│  • SQLite integration          │  • Dashboard (Port 5001)      │  • 7-day retention   │
└─────────────────┬───────────────┴─────────────┬─────────────────┴───────────────────────┘
                  │                             │
                  ▼                             ▼
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                         PHASE 2: PASSENGER-FACING MICROSERVICES                         │
├────────────┬────────────┬────────────┬────────────┬────────────────────────────────────┤
│Mobile API  │Smart       │Alternative │Station     │      Passenger Web Portal         │
│Service     │Notifications│Routing     │Displays    │                                    │
│            │Service      │Service     │Service     │  • Unified interface (Port 5006)  │
│Port 5002   │Port 5003    │Port 5004   │Port 5005   │  • Real-time dashboard            │
│            │             │            │            │  • Service orchestration          │
│• Push      │• Proactive  │• Route     │• Real-time │  • Journey planning               │
│  notify    │  alerts     │  optimize  │  boards    │  • Integration hub                │
│• Mobile    │• Impact     │• Multi-    │• Platform  │  • Responsive UI                  │
│  optimize  │  analysis   │  modal     │  info      │  • Status monitoring              │
│• Severity  │• Threading  │• Disruption│• Auto-     │  • Service health checks          │
│  analysis  │  engine     │  aware     │  refresh   │                                    │
└─────┬──────┴─────┬──────┴─────┬──────┴─────┬──────┴────────────────┬───────────────────┘
      │            │            │            │                       │
      ▼            ▼            ▼            ▼                       ▼
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                                  USER INTERFACES                                        │
├─────────────┬─────────────┬─────────────┬─────────────┬─────────────────────────────────┤
│Web          │Mobile       │Station      │Passenger    │        API Gateway              │
│Dashboard    │Applications │Display UI   │Portal UI    │                                 │
│             │             │             │             │  • Load balancing               │
│• Admin      │• iOS/Android│• Public     │• Unified    │  • Rate limiting                │
│  interface  │  apps       │  displays   │  interface  │  • Authentication               │
│• Monitoring │• Push       │• Real-time  │• Journey    │  • Service discovery            │
│• Analytics  │  notifications│  boards   │  planning   │  • Request routing              │
│• Control    │• Journey    │• Platform   │• Service    │                                 │
│  panel      │  planning   │  info       │  status     │                                 │
└─────────────┴─────────────┴─────────────┴─────────────┴─────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                          SYSTEM INTEGRATION & MONITORING                                │
├─────────────────┬─────────────────┬─────────────────┬─────────────────────────────────┤
│Monitoring &     │Configuration    │Logging &        │Security &                       │
│Analytics        │Management       │Audit            │Authentication                   │
│                 │                 │                 │                                 │
│• Health checks  │• Environment    │• Centralized    │• API authentication             │
│• Performance    │  variables      │  logging        │• Rate limiting                  │
│  metrics        │• Service        │• Audit trails   │• Data encryption                │
│• Error tracking │  discovery      │• Debug info     │• Access control                 │
│• Usage          │• Feature flags  │• Compliance     │• Security monitoring            │
│  analytics      │• Runtime config │  tracking       │• Threat detection               │
└─────────────────┴─────────────────┴─────────────────┴─────────────────────────────────┘

                                      DATA FLOW
                                        
External APIs ──→ Phase 1 Services ──→ Database ←── Phase 2 Services ──→ User Interfaces
                         │                                │
                         └──→ Monitoring ←──→ Logging ←───┘
                                │              │
                                └──→ Security ←┘

═══════════════════════════════════════════════════════════════════════════════════════════
                                   PORT ALLOCATION
═══════════════════════════════════════════════════════════════════════════════════════════
│ Service                    │ Port  │ Purpose                                              │
├────────────────────────────┼───────┼──────────────────────────────────────────────────────┤
│ Darwin Push Port           │ 61613 │ External real-time feed (STOMP)                     │
│ Enhanced API Dashboard     │ 5001  │ Administrative monitoring interface                  │
│ Mobile API Service         │ 5002  │ Mobile-optimized API endpoints                      │
│ Smart Notifications        │ 5003  │ Proactive passenger alerting system                 │
│ Alternative Routing        │ 5004  │ Intelligent route optimization                       │
│ Station Displays           │ 5005  │ Enhanced departure board interfaces                  │
│ Passenger Web Portal       │ 5006  │ Unified passenger experience hub                     │
│ Enhanced API Service       │ 8080  │ Core data enrichment and API gateway                │
═══════════════════════════════════════════════════════════════════════════════════════════

                                  TECHNOLOGY STACK
                                  
• Language: Python 3.12 with virtual environment
• Web Framework: Flask with Jinja2 templating  
• Database: SQLite with real-time operations
• Messaging: STOMP protocol for Darwin integration
• APIs: RESTful architecture with JSON responses
• Frontend: HTML/CSS/JavaScript with responsive design
• Development: Local development with port-based services
• Dependencies: Real-time processing, requests, sqlite3, stomp

════════════════════════════════════════════════════════════════════════════════════════════
"""
    
    return diagram

def main():
    """Generate and save ASCII architecture diagram"""
    print("📋 Generating ASCII System Architecture Diagram...")
    
    # Generate the diagram
    ascii_diagram = create_ascii_architecture()
    
    # Save to file
    with open('SYSTEM_ARCHITECTURE_ASCII.txt', 'w') as f:
        f.write(ascii_diagram)
    
    # Display the diagram
    print(ascii_diagram)
    
    print("\n✅ ASCII Architecture Diagram Generated!")
    print("📄 Saved as: SYSTEM_ARCHITECTURE_ASCII.txt")

if __name__ == "__main__":
    main()