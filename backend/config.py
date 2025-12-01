"""
Configuration module for Kashi Finances backend.

Loads environment variables and validates required settings.
"""
import os
from typing import List
from dotenv import load_dotenv

# Load .env file
load_dotenv()


class Settings:
    """Application settings loaded from environment variables."""
    
    # Supabase Configuration
    SUPABASE_URL: str = os.getenv("SUPABASE_URL", "")
    # Use the new publishable key instead of deprecated anon key
    SUPABASE_PUBLISHABLE_KEY: str = os.getenv("SUPABASE_PUBLISHABLE_KEY", "")
    
    # JWT Verification - Using new JWT Signing Keys (ES256 with JWKS)
    # The JWKS URL is automatically derived from SUPABASE_URL
    # Format: https://<project-id>.supabase.co/auth/v1/.well-known/jwks.json
    @property
    def SUPABASE_JWKS_URL(self) -> str:
        """Get the JWKS URL for JWT verification."""
        if not self.SUPABASE_URL:
            return ""
        return f"{self.SUPABASE_URL}/auth/v1/.well-known/jwks.json"
    
    # Google Gemini API
    GOOGLE_API_KEY: str = os.getenv("GOOGLE_API_KEY", "")
    
    # DeepSeek API
    DEEPSEEK_API_KEY: str = os.getenv("DEEPSEEK_API_KEY", "")
    
    # Supabase Storage Configuration
    SUPABASE_STORAGE_BUCKET: str = os.getenv("SUPABASE_STORAGE_BUCKET", "invoices")
    
    # Application Settings
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    
    # CORS Settings
    CORS_ORIGINS: List[str] = os.getenv(
        "CORS_ORIGINS", 
        "http://localhost:3000,http://localhost:8080"
    ).split(",")
    
    @classmethod
    def validate(cls) -> None:
        """
        Validate that all required settings are configured.
        
        Raises:
            ValueError: If any required setting is missing.
        """
        required_settings = {
            "SUPABASE_URL": cls.SUPABASE_URL,
        }
        
        missing = [key for key, value in required_settings.items() if not value]
        
        if missing:
            raise ValueError(
                f"Missing required environment variables: {', '.join(missing)}. "
                "Please check your .env file."
            )
    
    @classmethod
    def is_production(cls) -> bool:
        """Check if running in production environment."""
        return cls.ENVIRONMENT.lower() == "production"
    
    @classmethod
    def is_staging(cls) -> bool:
        """Check if running in staging environment."""
        return cls.ENVIRONMENT.lower() == "staging"
    
    @classmethod
    def is_development(cls) -> bool:
        """Check if running in development environment."""
        return cls.ENVIRONMENT.lower() == "development"


# Create a singleton instance
settings = Settings()

# Validate settings on module import (will fail fast if misconfigured)
# Only validate in production or if explicitly running the app
# Skip validation during tests or when importing for introspection
if os.getenv("VALIDATE_CONFIG", "true").lower() == "true":
    try:
        settings.validate()
    except ValueError as e:
        # In development, warn but don't crash
        if settings.is_development():
            print(f"⚠️  Warning: {e}")
            print("   The app may not work correctly until you configure your .env file.")
        else:
            # In production or staging, fail immediately
            raise
