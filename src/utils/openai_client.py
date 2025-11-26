"""
OpenAI Client Utility
Robust client for OpenAI API with retry logic, error handling, and cost tracking
"""

import os
import time
import logging
from datetime import datetime
from typing import Optional, List, Dict, Any, Union
from dataclasses import dataclass, field
from functools import wraps

from dotenv import load_dotenv
from openai import OpenAI, RateLimitError, APIConnectionError, APITimeoutError, APIError
import tiktoken

load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class UsageStats:
    """Track API usage statistics"""
    total_requests: int = 0
    total_tokens: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_cost: float = 0.0
    requests_by_model: Dict[str, int] = field(default_factory=dict)
    tokens_by_model: Dict[str, int] = field(default_factory=dict)
    cost_by_model: Dict[str, float] = field(default_factory=dict)


# Pricing per 1K tokens (as of 2024, update as needed)
PRICING = {
    "gpt-4": {"input": 0.03, "output": 0.06},
    "gpt-4-turbo": {"input": 0.01, "output": 0.03},
    "gpt-4-turbo-preview": {"input": 0.01, "output": 0.03},
    "gpt-3.5-turbo": {"input": 0.0015, "output": 0.002},
    "gpt-3.5-turbo-16k": {"input": 0.003, "output": 0.004},
    "text-embedding-ada-002": {"input": 0.0001, "output": 0.0},
    "text-embedding-3-small": {"input": 0.00002, "output": 0.0},
    "text-embedding-3-large": {"input": 0.00013, "output": 0.0},
}


def retry_with_exponential_backoff(
    max_retries: int = 5,
    initial_delay: float = 1.0,
    max_delay: float = 60.0,
    exponential_base: float = 2.0,
):
    """
    Decorator for retrying API calls with exponential backoff
    
    Args:
        max_retries: Maximum number of retry attempts
        initial_delay: Initial delay in seconds
        max_delay: Maximum delay in seconds
        exponential_base: Base for exponential backoff calculation
    """
    def decorator(func):
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            delay = initial_delay
            last_exception = None
            
            for attempt in range(max_retries + 1):
                try:
                    return func(self, *args, **kwargs)
                except RateLimitError as e:
                    if attempt == max_retries:
                        logger.error(f"Rate limit exceeded after {max_retries} retries")
                        raise
                    
                    # Check if response includes retry-after header
                    retry_after = None
                    try:
                        if hasattr(e, 'response') and hasattr(e.response, 'headers'):
                            retry_after = e.response.headers.get('retry-after')
                    except (AttributeError, TypeError):
                        pass
                    
                    if retry_after:
                        try:
                            delay = float(retry_after)
                        except (ValueError, TypeError):
                            delay = min(delay * exponential_base, max_delay)
                    else:
                        delay = min(delay * exponential_base, max_delay)
                    
                    logger.warning(
                        f"Rate limit hit. Retrying in {delay:.2f}s "
                        f"(attempt {attempt + 1}/{max_retries})"
                    )
                    time.sleep(delay)
                    last_exception = e
                    
                except (APIConnectionError, APITimeoutError) as e:
                    if attempt == max_retries:
                        logger.error(f"Connection/timeout error after {max_retries} retries: {e}")
                        raise
                    
                    delay = min(delay * exponential_base, max_delay)
                    logger.warning(
                        f"Connection/timeout error. Retrying in {delay:.2f}s "
                        f"(attempt {attempt + 1}/{max_retries}): {e}"
                    )
                    time.sleep(delay)
                    last_exception = e
                    
                except APIError as e:
                    # Don't retry on client errors (4xx) except rate limits
                    status_code = None
                    try:
                        if hasattr(e, 'response') and hasattr(e.response, 'status_code'):
                            status_code = e.response.status_code
                    except (AttributeError, TypeError):
                        pass
                    
                    if status_code and 400 <= status_code < 500 and status_code != 429:
                        logger.error(f"Client error (not retrying): {e}")
                        raise
                    
                    if attempt == max_retries:
                        logger.error(f"API error after {max_retries} retries: {e}")
                        raise
                    
                    delay = min(delay * exponential_base, max_delay)
                    logger.warning(
                        f"API error. Retrying in {delay:.2f}s "
                        f"(attempt {attempt + 1}/{max_retries}): {e}"
                    )
                    time.sleep(delay)
                    last_exception = e
                    
                except Exception as e:
                    # Don't retry on unknown errors
                    logger.error(f"Unexpected error: {e}")
                    raise
            
            # If we exhausted retries, raise last exception
            if last_exception:
                raise last_exception
                
        return wrapper
    return decorator


class OpenAIClient:
    """
    Robust OpenAI client with retry logic, error handling, and cost tracking
    """
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        max_retries: int = 5,
        timeout: float = 60.0,
    ):
        """
        Initialize OpenAI client
        
        Args:
            api_key: OpenAI API key (defaults to OPENAI_API_KEY env var)
            max_retries: Maximum retry attempts for API calls
            timeout: Request timeout in seconds
        """
        self.api_key = api_key or os.getenv('OPENAI_API_KEY')
        
        if not self.api_key:
            raise ValueError(
                "OpenAI API key not found. Set OPENAI_API_KEY environment variable "
                "or pass api_key parameter."
            )
        
        self.client = OpenAI(api_key=self.api_key, timeout=timeout)
        self.max_retries = max_retries
        self.timeout = timeout
        self.logger = logging.getLogger(__name__)
        
        # Initialize usage tracking
        self.stats = UsageStats()
        
        # Initialize token encoders cache
        self._encoders: Dict[str, tiktoken.Encoding] = {}
        
        self.logger.info("OpenAI client initialized")
    
    def _get_encoding(self, model: str) -> tiktoken.Encoding:
        """Get or create tokenizer encoding for a model"""
        # Map model names to encoding names
        encoding_map = {
            "gpt-4": "cl100k_base",
            "gpt-4-turbo": "cl100k_base",
            "gpt-4-turbo-preview": "cl100k_base",
            "gpt-3.5-turbo": "cl100k_base",
            "gpt-3.5-turbo-16k": "cl100k_base",
            "text-embedding-ada-002": "cl100k_base",
            "text-embedding-3-small": "cl100k_base",
            "text-embedding-3-large": "cl100k_base",
        }
        
        encoding_name = encoding_map.get(model, "cl100k_base")
        
        if encoding_name not in self._encoders:
            self._encoders[encoding_name] = tiktoken.get_encoding(encoding_name)
        
        return self._encoders[encoding_name]
    
    def count_tokens(
        self,
        text: Union[str, List[Dict[str, str]]],
        model: str = "gpt-3.5-turbo"
    ) -> int:
        """
        Count tokens in text or chat messages
        
        Args:
            text: Text string or list of chat messages
            model: Model name for token counting
            
        Returns:
            Number of tokens
        """
        encoding = self._get_encoding(model)
        
        if isinstance(text, str):
            return len(encoding.encode(text))
        
        # Count tokens in chat messages
        # Format: [{"role": "user", "content": "..."}, ...]
        tokens_per_message = 3  # Every message follows: <|start|>{role/name}\n{content}<|end|>\n
        tokens_per_name = 1  # If there's a name, the role is omitted
        
        num_tokens = 0
        for message in text:
            num_tokens += tokens_per_message
            for key, value in message.items():
                num_tokens += len(encoding.encode(str(value)))
                if key == "name":
                    num_tokens += tokens_per_name
        
        num_tokens += 3  # Every reply is primed with <|start|>assistant<|message|>
        return num_tokens
    
    def _calculate_cost(
        self,
        model: str,
        prompt_tokens: int,
        completion_tokens: int = 0
    ) -> float:
        """
        Calculate cost for API call
        
        Args:
            model: Model name
            prompt_tokens: Number of prompt tokens
            completion_tokens: Number of completion tokens
            
        Returns:
            Cost in USD
        """
        # Get base model name (remove version suffixes)
        base_model = model.split("-", 1)[0] + "-" + model.split("-", 1)[1].split(":")[0] if "-" in model else model
        
        # Find matching pricing (exact match or fallback)
        pricing = PRICING.get(model) or PRICING.get(base_model)
        
        if not pricing:
            self.logger.warning(f"Pricing not found for model {model}, using gpt-3.5-turbo pricing")
            pricing = PRICING["gpt-3.5-turbo"]
        
        input_cost = (prompt_tokens / 1000) * pricing["input"]
        output_cost = (completion_tokens / 1000) * pricing["output"]
        
        return input_cost + output_cost
    
    def _log_api_call(
        self,
        method: str,
        model: str,
        prompt_tokens: int,
        completion_tokens: int = 0,
        cost: float = 0.0,
        duration: float = 0.0
    ):
        """Log API call with timestamp and details"""
        timestamp = datetime.now().isoformat()
        self.logger.info(
            f"[{timestamp}] OpenAI API Call - "
            f"Method: {method}, Model: {model}, "
            f"Tokens: {prompt_tokens}+{completion_tokens}={prompt_tokens + completion_tokens}, "
            f"Cost: ${cost:.6f}, Duration: {duration:.2f}s"
        )
    
    def _update_stats(
        self,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
        cost: float
    ):
        """Update usage statistics"""
        self.stats.total_requests += 1
        self.stats.total_tokens += prompt_tokens + completion_tokens
        self.stats.prompt_tokens += prompt_tokens
        self.stats.completion_tokens += completion_tokens
        self.stats.total_cost += cost
        
        # Update per-model stats
        self.stats.requests_by_model[model] = self.stats.requests_by_model.get(model, 0) + 1
        self.stats.tokens_by_model[model] = self.stats.tokens_by_model.get(model, 0) + prompt_tokens + completion_tokens
        self.stats.cost_by_model[model] = self.stats.cost_by_model.get(model, 0.0) + cost
    
    @retry_with_exponential_backoff(max_retries=5)
    def chat_completion(
        self,
        messages: List[Dict[str, str]],
        model: str = "gpt-3.5-turbo",
        temperature: float = 1.0,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Create a chat completion with retry logic and error handling
        
        Args:
            messages: List of message dicts with 'role' and 'content'
            model: Model to use (default: gpt-3.5-turbo)
            temperature: Sampling temperature (0-2)
            max_tokens: Maximum tokens to generate
            **kwargs: Additional parameters for chat.completions.create
            
        Returns:
            Response dictionary with content and metadata
            
        Raises:
            ValueError: If messages are invalid
            APIError: If API call fails after retries
        """
        start_time = time.time()
        
        if not messages or not isinstance(messages, list):
            raise ValueError("Messages must be a non-empty list")
        
        # Count tokens before API call
        estimated_tokens = self.count_tokens(messages, model)
        self.logger.info(f"Creating chat completion with {estimated_tokens} estimated tokens")
        
        try:
            # Make API call
            response = self.client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                **kwargs
            )
            
            # Extract usage information
            usage = response.usage
            prompt_tokens = usage.prompt_tokens
            completion_tokens = usage.completion_tokens
            total_tokens = usage.total_tokens
            
            # Get response content
            content = response.choices[0].message.content
            
            # Calculate cost
            cost = self._calculate_cost(model, prompt_tokens, completion_tokens)
            
            # Calculate duration
            duration = time.time() - start_time
            
            # Log and update stats
            self._log_api_call("chat_completion", model, prompt_tokens, completion_tokens, cost, duration)
            self._update_stats(model, prompt_tokens, completion_tokens, cost)
            
            return {
                "content": content,
                "model": model,
                "usage": {
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens,
                    "total_tokens": total_tokens
                },
                "cost": cost,
                "duration": duration,
                "response_id": response.id,
                "finish_reason": response.choices[0].finish_reason
            }
            
        except Exception as e:
            duration = time.time() - start_time
            self.logger.error(f"Chat completion failed after {duration:.2f}s: {e}")
            raise
    
    @retry_with_exponential_backoff(max_retries=5)
    def create_embedding(
        self,
        text: Union[str, List[str]],
        model: str = "text-embedding-3-small",
        **kwargs
    ) -> Dict[str, Any]:
        """
        Create embeddings with retry logic and error handling
        
        Args:
            text: Single text string or list of text strings
            model: Embedding model to use (default: text-embedding-3-small)
            **kwargs: Additional parameters for embeddings.create
            
        Returns:
            Dictionary with embeddings and metadata
            
        Raises:
            ValueError: If text is invalid
            APIError: If API call fails after retries
        """
        start_time = time.time()
        
        # Normalize input to list
        if isinstance(text, str):
            texts = [text]
        elif isinstance(text, list) and len(text) > 0:
            texts = text
        else:
            raise ValueError("Text must be a non-empty string or list of strings")
        
        # Count tokens
        total_tokens = sum(self.count_tokens(t, model) for t in texts)
        self.logger.info(f"Creating embeddings for {len(texts)} text(s) with {total_tokens} estimated tokens")
        
        try:
            # Make API call
            response = self.client.embeddings.create(
                model=model,
                input=texts,
                **kwargs
            )
            
            # Extract usage information
            usage = response.usage
            prompt_tokens = usage.prompt_tokens
            
            # Get embeddings
            embeddings = [item.embedding for item in response.data]
            
            # For single input, return single embedding
            if isinstance(text, str):
                embeddings = embeddings[0]
            
            # Calculate cost
            cost = self._calculate_cost(model, prompt_tokens, 0)
            
            # Calculate duration
            duration = time.time() - start_time
            
            # Log and update stats
            self._log_api_call("create_embedding", model, prompt_tokens, 0, cost, duration)
            self._update_stats(model, prompt_tokens, 0, cost)
            
            return {
                "embeddings": embeddings,
                "model": model,
                "usage": {
                    "prompt_tokens": prompt_tokens,
                    "total_tokens": prompt_tokens
                },
                "cost": cost,
                "duration": duration
            }
            
        except Exception as e:
            duration = time.time() - start_time
            self.logger.error(f"Embedding creation failed after {duration:.2f}s: {e}")
            raise
    
    def get_usage_stats(self) -> Dict[str, Any]:
        """
        Get current usage statistics
        
        Returns:
            Dictionary with usage statistics
        """
        return {
            "total_requests": self.stats.total_requests,
            "total_tokens": self.stats.total_tokens,
            "prompt_tokens": self.stats.prompt_tokens,
            "completion_tokens": self.stats.completion_tokens,
            "total_cost": self.stats.total_cost,
            "requests_by_model": dict(self.stats.requests_by_model),
            "tokens_by_model": dict(self.stats.tokens_by_model),
            "cost_by_model": dict(self.stats.cost_by_model)
        }
    
    def reset_stats(self):
        """Reset usage statistics"""
        self.stats = UsageStats()
        self.logger.info("Usage statistics reset")


# Usage example
if __name__ == "__main__":
    # Initialize client
    client = OpenAIClient()
    
    # Test chat completion
    messages = [
        {"role": "user", "content": "What is machine learning?"}
    ]
    
    try:
        response = client.chat_completion(messages, model="gpt-3.5-turbo")
        print(f"\nResponse: {response['content'][:200]}...")
        print(f"Cost: ${response['cost']:.6f}")
    except Exception as e:
        print(f"Error: {e}")
    
    # Test embedding
    try:
        embedding_response = client.create_embedding(
            "This is a test sentence for embedding."
        )
        print(f"\nEmbedding dimension: {len(embedding_response['embeddings'])}")
        print(f"Cost: ${embedding_response['cost']:.6f}")
    except Exception as e:
        print(f"Error: {e}")
    
    # Print usage stats
    stats = client.get_usage_stats()
    print(f"\nUsage Stats:")
    print(f"  Total requests: {stats['total_requests']}")
    print(f"  Total tokens: {stats['total_tokens']}")
    print(f"  Total cost: ${stats['total_cost']:.6f}")

