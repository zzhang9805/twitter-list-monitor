"""
TwitterAPI.io client module.

Provides methods to interact with TwitterAPI.io for fetching list members
and user tweets with rate limiting and retry logic.
"""

import time
import logging
from typing import List, Dict, Optional
import requests

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TwitterAPIError(Exception):
    """Base exception for TwitterAPI errors."""
    pass


class TwitterAPIRateLimitError(TwitterAPIError):
    """Raised when rate limit is exceeded."""
    pass


class TwitterAPIAuthError(TwitterAPIError):
    """Raised when authentication fails."""
    pass


class TwitterAPI:
    """
    Client for TwitterAPI.io API.
    
    Implements rate limiting and retry logic with exponential backoff.
    """
    
    BASE_URL = "https://api.twitterapi.io"
    MAX_RETRIES = 3
    RETRY_BACKOFF_FACTOR = 2  # Exponential backoff multiplier
    
    def __init__(self, api_key: str, delay_seconds: float = 0.1):
        """
        Initialize TwitterAPI client.
        
        Args:
            api_key: TwitterAPI.io API key
            delay_seconds: Delay between requests for rate limiting (default: 0.1s for QPS=20)
        """
        self.api_key = api_key
        self.delay_seconds = delay_seconds
        self.session = requests.Session()
        self.session.headers.update({
            "X-API-Key": api_key,
            "Content-Type": "application/json"
        })
        self._last_request_time = 0.0
    
    def _rate_limit(self):
        """Apply rate limiting between requests."""
        current_time = time.time()
        elapsed = current_time - self._last_request_time
        
        if elapsed < self.delay_seconds:
            sleep_time = self.delay_seconds - elapsed
            logger.debug(f"Rate limiting: sleeping {sleep_time:.3f}s")
            time.sleep(sleep_time)
        
        self._last_request_time = time.time()
    
    def _request_with_retry(
        self,
        method: str,
        url: str,
        params: Optional[Dict] = None,
        max_retries: int = MAX_RETRIES
    ) -> requests.Response:
        """
        Make HTTP request with retry logic and exponential backoff.
        
        Args:
            method: HTTP method (GET, POST, etc.)
            url: Request URL
            params: Query parameters
            max_retries: Maximum number of retry attempts
            
        Returns:
            Response object
            
        Raises:
            TwitterAPIError: On API errors after all retries exhausted
            TwitterAPIRateLimitError: When rate limited
            TwitterAPIAuthError: On authentication failure
        """
        self._rate_limit()
        
        for attempt in range(max_retries):
            try:
                logger.info(f"Request attempt {attempt + 1}/{max_retries}: {method} {url}")
                
                response = self.session.request(
                    method=method,
                    url=url,
                    params=params
                )
                
                # Handle specific status codes
                if response.status_code == 200:
                    return response
                elif response.status_code == 401:
                    raise TwitterAPIAuthError("Authentication failed. Check your API key.")
                elif response.status_code == 429:
                    # Rate limited - could implement wait logic here
                    raise TwitterAPIRateLimitError("Rate limit exceeded")
                elif response.status_code >= 500:
                    # Server error - retry with backoff
                    if attempt < max_retries - 1:
                        wait_time = self.RETRY_BACKOFF_FACTOR ** attempt
                        logger.warning(f"Server error {response.status_code}, retrying in {wait_time}s")
                        time.sleep(wait_time)
                        continue
                else:
                    # Other client errors
                    error_msg = f"API error {response.status_code}: {response.text}"
                    logger.error(error_msg)
                    raise TwitterAPIError(error_msg)
                    
            except requests.RequestException as e:
                if attempt < max_retries - 1:
                    wait_time = self.RETRY_BACKOFF_FACTOR ** attempt
                    logger.warning(f"Request failed: {e}, retrying in {wait_time}s")
                    time.sleep(wait_time)
                    continue
                raise TwitterAPIError(f"Request failed after {max_retries} attempts: {e}")
        
        raise TwitterAPIError(f"Request failed after {max_retries} attempts")
    
    def get_list_members(self, list_id: str) -> List[dict]:
        """
        Get members of a Twitter list.
        
        Args:
            list_id: Twitter list ID
            
        Returns:
            List of member user objects
            
        Raises:
            TwitterAPIError: On API errors
        """
        url = f"{self.BASE_URL}/twitter/list/members"
        params = {"list_id": list_id}
        
        logger.info(f"Fetching list members for list_id: {list_id}")
        
        response = self._request_with_retry("GET", url, params=params)
        
        try:
            data = response.json()
            
            # Handle TwitterAPI.io response structure
            # Typical response: { "members": [...] } or { "users": [...] } or { "data": [...] }
            if isinstance(data, dict):
                if "members" in data:
                    return data["members"]
                elif "users" in data:
                    return data["users"]
                elif "data" in data:
                    return data["data"]
                elif "results" in data:
                    return data["results"]
                else:
                    # Return the whole response as a list if it's a dict with users
                    logger.warning(f"Unexpected response structure: {list(data.keys())}")
                    return [data] if data else []
            elif isinstance(data, list):
                return data
            else:
                logger.warning(f"Unexpected response type: {type(data)}")
                return []
                
        except ValueError as e:
            raise TwitterAPIError(f"Failed to parse response: {e}")
    
    def get_user_tweets(self, username: str, max_tweets: int = 20) -> List[dict]:
        """
        Get recent tweets from a user.
        
        Args:
            username: Twitter username (without @)
            max_tweets: Maximum number of tweets to retrieve (default: 20)
            
        Returns:
            List of tweet objects
            
        Raises:
            TwitterAPIError: On API errors
        """
        url = f"{self.BASE_URL}/twitter/user/last_tweets"
        params = {
            "userName": username,
            "maxResults": max_tweets
        }
        
        logger.info(f"Fetching tweets for user: {username}, max: {max_tweets}")
        
        response = self._request_with_retry("GET", url, params=params)
        
        try:
            data = response.json()
            
            # Handle TwitterAPI.io response structure
            if isinstance(data, dict):
                # Check nested structure first: data.data.tweets
                if "data" in data and isinstance(data["data"], dict):
                    nested = data["data"]
                    if "tweets" in nested:
                        return nested["tweets"]
                    elif "data" in nested:
                        return nested["data"]
                    elif "results" in nested:
                        return nested["results"]
                # Check top-level
                if "tweets" in data:
                    return data["tweets"]
                elif "data" in data:
                    return data["data"]
                elif "results" in data:
                    return data["results"]
                else:
                    logger.warning(f"Unexpected response structure: {list(data.keys())}")
                    return [data] if data else []
            elif isinstance(data, list):
                return data
            else:
                logger.warning(f"Unexpected response type: {type(data)}")
                return []
                
        except ValueError as e:
            raise TwitterAPIError(f"Failed to parse response: {e}")
    
    def get_tweets_by_ids(self, tweet_ids: List[str]) -> List[dict]:
        """
        Get full tweet details by tweet IDs. Returns retweeted_tweet field for RT tweets.
        
        Args:
            tweet_ids: List of tweet IDs to fetch
            
        Returns:
            List of full tweet objects with retweeted_tweet field
            
        Raises:
            TwitterAPIError: On API errors
        """
        if not tweet_ids:
            return []
            
        # TwitterAPI.io accepts comma-separated tweet IDs
        tweet_ids_str = ",".join(tweet_ids)
        url = f"{self.BASE_URL}/twitter/tweets"
        params = {"tweet_ids": tweet_ids_str}
        
        logger.info(f"Fetching {len(tweet_ids)} tweets by IDs")
        
        response = self._request_with_retry("GET", url, params=params)
        
        try:
            data = response.json()
            
            # Handle TwitterAPI.io response structure
            if isinstance(data, dict):
                # Check for nested tweets array
                if "data" in data and isinstance(data["data"], dict):
                    nested = data["data"]
                    if "tweets" in nested:
                        return nested["tweets"]
                    elif "data" in nested:
                        return nested["data"]
                # Check top-level
                if "tweets" in data:
                    return data["tweets"]
                elif "data" in data:
                    return data["data"]
                else:
                    logger.warning(f"Unexpected response structure for get_tweets_by_ids: {list(data.keys())}")
                    return []
            elif isinstance(data, list):
                return data
            else:
                logger.warning(f"Unexpected response type: {type(data)}")
                return []
                
        except ValueError as e:
            raise TwitterAPIError(f"Failed to parse response: {e}")
    
    def get_article(self, tweet_id: str) -> Optional[dict]:
        """
        Get full article content from a tweet (for Article tweets).
        
        Args:
            tweet_id: Twitter tweet ID
            
        Returns:
            Dict with title, preview_text, contents[] or None if not an article
            
        Raises:
            TwitterAPIError: On API errors
        """
        url = f"{self.BASE_URL}/twitter/article"
        params = {"tweet_id": tweet_id}
        
        logger.info(f"Fetching article for tweet_id: {tweet_id}")
        
        response = self._request_with_retry("GET", url, params=params)
        
        try:
            data = response.json()
            
            # Handle TwitterAPI.io response structure
            if isinstance(data, dict):
                # Check for article key (TwitterAPI.io returns {"article": {...}})
                if "article" in data and isinstance(data["article"], dict):
                    return data["article"]
                # Check nested structure
                if "data" in data and isinstance(data["data"], dict):
                    return data["data"]
                # Check top-level - return relevant article fields
                if "title" in data or "contents" in data:
                    return data
                # Not an article or no content
                return None
            else:
                return None
                
        except ValueError as e:
            logger.warning(f"Failed to parse article response: {e}")
            return None


# Example usage
if __name__ == "__main__":
    # Example: How to use the TwitterAPI client
    print("TwitterAPI.io client module")
    print("Usage:")
    print("  from twitter_api import TwitterAPI")
    print("  api = TwitterAPI('your-api-key', delay_seconds=0.1)")
    print("  members = api.get_list_members('list_id')")
    print("  tweets = api.get_user_tweets('username', max_tweets=20)")
