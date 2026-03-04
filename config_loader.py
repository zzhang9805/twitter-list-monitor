"""
Configuration loader module for Twitter List Monitor.

Loads configuration from:
1. config.yaml - base configuration
2. .env file - API keys (override config.yaml values)

Validates required fields:
- twitter.api_key
- openrouter.api_key  
- twitter.list_ids
"""

import os
from pathlib import Path
from typing import Any, Dict, Optional

import yaml
from dotenv import load_dotenv


class ConfigError(Exception):
    """Raised when configuration validation fails."""
    pass


def get_config_path() -> Path:
    """Get the path to config.yaml (same directory as this script)."""
    return Path(__file__).parent / "config.yaml"


def load_yaml_config(config_path: Optional[Path] = None) -> Dict[str, Any]:
    """Load configuration from YAML file."""
    if config_path is None:
        config_path = get_config_path()
    
    if not config_path.exists():
        raise ConfigError(f"Config file not found: {config_path}")
    
    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
    
    return config or {}


def load_env_config() -> Dict[str, Any]:
    """Load environment variables from .env file."""
    env_path = Path(__file__).parent / ".env"
    
    if env_path.exists():
        load_dotenv(env_path)
    
    # Return dict with only relevant env vars that are set
    env_config = {}
    
    # Twitter API keys
    if os.getenv("TWITTER_API_KEY"):
        env_config["twitter_api_key"] = os.getenv("TWITTER_API_KEY")
    if os.getenv("TWITTER_BEARER_TOKEN"):
        env_config["twitter_bearer_token"] = os.getenv("TWITTER_BEARER_TOKEN")
    
    # OpenRouter API key
    if os.getenv("OPENROUTER_API_KEY"):
        env_config["openrouter_api_key"] = os.getenv("OPENROUTER_API_KEY")
    
    # Override values from config.yaml
    if os.getenv("OUTPUT_DIRECTORY"):
        env_config["output_directory"] = os.getenv("OUTPUT_DIRECTORY")
    if os.getenv("API_DELAY_SECONDS"):
        env_config["api_delay_seconds"] = float(os.getenv("API_DELAY_SECONDS"))
    if os.getenv("MODEL"):
        env_config["model"] = os.getenv("MODEL")
    
    return env_config


def validate_config(config: Dict[str, Any]) -> None:
    """Validate required configuration fields."""
    errors = []
    
    # Validate twitter section
    if "twitter" not in config:
        errors.append("Missing required section: twitter")
    else:
        twitter = config["twitter"]
        
        if not twitter.get("api_key"):
            errors.append("Missing required field: twitter.api_key")
        
        if not twitter.get("list_ids") or len(twitter.get("list_ids", [])) == 0:
            errors.append("Missing required field: twitter.list_ids (at least one required)")
    
    # Validate openrouter section
    if "openrouter" not in config:
        errors.append("Missing required section: openrouter")
    else:
        openrouter = config["openrouter"]
        
        if not openrouter.get("api_key"):
            errors.append("Missing required field: openrouter.api_key")
    
    if errors:
        raise ConfigError("Configuration validation failed:\n" + "\n".join(f"  - {e}" for e in errors))


def merge_configs(yaml_config: Dict[str, Any], env_config: Dict[str, Any]) -> Dict[str, Any]:
    """Merge YAML config with environment config (env takes precedence)."""
    merged = yaml_config.copy()
    
    # Override twitter section
    if "twitter" in merged:
        if "twitter_api_key" in env_config:
            merged["twitter"]["api_key"] = env_config["twitter_api_key"]
        if "twitter_bearer_token" in env_config:
            merged["twitter"]["bearer_token"] = env_config["twitter_bearer_token"]
    
    # Override openrouter section
    if "openrouter" in merged:
        if "openrouter_api_key" in env_config:
            merged["openrouter"]["api_key"] = env_config["openrouter_api_key"]
    
    # Override output section
    if "output" in merged:
        if "output_directory" in env_config:
            merged["output"]["directory"] = env_config["output_directory"]
    
    # Override rate_limit section
    if "rate_limit" in merged:
        if "api_delay_seconds" in env_config:
            merged["rate_limit"]["api_delay_seconds"] = env_config["api_delay_seconds"]
    
    # Override model in openrouter (if set in env)
    if "openrouter" in merged and "model" in env_config:
        merged["openrouter"]["model"] = env_config["model"]
    
    return merged


class Config:
    """Configuration object with attribute access."""
    
    def __init__(self, config_dict: Dict[str, Any]):
        self._config = config_dict
    
    def __getitem__(self, key: str) -> Any:
        return self._config[key]
    
    def __getattr__(self, name: str) -> Any:
        try:
            return self._config[name]
        except KeyError:
            raise AttributeError(f"Config has no attribute '{name}'")
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get config value with default."""
        return self._config.get(key, default)
    
    @property
    def twitter(self) -> Dict[str, Any]:
        return self._config.get("twitter", {})
    
    @property
    def openrouter(self) -> Dict[str, Any]:
        return self._config.get("openrouter", {})
    
    @property
    def output(self) -> Dict[str, Any]:
        return self._config.get("output", {})
    
    @property
    def rate_limit(self) -> Dict[str, Any]:
        return self._config.get("rate_limit", {})
    
    @property
    def monitoring(self) -> Dict[str, Any]:
        return self._config.get("monitoring", {})
    
    @property
    def logging(self) -> Dict[str, Any]:
        return self._config.get("logging", {})
    
    @property
    def telegram(self) -> Dict[str, Any]:
        return self._config.get("telegram", {})
    def logging(self) -> Dict[str, Any]:
        return self._config.get("logging", {})
    
    def to_dict(self) -> Dict[str, Any]:
        """Return config as dictionary."""
        return self._config.copy()


def load_config(config_path: Optional[Path] = None) -> Config:
    """
    Main function to load all configuration.
    
    Loads config from:
    1. config.yaml (base configuration)
    2. .env file (API keys override config.yaml)
    
    Validates required fields and returns a Config object.
    
    Args:
        config_path: Optional path to config.yaml
        
    Returns:
        Config object with all configuration
        
    Raises:
        ConfigError: If configuration is invalid or required fields are missing
    """
    # Load YAML config
    yaml_config = load_yaml_config(config_path)
    
    # Load environment config from .env
    env_config = load_env_config()
    
    # Merge configurations (env takes precedence)
    merged_config = merge_configs(yaml_config, env_config)
    
    # Validate required fields
    validate_config(merged_config)
    
    return Config(merged_config)


# Example usage
if __name__ == "__main__":
    try:
        config = load_config()
        print("Configuration loaded successfully!")
        print(f"Twitter API Key: {config.twitter.get('api_key', 'NOT SET')[:10]}...")
        print(f"OpenRouter API Key: {config.openrouter.get('api_key', 'NOT SET')[:10]}...")
        print(f"List IDs: {config.twitter.get('list_ids', [])}")
        print(f"Output Directory: {config.output.get('directory')}")
        print(f"API Delay: {config.rate_limit.get('api_delay_seconds')}s")
        print(f"Model: {config.openrouter.get('model')}")
    except ConfigError as e:
        print(f"ConfigError: {e}")
    except Exception as e:
        print(f"Error: {e}")
