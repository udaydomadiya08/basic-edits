import json
import logging
import aiohttp
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
from enum import Enum

logger = logging.getLogger(__name__)

class ModelStatus(Enum):
    AVAILABLE = "available"
    RATE_LIMITED = "rate_limited"
    BANNED = "banned"
    COOLDOWN = "cooldown"

@dataclass
class RateLimit:
    rpm: int  # Requests per minute
    tpm: int  # Tokens per minute  
    rpd: int  # Requests per day

@dataclass
class ModelConfig:
    name: str
    category: str
    rate_limit: RateLimit
    performance_score: float  # 1-10, higher is better
    cost_efficiency: float    # 1-10, higher is better

@dataclass
class APIKeyStatus:
    key: str
    last_used: datetime
    daily_requests: int
    daily_tokens: int
    minute_requests: int
    minute_tokens: int
    last_minute_reset: datetime
    last_day_reset: datetime
    banned_until: Optional[datetime] = None
    status: ModelStatus = ModelStatus.AVAILABLE

class GeminiAPIManager:
    """
    Advanced Gemini API Manager with Rate Limit Protection
    Handles multiple API keys, model rotation, and intelligent fallback
    """
    
    def __init__(self, config_path: str = "gemini_config.json"):
        self.config_path = config_path
        self.api_keys: Dict[str, APIKeyStatus] = {}
        self.models: Dict[str, ModelConfig] = {}
        self.current_key_index = 0
        self.key_health_scores: Dict[str, float] = {}
        self.last_health_check = datetime.now()
        self.model_cooldowns: Dict[str, datetime] = {}
        self.key_unsupported_models: Dict[str, set] = {}
        self.load_config()
        
    def load_config(self):
        """Load API keys and model configurations"""
        try:
            with open(self.config_path, 'r') as f:
                config = json.load(f)
                
            # Initialize API keys with health tracking
            for key_data in config.get('api_keys', []):
                api_key = key_data['key']
                self._add_api_key(api_key)
            
            # Initialize model configurations based on free tier limits
            self.models = {
                "gemini-2.5-flash": ModelConfig(
                    name="gemini-2.5-flash",
                    category="text",
                    rate_limit=RateLimit(rpm=15, tpm=1000000, rpd=1500),
                    performance_score=10.0,
                    cost_efficiency=9.9
                ),
                "gemini-1.5-flash": ModelConfig(
                    name="gemini-1.5-flash",
                    category="text",
                    rate_limit=RateLimit(rpm=15, tpm=1000000, rpd=1500),
                    performance_score=9.8,
                    cost_efficiency=9.5
                ),
                "gemini-2.0-flash": ModelConfig(
                    name="gemini-2.0-flash",
                    category="text",
                    rate_limit=RateLimit(rpm=15, tpm=1000000, rpd=1500),
                    performance_score=9.5,
                    cost_efficiency=9.5
                ),
                "gemini-3.1-flash": ModelConfig(
                    name="gemini-3.1-flash",
                    category="text",
                    rate_limit=RateLimit(rpm=15, tpm=1000000, rpd=1500),
                    performance_score=9.0,
                    cost_efficiency=9.9
                ),
                "gemini-1.5-pro": ModelConfig(
                    name="gemini-1.5-pro",
                    category="text",
                    rate_limit=RateLimit(rpm=5, tpm=500000, rpd=360),
                    performance_score=9.0,
                    cost_efficiency=8.0
                ),
                
                # TTS models - Medium priority
                "gemini-2.5-flash-tts": ModelConfig(
                    name="gemini-2.5-flash-tts",
                    category="tts",
                    rate_limit=RateLimit(rpm=3, tpm=10000, rpd=10),
                    performance_score=8.0,
                    cost_efficiency=7.0
                ),
                "gemini-3.1-flash-tts": ModelConfig(
                    name="gemini-3.1-flash-tts", 
                    category="tts",
                    rate_limit=RateLimit(rpm=3, tpm=10000, rpd=10),
                    performance_score=8.5,
                    cost_efficiency=7.5
                ),
                
                # Embedding models - Low priority
                "gemini-embedding-1": ModelConfig(
                    name="gemini-embedding-1",
                    category="embedding",
                    rate_limit=RateLimit(rpm=100, tpm=30000, rpd=1000),
                    performance_score=7.0,
                    cost_efficiency=8.0
                ),
                "gemini-embedding-2": ModelConfig(
                    name="gemini-embedding-2",
                    category="embedding", 
                    rate_limit=RateLimit(rpm=100, tpm=30000, rpd=1000),
                    performance_score=7.5,
                    cost_efficiency=8.5
                ),
                
                # Other models - Lowest priority
                "gemma-3-1b": ModelConfig(
                    name="gemma-3-1b",
                    category="fallback",
                    rate_limit=RateLimit(rpm=30, tpm=15000, rpd=14400),
                    performance_score=6.0,
                    cost_efficiency=9.0
                ),
                "gemma-3-4b": ModelConfig(
                    name="gemma-3-4b", 
                    category="fallback",
                    rate_limit=RateLimit(rpm=30, tpm=15000, rpd=14400),
                    performance_score=7.0,
                    cost_efficiency=8.5
                ),
                "gemma-4-12b": ModelConfig(
                    name="gemma-4-12b",
                    category="fallback",
                    rate_limit=RateLimit(rpm=30, tpm=15000, rpd=14400),
                    performance_score=8.0,
                    cost_efficiency=9.0
                ),
                "gemma-4-26b": ModelConfig(
                    name="gemma-4-26b",
                    category="fallback",
                    rate_limit=RateLimit(rpm=15, tpm=999999, rpd=1500),
                    performance_score=8.5,
                    cost_efficiency=6.5
                ),
                "gemma-2-27b": ModelConfig(
                    name="gemma-2-27b",
                    category="fallback",
                    rate_limit=RateLimit(rpm=30, tpm=15000, rpd=14400),
                    performance_score=8.7,
                    cost_efficiency=8.5
                ),
                "gemma-4-31b": ModelConfig(
                    name="gemma-4-31b",
                    category="fallback",
                    rate_limit=RateLimit(rpm=15, tpm=999999, rpd=1500),
                    performance_score=9.2,
                    cost_efficiency=6.0
                )
            }
            
            logger.info(f"Loaded {len(self.api_keys)} API keys and {len(self.models)} models")
            
        except FileNotFoundError:
            logger.warning(f"Config file {self.config_path} not found")
            # Fall back to GEMINI_API_KEY env var
            env_key = os.getenv("GEMINI_API_KEY")
            if env_key:
                logger.info("Using GEMINI_API_KEY from environment")
                self._add_api_key(env_key)
            else:
                logger.error("No GEMINI_API_KEY in .env either")
                self.create_default_config()
        except Exception as e:
            logger.error(f"Error loading config: {e}")

    def _add_api_key(self, api_key: str):
        if not api_key or api_key.startswith("YOUR_") or api_key == "GEMINI_API_KEY":
            return
        self.api_keys[api_key] = APIKeyStatus(
            key=api_key,
            last_used=datetime.min,
            daily_requests=0,
            daily_tokens=0,
            minute_requests=0,
            minute_tokens=0,
            last_minute_reset=datetime.now(),
            last_day_reset=datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        )
        self.key_health_scores[api_key] = 1.0

    def create_default_config(self):
        """Create default configuration file"""
        default_config = {
            "api_keys": [],
            "settings": {
                "auto_rotate_keys": True,
                "prefer_high_performance": True,
                "max_retries": 3,
                "retry_delay": 1.0
            }
        }
        
        with open(self.config_path, 'w') as f:
            json.dump(default_config, f, indent=2)
        
        logger.info(f"Created default config at {self.config_path}")
        
    def get_available_models(self, category: Optional[str] = None) -> List[str]:
        """Get list of available models, optionally filtered by category"""
        available = []
        for model_name, model_config in self.models.items():
            if category and model_config.category != category:
                continue
            available.append(model_name)
        
        # Sort by performance score (highest first)
        available.sort(key=lambda x: self.models[x].performance_score, reverse=True)
        return available
    
    def check_rate_limits(self, api_key: str, model_name: str, estimated_tokens: int = 0) -> Tuple[bool, str]:
        """Check if API key and model are within rate limits"""
        if api_key not in self.api_keys:
            return False, "API key not found"
            
        if model_name not in self.models:
            return False, "Model not found"
            
        key_status = self.api_keys[api_key]
        model_config = self.models[model_name]
        
        now = datetime.now()
        
        # Check if key is banned
        if key_status.banned_until and now < key_status.banned_until:
            return False, f"API key banned until {key_status.banned_until}"
            
        # Reset counters if needed
        if (now - key_status.last_minute_reset).seconds >= 60:
            key_status.minute_requests = 0
            key_status.minute_tokens = 0
            key_status.last_minute_reset = now
            
        if now.date() > key_status.last_day_reset.date():
            key_status.daily_requests = 0
            key_status.daily_tokens = 0
            key_status.last_day_reset = now
            key_status.banned_until = None  # Reset ban on new day
        
        # Check model cooldown (for 503 high demand)
        if model_name in self.model_cooldowns and now < self.model_cooldowns[model_name]:
            return False, f"Model {model_name} is in cooldown until {self.model_cooldowns[model_name]}"

        # Check rate limits
        if key_status.minute_requests >= model_config.rate_limit.rpm:
            return False, "Minute request limit exceeded"
            
        if key_status.minute_tokens + estimated_tokens >= model_config.rate_limit.tpm:
            return False, "Minute token limit exceeded"
            
        if key_status.daily_requests >= model_config.rate_limit.rpd:
            return False, "Daily request limit exceeded"
            
        return True, "OK"
    
    def update_usage(self, api_key: str, model_name: str, tokens_used: int):
        """Update usage statistics after successful API call"""
        if api_key in self.api_keys:
            key_status = self.api_keys[api_key]
            key_status.last_used = datetime.now()
            key_status.minute_requests += 1
            key_status.minute_tokens += tokens_used
            key_status.daily_requests += 1
            key_status.daily_tokens += tokens_used
    
    def handle_rate_limit_error(self, api_key: str, model_name: str, error_msg: str):
        """Update health scores and ban keys/models on failure"""
        if api_key in self.api_keys:
            key_status = self.api_keys[api_key]
            
            # Decrease health score
            self.key_health_scores[api_key] = max(0, self.key_health_scores.get(api_key, 100) - 20)
            
            # 503 Service Unavailable / High Demand (Model level failure)
            if "503" in error_msg or "high demand" in error_msg.lower():
                logger.warning(f"🚨 Model {model_name} is under high demand. Rotating model globally.")
                # Ban the model globally for 3 minutes to let demand spike pass
                self.model_cooldowns[model_name] = datetime.now() + timedelta(minutes=3)
                # Also penalize the key slightly
                key_status.status = ModelStatus.RATE_LIMITED
                key_status.banned_until = datetime.now() + timedelta(seconds=30)
                
            # 404 Model Not Found / Unsupported (Key-level model restriction)
            elif "404" in error_msg or "not found" in error_msg.lower() or "not supported" in error_msg.lower():
                logger.warning(f"🚫 Key {api_key[:10]}... does not support model {model_name}. Banning model for this key.")
                if api_key not in self.key_unsupported_models:
                    self.key_unsupported_models[api_key] = set()
                self.key_unsupported_models[api_key].add(model_name)
                
            # 429 Rate Limit (Key level failure)
            elif "429" in error_msg or "rate limit" in error_msg.lower():
                if "daily" in error_msg.lower():
                    logger.warning(f"🚫 Key {api_key[:10]}... hit DAILY limit.")
                    key_status.status = ModelStatus.BANNED
                    key_status.banned_until = datetime.now() + timedelta(hours=24)
                else:
                    logger.warning(f"⏳ Key {api_key[:10]}... hit RPM limit.")
                    key_status.status = ModelStatus.RATE_LIMITED
                    key_status.banned_until = datetime.now() + timedelta(minutes=1)
            else:
                # General error, penalize health but don't ban yet
                self.key_health_scores[api_key] = max(0, self.key_health_scores.get(api_key, 100) - 10)
    
    def get_best_available_key_model(self, category: Optional[str] = None, estimated_tokens: int = 0, target_model: Optional[str] = None) -> Tuple[Optional[str], Optional[str]]:
        """Get the best available API key and model combination with health-based rotation"""
        if target_model:
            available_models = [target_model]
        else:
            available_models = self.get_available_models(category)
            # If primary category is exhausted, append fallback models
            if category and category != "fallback":
                fallback_models = self.get_available_models("fallback")
                available_models.extend([m for m in fallback_models if m not in available_models])
        
        if not available_models:
            return None, None
        
        # Sort keys by health score and availability
        healthy_keys = sorted(
            [key for key in self.api_keys.keys()],
            key=lambda k: self.key_health_scores.get(k, 0),
            reverse=True
        )
        
        # Try each model in priority order
        for model_name in available_models:
            # Check if model is on global cooldown
            if model_name in self.model_cooldowns and datetime.now() < self.model_cooldowns[model_name]:
                continue
            # Try each API key by health score
            for api_key in healthy_keys:
                # Check if model is unsupported by this specific key
                if api_key in self.key_unsupported_models and model_name in self.key_unsupported_models[api_key]:
                    continue
                can_use, reason = self.check_rate_limits(api_key, model_name, estimated_tokens)
                if can_use:
                    return api_key, model_name
                    
        return None, None
    
    async def make_api_call(self, prompt: str, category: str = "text", model_name: Optional[str] = None, **kwargs) -> Dict:
        """Make API call with automatic retry and key rotation"""
        estimated_tokens = len(prompt.split()) * 4  # Rough estimate
        
        # If specific model requested, try it first
        api_key, selected_model = self.get_best_available_key_model(category, estimated_tokens, target_model=model_name)
            
        print(f"[TRACE] Gemini Manager Selected Model: {selected_model}")
        if not api_key or not selected_model:
            return {
                "error": "No available API keys or models within rate limits",
                "status": "rate_limited"
            }
        
        # Make the API call
        try:
            result = await self._call_gemini_api(api_key, selected_model, prompt, **kwargs)
            
            # Update usage on success
            
            # Update usage on success
            tokens_used = result.get("tokens_used", estimated_tokens)
            self.update_usage(api_key, selected_model, tokens_used)
            
            return {
                "content": result,
                "model": selected_model,
                "api_key": api_key[:10] + "...",
                "status": "success"
            }
            
        except Exception as e:
            error_msg = str(e)
            self.handle_rate_limit_error(api_key, selected_model, error_msg)
            
            # Recursive retry with a limit to avoid infinite loops
            retry_count = kwargs.get("retry_count", 0)
            if retry_count < 3:
                # Try fallback - get_best_available_key_model will now return a DIFFERENT key
                fallback_key, fallback_model = self.get_best_available_key_model(category, estimated_tokens)
                if fallback_key and (fallback_key != api_key or fallback_model != selected_model):
                    logger.info(f"Retrying with fallback (Key: {fallback_key[:10]}..., Model: {fallback_model})")
                    kwargs["retry_count"] = retry_count + 1
                    return await self.make_api_call(prompt, category, None, **kwargs)
            
            return {
                "error": error_msg,
                "status": "error",
                "model": selected_model,
                "api_key": api_key[:10] + "..."
            }
    
    async def _call_gemini_api(self, api_key: str, model_name: str, prompt: str, image_data: Optional[str] = None, **kwargs):
        """Actual API call to Gemini with Multimodal support"""
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent"
        headers = {
            "Content-Type": "application/json",
            "x-goog-api-key": api_key
        }
        
        # Prepare parts
        parts = [{"text": prompt}]
        if image_data:
            parts.append({
                "inline_data": {
                    "mime_type": "image/jpeg",
                    "data": image_data
                }
            })
            
        data = {
            "contents": [{"parts": parts}],
            "generationConfig": {
                "temperature": kwargs.get("temperature", 0.1),
                "maxOutputTokens": kwargs.get("max_tokens", 2048)
            }
        }
        
        async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=False)) as session:
            async with session.post(url, json=data, headers=headers) as response:
                if response.status == 200:
                    result = await response.json()
                    return result
                else:
                    error_text = await response.text()
                    raise Exception(f"API Error {response.status}: {error_text}")
    
    def get_usage_stats(self) -> Dict:
        """Get current usage statistics"""
        stats = {
            "total_keys": len(self.api_keys),
            "available_keys": 0,
            "rate_limited_keys": 0,
            "banned_keys": 0,
            "models": {}
        }
        
        for key_status in self.api_keys.values():
            if key_status.status == ModelStatus.AVAILABLE:
                stats["available_keys"] += 1
            elif key_status.status == ModelStatus.RATE_LIMITED:
                stats["rate_limited_keys"] += 1
            elif key_status.status == ModelStatus.BANNED:
                stats["banned_keys"] += 1
        
        for model_name, model_config in self.models.items():
            stats["models"][model_name] = {
                "category": model_config.category,
                "performance_score": model_config.performance_score,
                "rate_limits": asdict(model_config.rate_limit)
            }
        
        return stats
