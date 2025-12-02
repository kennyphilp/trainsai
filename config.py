"""
Configuration management for ScotRail Train Travel Advisor.

Centralizes all configuration with type-safe defaults and validation.
"""

import os
from typing import List, Optional
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


class AppConfig(BaseSettings):
    """Application configuration with environment variable support."""
    
    # Flask Configuration
    flask_secret_key: str = Field(
        default_factory=lambda: os.urandom(32).hex(),
        description="Secret key for Flask sessions"
    )
    flask_debug: bool = Field(
        default=False,
        description="Enable Flask debug mode"
    )
    flask_host: str = Field(
        default="0.0.0.0",
        description="Flask server host"
    )
    flask_port: int = Field(
        default=5001,
        description="Flask server port"
    )
    testing: bool = Field(
        default=False,
        description="Enable testing mode"
    )
    
    # Rate Limiting Configuration
    rate_limit_enabled: bool = Field(
        default=True,
        description="Enable rate limiting"
    )
    rate_limit_chat: str = Field(
        default="10 per minute",
        description="Rate limit for chat endpoint"
    )
    rate_limit_health: str = Field(
        default="60 per minute",
        description="Rate limit for health endpoint"
    )
    rate_limit_default: str = Field(
        default="100 per hour",
        description="Default rate limit"
    )
    
    # CORS Configuration
    cors_enabled: bool = Field(
        default=True,
        description="Enable CORS"
    )
    cors_origins: List[str] = Field(
        default=["http://localhost:3000", "http://localhost:5173"],
        description="Allowed CORS origins"
    )
    
    # Security Configuration
    https_enabled: bool = Field(
        default=True,
        description="Enable HTTPS enforcement with Talisman"
    )
    
    # Input Validation Configuration
    max_message_length: int = Field(
        default=5000,
        description="Maximum message length in characters"
    )
    min_message_length: int = Field(
        default=1,
        description="Minimum message length in characters"
    )
    
    # Session Management Configuration
    max_sessions: int = Field(
        default=100,
        description="Maximum number of concurrent sessions"
    )
    session_ttl_hours: int = Field(
        default=24,
        description="Session time-to-live in hours"
    )
    
    # OpenAI Configuration
    openai_api_key: Optional[str] = Field(
        default=None,
        description="OpenAI API key"
    )
    openai_model: str = Field(
        default="gpt-4o-mini",
        description="OpenAI model to use"
    )
    max_conversation_history: int = Field(
        default=20,
        description="Maximum conversation history length"
    )
    max_tokens_per_response: int = Field(
        default=1000,
        description="Maximum tokens per AI response"
    )
    max_context_tokens: int = Field(
        default=128000,
        description="Maximum context window tokens"
    )
    safety_margin_tokens: int = Field(
        default=1000,
        description="Safety margin tokens"
    )
    
    # National Rail API Configuration
    ldb_token: Optional[str] = Field(
        default=None,
        description="National Rail Live Departure Boards token"
    )
    ldb_wsdl: str = Field(
        default="http://lite.realtime.nationalrail.co.uk/OpenLDBWS/wsdl.aspx?ver=2021-11-01",
        description="National Rail WSDL URL"
    )
    disruptions_api_key: Optional[str] = Field(
        default=None,
        description="Rail Delivery Group disruptions API key"
    )
    service_details_api_key: Optional[str] = Field(
        default=None,
        description="Service details API key"
    )
    
    # Database Configuration
    timetable_db_path: str = Field(
        default="timetable.db",
        description="Path to timetable SQLite database"
    )
    timetable_msn_path: str = Field(
        default="timetable/RJTTF666MSN.txt",
        description="Path to MSN station file"
    )
    
    # Logging Configuration
    log_level: str = Field(
        default="INFO",
        description="Logging level (DEBUG, INFO, WARNING, ERROR)"
    )
    log_file: str = Field(
        default="logs/app.log",
        description="Log file path"
    )
    log_max_bytes: int = Field(
        default=10485760,  # 10MB
        description="Maximum log file size in bytes"
    )
    log_backup_count: int = Field(
        default=10,
        description="Number of backup log files to keep"
    )
    
    @field_validator('cors_origins', mode='before')
    @classmethod
    def parse_cors_origins(cls, v):
        """Parse CORS origins from string or list."""
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(',')]
        return v
    
    @field_validator('flask_debug', 'testing', 'rate_limit_enabled', 'cors_enabled', 'https_enabled', mode='before')
    @classmethod
    def parse_bool(cls, v):
        """Parse boolean values from environment strings."""
        if isinstance(v, str):
            return v.lower() in ('true', '1', 'yes', 'on')
        return v
    
    def validate_required_keys(self) -> List[str]:
        """
        Validate that required API keys are present.
        
        Returns:
            List of missing required keys (empty if all present)
        """
        missing = []
        
        if not self.openai_api_key:
            missing.append("OPENAI_API_KEY")
        
        if not self.ldb_token:
            missing.append("LDB_TOKEN")
        
        return missing
    
    class Config:
        """Pydantic configuration."""
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
        extra = "ignore"  # Ignore extra environment variables


# Global configuration instance
config = AppConfig()


def get_config() -> AppConfig:
    """Get the global configuration instance."""
    return config
