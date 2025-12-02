#!/usr/bin/env python3
"""
High-Level System Architecture Diagram Generator
Visualizes the complete Darwin Rail AI system architecture
"""

import matplotlib.pyplot as plt
import matplotlib.patches as patches
from matplotlib.patches import FancyBboxPatch, ConnectionPatch
import numpy as np

def create_architecture_diagram():
    """Generate comprehensive system architecture diagram"""
    
    # Create figure with larger size for detailed diagram
    fig, ax = plt.subplots(1, 1, figsize=(20, 14))
    ax.set_xlim(0, 20)
    ax.set_ylim(0, 14)
    ax.axis('off')
    
    # Color scheme
    colors = {
        'external': '#FF6B6B',      # Red for external services
        'phase1': '#4ECDC4',        # Teal for Phase 1 components
        'phase2': '#45B7D1',        # Blue for Phase 2 components
        'data': '#96CEB4',          # Green for data stores
        'api': '#FFEAA7',           # Yellow for APIs
        'ui': '#DDA0DD',            # Purple for UI components
        'connection': '#2D3436'      # Dark gray for connections
    }
    
    # Helper function to create rounded rectangles
    def create_box(x, y, width, height, label, color, fontsize=10, text_color='black'):
        box = FancyBboxPatch(
            (x, y), width, height,
            boxstyle="round,pad=0.1",
            facecolor=color,
            edgecolor='black',
            linewidth=1.5
        )
        ax.add_patch(box)
        ax.text(x + width/2, y + height/2, label, 
               ha='center', va='center', fontsize=fontsize, 
               weight='bold', color=text_color, wrap=True)
        return box
    
    # Helper function to create connections
    def create_connection(start_x, start_y, end_x, end_y, label='', curved=False):
        if curved:
            # Create curved connection
            style = "arc3,rad=0.3"
        else:
            style = "arc3,rad=0"
            
        arrow = ConnectionPatch(
            (start_x, start_y), (end_x, end_y),
            "data", "data",
            arrowstyle="->", 
            shrinkA=5, shrinkB=5,
            connectionstyle=style,
            color=colors['connection'],
            linewidth=2
        )
        ax.add_patch(arrow)
        
        # Add label if provided
        if label:
            mid_x = (start_x + end_x) / 2
            mid_y = (start_y + end_y) / 2
            if curved:
                mid_y += 0.3
            ax.text(mid_x, mid_y, label, ha='center', va='center', 
                   fontsize=8, bbox=dict(boxstyle="round,pad=0.2", 
                   facecolor='white', alpha=0.8))
    
    # Title
    ax.text(10, 13.5, 'Darwin Rail AI System Architecture', 
           ha='center', va='center', fontsize=20, weight='bold')
    
    # External Data Sources Layer
    ax.text(1, 12.5, 'EXTERNAL DATA SOURCES', fontsize=12, weight='bold', color=colors['external'])
    create_box(0.5, 11.5, 3, 0.8, 'Darwin Push Port\n(Real-time Rail Data)\nPort 61613', colors['external'], 9)
    create_box(4, 11.5, 3, 0.8, 'National Rail\nEnquiries API\n(Station Data)', colors['external'], 9)
    create_box(7.5, 11.5, 3, 0.8, 'Alternative Transport\nAPIs (Bus/Tube)', colors['external'], 9)
    
    # Phase 1: Core Darwin Processing Layer
    ax.text(1, 10.5, 'PHASE 1: DARWIN CORE PROCESSING', fontsize=12, weight='bold', color=colors['phase1'])
    
    # Darwin Schedule Service
    create_box(0.5, 9, 4, 1.2, 'Darwin Schedule Service\n• Real-time feed processing\n• Schedule storage\n• Cancellation detection\n• SQLite database', colors['phase1'], 9)
    
    # Enhanced API Service  
    create_box(5.5, 9, 4, 1.2, 'Enhanced API Service\n• Data enrichment engine\n• Schedule-based enrichment\n• RESTful API (Port 8080)\n• Statistics & analytics', colors['phase1'], 9)
    
    # Data Storage Layer
    ax.text(12, 10.5, 'DATA STORAGE', fontsize=12, weight='bold', color=colors['data'])
    create_box(11, 9, 2.5, 1.2, 'SQLite Database\n• Schedule data\n• Cancellations\n• Enrichment cache', colors['data'], 9)
    
    # Phase 2: Passenger-Facing Services Layer
    ax.text(1, 7.8, 'PHASE 2: PASSENGER-FACING MICROSERVICES', fontsize=12, weight='bold', color=colors['phase2'])
    
    # Mobile API Service
    create_box(0.5, 6.5, 3, 1, 'Mobile API Service\n• Port 5002\n• Push notifications\n• Mobile-optimized data\n• Severity analysis', colors['phase2'], 8)
    
    # Smart Notifications Service
    create_box(4, 6.5, 3, 1, 'Smart Notifications\n• Port 5003\n• Proactive alerts\n• Impact analysis\n• Multi-threaded engine', colors['phase2'], 8)
    
    # Alternative Routing Service
    create_box(7.5, 6.5, 3, 1, 'Alternative Routing\n• Port 5004\n• Route optimization\n• Multimodal planning\n• Disruption awareness', colors['phase2'], 8)
    
    # Station Displays Service
    create_box(11, 6.5, 3, 1, 'Station Displays\n• Port 5005\n• Real-time boards\n• Platform info\n• Auto-refresh UI', colors['phase2'], 8)
    
    # Passenger Web Portal
    create_box(14.5, 6.5, 4.5, 1, 'Passenger Web Portal\n• Port 5006\n• Unified interface\n• Real-time dashboard\n• Service orchestration', colors['phase2'], 8)
    
    # User Interface Layer
    ax.text(1, 5.3, 'USER INTERFACES', fontsize=12, weight='bold', color=colors['ui'])
    
    # Web Dashboard
    create_box(0.5, 4, 3, 1, 'Web Dashboard\n• Real-time monitoring\n• Cancellation tracking\n• Admin interface', colors['ui'], 9)
    
    # Mobile Apps
    create_box(4, 4, 3, 1, 'Mobile Applications\n• iOS/Android apps\n• Push notifications\n• Journey planning', colors['ui'], 9)
    
    # Station Displays UI
    create_box(7.5, 4, 3, 1, 'Station Display UI\n• Public displays\n• Real-time boards\n• Platform information', colors['ui'], 9)
    
    # Passenger Portal UI
    create_box(11, 4, 3, 1, 'Passenger Portal\n• Unified web interface\n• Journey planning\n• Service status', colors['ui'], 9)
    
    # API Gateway/Load Balancer (conceptual)
    create_box(15, 4, 3.5, 1, 'API Gateway\n• Load balancing\n• Rate limiting\n• Authentication', colors['api'], 9)
    
    # System Integration Layer
    ax.text(1, 2.8, 'SYSTEM INTEGRATION & MONITORING', fontsize=12, weight='bold', color=colors['api'])
    
    # Monitoring & Analytics
    create_box(0.5, 1.5, 4, 1, 'Monitoring & Analytics\n• Service health checks\n• Performance metrics\n• Error tracking\n• Usage analytics', colors['api'], 9)
    
    # Configuration Management
    create_box(5, 1.5, 4, 1, 'Configuration Management\n• Environment settings\n• API keys & credentials\n• Feature flags\n• Service discovery', colors['api'], 9)
    
    # Logging & Audit
    create_box(9.5, 1.5, 4, 1, 'Logging & Audit\n• Centralized logging\n• Audit trails\n• Debug information\n• Compliance tracking', colors['api'], 9)
    
    # Security Layer
    create_box(14, 1.5, 4.5, 1, 'Security & Authentication\n• API authentication\n• Rate limiting\n• Data encryption\n• Access control', colors['api'], 9)
    
    # Create connections between components
    
    # External to Phase 1
    create_connection(2.5, 11.5, 2.5, 10.2, 'Real-time\nFeed')
    create_connection(5.5, 11.5, 7.5, 10.2, 'Station\nData', curved=True)
    
    # Phase 1 internal
    create_connection(4.5, 9.5, 5.5, 9.5, 'Enriched\nData')
    create_connection(9.5, 9.5, 11, 9.5, 'Database\nOperations')
    
    # Phase 1 to Phase 2
    create_connection(7.5, 9, 2, 7.5, 'API\nCalls', curved=True)
    create_connection(7.5, 9, 5.5, 7.5, 'Data\nFeed', curved=True)
    create_connection(7.5, 9, 9, 7.5, 'Routing\nData', curved=True)
    create_connection(7.5, 9, 12.5, 7.5, 'Display\nData', curved=True)
    create_connection(7.5, 9, 17, 7.5, 'Portal\nIntegration', curved=True)
    
    # Phase 2 to UI
    create_connection(2, 6.5, 2, 5, 'Mobile\nAPI')
    create_connection(5.5, 6.5, 5.5, 5, 'Notification\nAPI')
    create_connection(9, 6.5, 9, 5, 'Display\nAPI')
    create_connection(17, 6.5, 12.5, 5, 'Web\nInterface', curved=True)
    
    # External routing data
    create_connection(9, 11.5, 9, 7.5, 'Transport\nAPIs', curved=True)
    
    # Add legend
    legend_x = 0.5
    legend_y = 0.5
    ax.text(legend_x, legend_y + 0.3, 'LEGEND:', fontsize=10, weight='bold')
    
    legend_items = [
        ('External Services', colors['external']),
        ('Phase 1 (Core)', colors['phase1']),
        ('Phase 2 (Passenger)', colors['phase2']),
        ('Data Storage', colors['data']),
        ('APIs/Integration', colors['api']),
        ('User Interfaces', colors['ui'])
    ]
    
    for i, (label, color) in enumerate(legend_items):
        create_box(legend_x + i * 3, legend_y - 0.3, 2.5, 0.4, label, color, 8)
    
    # Add system metrics
    metrics_text = """
    SYSTEM METRICS:
    • 6 Microservices (Ports 5002-5006, 8080)
    • Real-time Darwin feed processing
    • SQLite database with schedule enrichment
    • RESTful API architecture
    • Responsive web interfaces
    • Multi-modal transport integration
    """
    
    ax.text(15, 2.8, metrics_text, fontsize=9, 
           bbox=dict(boxstyle="round,pad=0.5", facecolor='lightgray', alpha=0.8))
    
    plt.tight_layout()
    return fig

def main():
    """Generate and save the architecture diagram"""
    print("🏗️  Generating Darwin Rail AI System Architecture Diagram...")
    
    # Create the diagram
    fig = create_architecture_diagram()
    
    # Save in multiple formats
    output_files = [
        'darwin_system_architecture.png',
        'darwin_system_architecture.pdf',
        'darwin_system_architecture.svg'
    ]
    
    for filename in output_files:
        fig.savefig(filename, dpi=300, bbox_inches='tight', 
                   facecolor='white', edgecolor='none')
        print(f"📊 Architecture diagram saved: {filename}")
    
    # Display the diagram
    plt.show()
    
    print("\n✅ System Architecture Diagram Generated Successfully!")
    print("\n🎯 Key Components Visualized:")
    print("   • External data sources (Darwin Push Port, National Rail APIs)")
    print("   • Phase 1: Core Darwin processing and enrichment")
    print("   • Phase 2: 5 passenger-facing microservices")
    print("   • Data storage and API layers")
    print("   • User interface components")
    print("   • System integration and monitoring")
    print("   • Security and authentication layers")

if __name__ == "__main__":
    main()