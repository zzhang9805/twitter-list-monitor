"""
OpenRouter AI Client for Tweet Summarization

Provides functionality to generate summaries of tweets from Twitter lists using OpenRouter API.
"""

import requests
from typing import List, Dict, Optional


class OpenRouterClient:
    """Client for interacting with OpenRouter AI API to summarize tweets."""

    def __init__(self, api_key: str, model: str = "moonshotai/kimi-k2.5", prompt_template: Optional[str] = None):
        self.api_key = api_key
        self.model = model
        self.prompt_template = prompt_template
        self.api_url = "https://openrouter.ai/api/v1/chat/completions"
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }

    def summarize_tweets(self, tweets: List[dict], list_name: str) -> str:
        if not tweets:
            raise ValueError("Cannot summarize empty tweet list")

        formatted_tweets = self._format_tweets(tweets)
        prompt = self._build_prompt(formatted_tweets, list_name)

        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}]
        }

        try:
            response = requests.post(self.api_url, headers=self.headers, json=payload, timeout=30)
            response.raise_for_status()
            result = response.json()
            if "choices" in result and len(result["choices"]) > 0:
                return result["choices"][0]["message"]["content"]
            return "Unable to generate summary"
        except Exception as e:
            return f"API error: {str(e)}"

    def _format_tweets(self, tweets: List[dict]) -> str:
        formatted = []
        for i, tweet in enumerate(tweets, 1):
            text = tweet.get("text", "")
            author = tweet.get("author", "unknown")
            if isinstance(author, dict):
                author = author.get("name") or author.get("userName") or author.get("username") or "unknown"
            created_at = tweet.get("created_at", "")
            likes = tweet.get("likes", 0)
            retweets = tweet.get("retweets", 0)
            formatted.append(f"Tweet {i} by @{author} ({created_at}):\n{text}\n❤️ {likes} | 🔁 {retweets}\n")
        return "\n".join(formatted)

    def _build_prompt(self, tweets: str, list_name: str) -> str:
        if self.prompt_template:
            return self.prompt_template.format(list_name=list_name, tweets=tweets)
        
        return f"""你是一位专注于社交媒体趋势和洞察力的专家分析师。
你的任务是对Twitter列表中的推文进行分析，并提供简洁、有见地的摘要。

## 背景
你正在分析来自Twitter列表的推文："{list_name}"

## 需要分析的推文
{tweets}

## 分析要求
请提供一个包含以下内容的摘要：

1. **关键主题**：正在讨论的主要话题是什么？
2. **热门讨论**：哪些推文获得了最多的互动？
3. **重要见解**：分享了什么有趣的见解、新闻或观点？
4. **情绪概述**：整体情绪是正面、负面还是中性？
5. **行动项或更新**：是否有重要的公告、行动号召或发展？

## 输出格式
- 保持摘要简洁但信息丰富（300-500字）
- 使用项目符号提高清晰度
- 聚焦最相关和最有影响力的内容
- 突出任何新兴趋势或热点话题

请现在提供你的摘要："""