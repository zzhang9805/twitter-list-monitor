#!/usr/bin/env python3
"""
Twitter List Monitor - Main Entry Point

This script monitors Twitter lists and generates daily summaries using AI.

Usage:
    python twitter_monitor.py                    # Run for today
    python twitter_monitor.py --date 2026-03-01  # Run for specific date
    python twitter_monitor.py --dry-run           # Test without API calls
    python twitter_monitor.py --verbose          # Enable verbose logging
"""

import argparse
import logging
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from config_loader import Config, ConfigError, load_config
from markdown_generator import generate_daily_markdown, save_markdown
from openrouter_client import OpenRouterClient
from twitter_api import TwitterAPI, TwitterAPIError


def setup_logging(verbose: bool = False, log_file: Optional[str] = None) -> logging.Logger:
    """Setup logging configuration."""
    level = logging.DEBUG if verbose else logging.INFO
    
    handlers = [logging.StreamHandler(sys.stdout)]
    if log_file:
        Path(log_file).parent.mkdir(parents=True, exist_ok=True)
        handlers.append(logging.FileHandler(log_file))
    
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=handlers
    )
    
    return logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Twitter List Monitor - Generate daily summaries from Twitter lists"
    )
    
    parser.add_argument(
        "--date",
        type=str,
        default=None,
        help="Date to monitor (YYYY-MM-DD format). Default: today"
    )
    
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run without making API calls (for testing)"
    )
    
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose logging"
    )
    
    parser.add_argument(
        "--config",
        type=str,
        default=None,
        help="Path to config.yaml file"
    )
    
    parser.add_argument(
        "--max-tweets",
        type=int,
        default=100,
        help="Maximum tweets to fetch per user (default: 100)"
    )
    
    return parser.parse_args()


def get_cutoff_time(hours: int = 24) -> datetime:
    """Get the cutoff datetime for filtering tweets."""
    utc_tz = timezone(timedelta(hours=0))
    return datetime.now(utc_tz) - timedelta(hours=hours)


def parse_tweet_datetime(created_at: str) -> Optional[datetime]:
    """Parse tweet created_at string to datetime object."""
    if not created_at:
        return None
    
    # Try format: "Mon Mar 02 20:55:31 +0000 2026"
    try:
        return datetime.strptime(created_at, "%a %b %d %H:%M:%S %z %Y")
    except ValueError:
        pass
    
    # Try ISO format: "2026-03-02T20:55:31.000Z"
    try:
        dt = datetime.strptime(created_at, "%Y-%m-%dT%H:%M:%S.000Z")
        return dt.replace(tzinfo=timezone(timedelta(hours=0)))
    except ValueError:
        pass
    
    return None


def filter_tweets_by_time(tweets: List[dict], hours: int = 24) -> List[dict]:
    """Filter tweets to only include those within the specified time window."""
    cutoff = get_cutoff_time(hours)
    filtered_tweets = []
    
    for tweet in tweets:
        created_at = tweet.get("raw", {}).get("createdAt") or tweet.get("raw", {}).get("created_at", "")
        if not created_at:
            continue
            
        tweet_dt = parse_tweet_datetime(created_at)
        if tweet_dt and tweet_dt >= cutoff:
            filtered_tweets.append(tweet)
    
    return filtered_tweets


def normalize_tweet(tweet: dict, include_retweets: bool = True, include_quotes: bool = True) -> Optional[dict]:
    """Normalize tweet data from TwitterAPI.io format."""
    if not isinstance(tweet, dict):
        return None

    text = tweet.get("text") or tweet.get("full_text") or tweet.get("content", "")
    
    is_retweet = text.startswith("RT ") or tweet.get("isRetweet") or tweet.get("retweeted_status") is not None or tweet.get("retweeted_tweet") is not None
    
    is_quote = tweet.get("is_quote_status", False) or tweet.get("isQuote", False) or tweet.get("quoted_status") is not None or tweet.get("quoted_tweet") is not None
    
    if not include_retweets and is_retweet:
        return None
    if not include_quotes and is_quote:
        return None
    
    author_data = tweet.get("author") or tweet.get("user") or {}
    author = author_data.get("name") or author_data.get("userName") or author_data.get("username") or "unknown" if isinstance(author_data, dict) else "unknown"
    
    created_at = tweet.get("createdAt") or tweet.get("created_at", "")
    time_str = ""
    if created_at:
        try:
            dt = datetime.strptime(created_at, "%a %b %d %H:%M:%S %z %Y")
            time_str = dt.strftime("%b %d, %Y at %I:%M %p")
        except ValueError:
            try:
                dt = datetime.strptime(created_at, "%Y-%m-%dT%H:%M:%S.000Z")
                time_str = dt.strftime("%b %d, %Y at %I:%M %p")
            except ValueError:
                time_str = created_at
    
    likes = tweet.get("likes") or tweet.get("favorite_count", 0)
    retweets = tweet.get("retweets") or tweet.get("retweet_count", 0)
    tweet_id = tweet.get("id") or tweet.get("id_str", "")
    urls = tweet.get("urls") or tweet.get("entities", {}).get("urls") or []
    
    return {
        "author": author,
        "time": time_str,
        "content": text,
        "retweets": retweets,
        "likes": likes,
        "is_retweet": is_retweet,
        "is_quote": is_quote,
        "tweet_id": tweet_id,
        "urls": urls,
        "retweeted_content": None,
        "article_title": None,
        "article_full_content": None,
        "quoted_content": None,
        "raw": tweet
    }


def is_article_tweet(urls: List[dict]) -> bool:
    """Check if tweet contains an article URL."""
    if not urls:
        return False
    for url_obj in urls:
        expanded_url = url_obj.get("expanded_url") or url_obj.get("url") or ""
        if "/i/article/" in expanded_url:
            return True
    return False


def enrich_tweets(
    tweets: List[dict],
    twitter_api: TwitterAPI,
    logger: logging.Logger
) -> List[dict]:
    """Enrich tweets with full RT content and article content."""
    if not tweets:
        return tweets
    
    rt_tweet_ids = []
    article_tweet_ids = []
    quote_tweet_ids = []
    
    for tweet in tweets:
        if tweet.get("is_retweet") and tweet.get("content", "").startswith("RT "):
            tweet_id = tweet.get("tweet_id")
            if tweet_id:
                rt_tweet_ids.append(str(tweet_id))
        
        urls = tweet.get("urls", [])
        if is_article_tweet(urls):
            tweet_id = tweet.get("tweet_id")
            if tweet_id:
                article_tweet_ids.append(str(tweet_id))
        
        if tweet.get("is_quote"):
            tweet_id = tweet.get("tweet_id")
            if tweet_id:
                quote_tweet_ids.append(str(tweet_id))
    
    logger.info(f"Enriching {len(tweets)} tweets (all RTs, Articles, and Quotes)")
    logger.info(f"  - RT tweets to enrich: {len(rt_tweet_ids)}")
    logger.info(f"  - Article tweets to enrich: {len(article_tweet_ids)}")
    logger.info(f"  - Quote tweets to enrich: {len(quote_tweet_ids)}")

    tweet_lookup = {str(tweet.get("tweet_id", "")): tweet for tweet in tweets}
    
    if rt_tweet_ids:
        try:
            rt_full_tweets = twitter_api.get_tweets_by_ids(rt_tweet_ids)
            for full_tweet in rt_full_tweets:
                tweet_id = str(full_tweet.get("id") or full_tweet.get("id_str", ""))
                if tweet_id in tweet_lookup:
                    retweeted_tweet = full_tweet.get("retweeted_tweet") or {}
                    original_text = retweeted_tweet.get("text") or retweeted_tweet.get("full_text") or ""
                    retweeted_status = full_tweet.get("retweeted_status") or {}
                    original_text = retweeted_status.get("text") or retweeted_status.get("full_text") or original_text
                    if original_text:
                        tweet_lookup[tweet_id]["retweeted_content"] = original_text
                        logger.debug(f"Enriched RT tweet {tweet_id}")
        except TwitterAPIError as e:
            logger.warning(f"Failed to enrich RT tweets: {e}")
    
    if article_tweet_ids:
        for tweet_id in article_tweet_ids:
            try:
                article_data = twitter_api.get_article(tweet_id)
                if article_data and tweet_id in tweet_lookup:
                    title = article_data.get("title", "")
                    preview_text = article_data.get("preview_text", "")
                    contents = article_data.get("contents", [])
                    
                    full_content_parts = []
                    if preview_text:
                        full_content_parts.append(preview_text)
                    for content_item in contents:
                        if isinstance(content_item, dict):
                            text = content_item.get("text") or ""
                            if text:
                                full_content_parts.append(text)
                        elif isinstance(content_item, str):
                            full_content_parts.append(content_item)
                    
                    full_content = "\n\n".join(full_content_parts)
                    
                    if title:
                        tweet_lookup[tweet_id]["article_title"] = title
                    if full_content:
                        tweet_lookup[tweet_id]["article_full_content"] = full_content
                    
                    logger.debug(f"Enriched article tweet {tweet_id}")
            except TwitterAPIError as e:
                logger.warning(f"Failed to enrich article tweet {tweet_id}: {e}")
    
    if quote_tweet_ids:
        try:
            quote_full_tweets = twitter_api.get_tweets_by_ids(quote_tweet_ids)
            for full_tweet in quote_full_tweets:
                tweet_id = str(full_tweet.get("id") or full_tweet.get("id_str", ""))
                if tweet_id in tweet_lookup:
                    quoted_tweet = full_tweet.get("quoted_tweet") or {}
                    quoted_text = quoted_tweet.get("text") or quoted_tweet.get("full_text") or ""
                    if quoted_text:
                        tweet_lookup[tweet_id]["quoted_content"] = quoted_text
                        logger.debug(f"Enriched quote tweet {tweet_id}")
        except TwitterAPIError as e:
            logger.warning(f"Failed to enrich quote tweets: {e}")
    
    return tweets


def fetch_list_data(
    twitter_api: TwitterAPI,
    list_id: str,
    max_tweets: int,
    include_retweets: bool,
    include_quotes: bool,
    logger: logging.Logger
) -> Dict[str, Any]:
    """Fetch all tweets for a Twitter list."""
    logger.info(f"Fetching data for list: {list_id}")
    
    try:
        members = twitter_api.get_list_members(list_id)
        logger.info(f"Found {len(members)} members in list {list_id}")
    except TwitterAPIError as e:
        logger.error(f"Failed to get list members for {list_id}: {e}")
        return {
            "list_id": list_id,
            "list_name": list_id,
            "members": {},
            "all_tweets": []
        }
    
    member_usernames = []
    for member in members:
        if isinstance(member, dict):
            username = member.get("userName") or member.get("username") or member.get("screen_name")
            if username:
                member_usernames.append(username)
    
    logger.info(f"Processing {len(member_usernames)} members: {member_usernames[:5]}...")
    
    all_tweets = []
    members_tweets: Dict[str, List[dict]] = {}
    
    for i, username in enumerate(member_usernames):
        logger.info(f"[{i+1}/{len(member_usernames)}] Fetching tweets for @{username}")
        
        try:
            tweets = twitter_api.get_user_tweets(username, max_tweets)
            
            normalized_tweets = []
            for tweet in tweets:
                normalized = normalize_tweet(
                    tweet, 
                    include_retweets=include_retweets,
                    include_quotes=include_quotes
                )
                if normalized:
                    normalized_tweets.append(normalized)
            
            if normalized_tweets:
                members_tweets[username] = normalized_tweets
                all_tweets.extend(normalized_tweets)
                logger.info(f"  -> Got {len(normalized_tweets)} tweets")
            else:
                logger.info(f"  -> No tweets (after filtering)")
                
        except TwitterAPIError as e:
            logger.warning(f"Failed to get tweets for @{username}: {e}")
            continue
    
    # Filter to last 24 hours only
    recent_tweets = filter_tweets_by_time(all_tweets, hours=24)
    cutoff_time = get_cutoff_time(24)
    logger.info(f"Filtered {len(all_tweets)} total tweets to {len(recent_tweets)} tweets in last 24 hours (before {cutoff_time.strftime('%Y-%m-%d %H:%M %Z')})")
    
    # Update members_tweets to only include recent tweets
    members_tweets_recent: Dict[str, List[dict]] = {}
    for username, tweets in members_tweets.items():
        recent_user_tweets = filter_tweets_by_time(tweets, hours=24)
        if recent_user_tweets:
            members_tweets_recent[username] = recent_user_tweets
    
    # Enrich RTs and Articles from recent tweets only
    if recent_tweets:
        logger.info(f"Starting tweet enrichment for {len(recent_tweets)} recent tweets...")
        recent_tweets = enrich_tweets(recent_tweets, twitter_api, logger)
    
    return {
        "list_id": list_id,
        "list_name": list_id,
        "members": members_tweets_recent,
        "all_tweets": recent_tweets
    }


def generate_ai_summaries(
    openrouter_client: OpenRouterClient,
    lists_data: List[Dict[str, Any]],
    logger: logging.Logger
) -> Dict[str, str]:
    """Generate AI summaries for each list."""
    summaries = {}
    
    for list_data in lists_data:
        list_id = list_data["list_id"]
        list_name = list_data["list_name"]
        all_tweets = list_data["all_tweets"]
        
        if not all_tweets:
            logger.warning(f"No tweets to summarize for list {list_id}")
            summaries[list_id] = "No tweets available for this list."
            continue
        
        logger.info(f"Generating AI summary for list {list_id} ({len(all_tweets)} tweets)")
        
        try:
            raw_tweets = [t.get("raw", t) for t in all_tweets[:50]]
            summary = openrouter_client.summarize_tweets(raw_tweets, list_name)
            summaries[list_id] = summary
            logger.info(f"Summary generated for list {list_id}")
        except Exception as e:
            logger.error(f"Failed to generate summary for {list_id}: {e}")
            summaries[list_id] = f"Summary generation failed: {str(e)}"
    
    return summaries


def build_tweets_by_list(lists_data: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """Build the tweets_by_list structure for markdown generator."""
    tweets_by_list = {}
    
    for list_data in lists_data:
        list_id = list_data["list_id"]
        tweets_by_list[list_id] = {
            "list_name": list_data["list_name"],
            "members": list_data["members"]
        }
    
    return tweets_by_list


def main():
    """Main entry point for Twitter List Monitor."""
    args = parse_args()
    
    if args.date:
        try:
            target_date = datetime.strptime(args.date, "%Y-%m-%d").date()
        except ValueError:
            print(f"Error: Invalid date format. Use YYYY-MM-DD (e.g., 2026-03-01)")
            sys.exit(1)
    else:
        target_date = datetime.now().date()
    
    date_str = target_date.strftime("%Y-%m-%d")
    
    try:
        config_path = Path(args.config) if args.config else None
        config = load_config(config_path)
    except ConfigError as e:
        print(f"Configuration Error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Error loading config: {e}")
        sys.exit(1)
    
    log_file = config.logging.get("log_file") if config.logging else None
    logger = setup_logging(verbose=args.verbose, log_file=log_file)
    
    logger.info("=" * 60)
    logger.info(f"Twitter List Monitor - Date: {date_str}")
    logger.info("=" * 60)
    
    api_key = config.twitter.get("api_key")
    bearer_token = config.twitter.get("bearer_token")
    list_ids = config.twitter.get("list_ids", [])
    output_dir = config.output.get("directory", "./info_stream")
    max_tweets_per_user = args.max_tweets
    include_retweets = config.output.get("include_retweets", True)
    include_quotes = config.output.get("include_quotes", True)
    api_delay = config.rate_limit.get("api_delay_seconds", 0.1)
    
    openrouter_api_key = config.openrouter.get("api_key")
    model = config.openrouter.get("model", "moonshotai/kimi-k2.5")
    
    logger.info(f"Configuration:")
    logger.info(f"  - List IDs: {list_ids}")
    logger.info(f"  - Output directory: {output_dir}")
    logger.info(f"  - Max tweets per user: {max_tweets_per_user}")
    logger.info(f"  - Include retweets: {include_retweets}")
    logger.info(f"  - Include quotes: {include_quotes}")
    logger.info(f"  - API delay: {api_delay}s")
    logger.info(f"  - Model: {model}")
    
    if args.dry_run:
        logger.info("\n*** DRY RUN MODE - No API calls will be made ***\n")
        logger.info("Would process the following lists:")
        for list_id in list_ids:
            logger.info(f"  - {list_id}")
        logger.info(f"\nWould output to: {output_dir}/{date_str}.md")
        logger.info("\nDry run completed successfully!")
        return
    
    logger.info("\nInitializing API clients...")
    
    twitter_api = TwitterAPI(api_key, delay_seconds=api_delay)
    openrouter_client = OpenRouterClient(openrouter_api_key, model=model)
    
    logger.info("Clients initialized")
    
    logger.info("\n" + "=" * 60)
    logger.info("Fetching data from Twitter lists...")
    logger.info("=" * 60)
    
    lists_data = []
    
    for i, list_id in enumerate(list_ids, 1):
        logger.info(f"\n[{i}/{len(list_ids)}] Processing list: {list_id}")
        
        list_data = fetch_list_data(
            twitter_api=twitter_api,
            list_id=list_id,
            max_tweets=max_tweets_per_user,
            include_retweets=include_retweets,
            include_quotes=include_quotes,
            logger=logger
        )
        
        lists_data.append(list_data)
        
        total_tweets = len(list_data["all_tweets"])
        logger.info(f"List {list_id} complete: {total_tweets} tweets from {len(list_data['members'])} members")
    
    logger.info("\n" + "=" * 60)
    logger.info("Generating AI summaries...")
    logger.info("=" * 60)
    
    summaries = generate_ai_summaries(openrouter_client, lists_data, logger)
    
    tweets_by_list = build_tweets_by_list(lists_data)
    
    combined_summary = []
    for list_data in lists_data:
        list_id = list_data["list_id"]
        list_name = list_data["list_name"]
        summary = summaries.get(list_id, "")
        
        combined_summary.append(f"### {list_name}")
        combined_summary.append("")
        combined_summary.append(summary)
        combined_summary.append("")
    
    full_ai_summary = "\n".join(combined_summary)
    
    logger.info("\n" + "=" * 60)
    logger.info("Generating Markdown document...")
    logger.info("=" * 60)
    
    markdown_content = generate_daily_markdown(
        tweets_by_list=tweets_by_list,
        date=date_str,
        ai_summary=full_ai_summary
    )
    
    output_path = save_markdown(
        content=markdown_content,
        output_dir=output_dir,
        date=date_str
    )
    
    logger.info(f"\n✓ Output saved to: {output_path}")
    
    total_tweets = sum(len(ld["all_tweets"]) for ld in lists_data)
    total_members = sum(len(ld["members"]) for ld in lists_data)
    
    logger.info("\n" + "=" * 60)
    logger.info("EXECUTION COMPLETE")
    logger.info("=" * 60)
    logger.info(f"Date: {date_str}")
    logger.info(f"Lists processed: {len(list_ids)}")
    logger.info(f"Members processed: {total_members}")
    logger.info(f"Total tweets: {total_tweets}")
    logger.info(f"Output: {output_path}")


if __name__ == "__main__":
    main()
