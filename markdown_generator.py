"""
Markdown Generator for Twitter List Monitor

Generates daily Markdown documents from Twitter list data.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional


def format_tweet_with_enrichment(tweet: dict) -> str:
    """Format a single tweet into Markdown with enriched content."""
    author = tweet.get('author', 'Unknown')
    time = tweet.get('time', '')
    content = tweet.get('content', '')
    retweets = tweet.get('retweets', 0)
    likes = tweet.get('likes', 0)
    is_retweet = tweet.get('is_retweet', False)
    is_quote = tweet.get('is_quote', False)
    
    retweeted_content = tweet.get('retweeted_content')
    article_title = tweet.get('article_title')
    article_full_content = tweet.get('article_full_content')
    quoted_content = tweet.get('quoted_content')
    
    lines = []
    
    if time:
        lines.append(f"**{author}** · {time}")
    else:
        lines.append(f"**{author}**")
    
    lines.append("")
    
    # Handle RT format with enriched content
    if is_retweet and content.startswith('RT '):
        lines.append(content)
        if retweeted_content:
            lines.append("")
            lines.append("**Original tweet:**")
            lines.append(retweeted_content)
    # Handle Article format with enriched content
    elif article_title or article_full_content:
        if article_title:
            lines.append(f"**{article_title}**")
            lines.append("")
        if article_full_content:
            lines.append(article_full_content)
        else:
            lines.append(content)
    # Handle Quote Tweet format with enriched content
    elif is_quote and quoted_content:
        lines.append(content)
        lines.append("")
        lines.append("**Quoted tweet:**")
        lines.append(quoted_content)
    else:
        lines.append(content)
    
    stats = []
    if retweets > 0:
        stats.append(f"🔁 {retweets}")
    if likes > 0:
        stats.append(f"❤️ {likes}")
    
    if stats:
        lines.append("")
        lines.append(" ".join(stats))
    
    return "\n".join(lines)


def format_tweet(tweet: dict) -> str:
    """Format a single tweet into Markdown."""
    author = tweet.get('author', 'Unknown')
    time = tweet.get('time', '')
    content = tweet.get('content', '')
    retweets = tweet.get('retweets', 0)
    likes = tweet.get('likes', 0)
    is_retweet = tweet.get('is_retweet', False)
    
    if is_retweet and content.startswith('RT '):
        pass
    
    lines = []
    
    if time:
        lines.append(f"**{author}** · {time}")
    else:
        lines.append(f"**{author}**")
    
    lines.append("")
    lines.append(content)
    
    stats = []
    if retweets > 0:
        stats.append(f"🔁 {retweets}")
    if likes > 0:
        stats.append(f"❤️ {likes}")
    
    if stats:
        lines.append("")
        lines.append(" ".join(stats))
    
    return "\n".join(lines)


def generate_daily_markdown(
    tweets_by_list: Dict[str, Dict[str, Any]],
    date: str,
    ai_summary: str = ""
) -> str:
    """
    Generate a daily Markdown document from tweets.
    
    Args:
        tweets_by_list: Dict mapping list_id to list data
        date: Date string in YYYY-MM-DD format
        ai_summary: AI-generated summary text
        
    Returns:
        Markdown formatted string
    """
    lines = []
    
    # Title
    lines.append(f"# Twitter List Monitor - {date}")
    lines.append("")
    
    # AI Summary
    if ai_summary:
        lines.append("## AI Summary")
        lines.append("")
        lines.append(ai_summary)
        lines.append("")
    
    # Tweets by list
    for list_id, list_data in tweets_by_list.items():
        list_name = list_data.get('list_name', list_id)
        
        lines.append(f"## {list_name}")
        lines.append("")
        
        members = list_data.get('members', {})
        
        for username, tweets in members.items():
            lines.append(f"### @{username}")
            lines.append("")
            
            for tweet in tweets:
                # Use enriched format if available
                if tweet.get('retweeted_content') or tweet.get('article_full_content') or tweet.get('quoted_content'):
                    formatted = format_tweet_with_enrichment(tweet)
                else:
                    formatted = format_tweet(tweet)
                
                lines.append(formatted)
                lines.append("")
                lines.append("---")
                lines.append("")
    
    return "\n".join(lines)


def save_markdown(content: str, output_dir: str, date: str) -> str:
    """
    Save Markdown content to a file.
    
    Args:
        content: Markdown content
        output_dir: Output directory path
        date: Date string for filename
        
    Returns:
        Path to saved file
    """
    from pathlib import Path
    
    output_path = Path(output_dir) / f"{date}.md"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(content)
    
    return str(output_path)
