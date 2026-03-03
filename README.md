# Twitter List Monitor

自动化 Twitter 列表监控程序：每天从配置的 Twitter List 获取成员最新推文，用 AI 生成热点总结，保存到 Markdown 文档。

## 功能特性

- **多列表监控**：同时监控多个 Twitter 列表
- **自动获取推文**：获取每个列表成员的最新推文
- **AI 智能总结**：使用 OpenRouter API 调用 Kimi K2.5 模型生成热点总结
- **Markdown 输出**：生成格式化的每日报告文档
- **Rate Limiting**：内置 API 速率限制，防止超出配额
- **Cron 定时任务**：支持每日自动运行

## 环境要求

- Python 3.8+
- pip 包管理器

## 安装步骤

### 1. 克隆或下载项目

将项目文件下载到本地目录。

### 2. 创建虚拟环境（推荐）

```bash
python3 -m venv venv
source venv/bin/activate  # Linux/macOS
# 或
venv\Scripts\activate     # Windows
```

### 3. 安装依赖

```bash
pip install -r requirements.txt
```

如果没有 requirements.txt，手动安装：

```bash
pip install pyyaml python-dotenv requests
```

## 配置说明

### config.yaml

项目根目录下的 `config.yaml` 是主配置文件：

```yaml
# Twitter API 配置
twitter:
  api_key: "YOUR_TWITTER_API_KEY"
  bearer_token: "YOUR_TWITTER_BEARER_TOKEN"
  list_ids:
    - "LIST_ID_1"
    - "LIST_ID_2"

# OpenRouter AI 配置
openrouter:
  api_key: "YOUR_OPENROUTER_API_KEY"
  model: "moonshotai/kimi-k2.5"
  max_tokens: 1000
  temperature: 0.7

# 输出设置
output:
  directory: "./info_stream"
  max_tweets_per_user: 100

# 速率限制
rate_limit:
  api_delay_seconds: 0.1
  max_retries: 3

# 日志设置
logging:
  level: "INFO"
  log_file: "./logs/twitter_monitor.log"
```

### .env 文件

在项目根目录创建 `.env` 文件：

```bash
# Twitter API 配置
TWITTER_API_KEY=your_twitter_api_key_here
TWITTER_BEARER_TOKEN=your_twitter_bearer_token_here

# OpenRouter API 配置
OPENROUTER_API_KEY=your_openrouter_api_key_here

# 可选配置
OUTPUT_DIR=info_stream
MAX_TWEETS_PER_USER=100
API_DELAY_SECONDS=1
```

### 如何获取 API Key

#### TwitterAPI.io

1. 访问 [TwitterAPI.io](https://twitterapi.io/dashboard)
2. 注册账号并订阅付费套餐
3. 在 Dashboard 获取 API Key

**注意**：免费版 QPS=1（每 60 秒 1 个请求），付费版可达 QPS=20。

#### OpenRouter

1. 访问 [OpenRouter.ai](https://openrouter.ai/)
2. 注册账号并获取 API Key
3. 默认使用 `moonshotai/kimi-k2.5` 模型

#### Twitter List ID

1. 在 Twitter 网页版打开目标列表
2. URL 格式：`https://twitter.com/i/lists/1234567890`
3. 列表 ID 就是 URL 中的数字部分：`1234567890`

## 使用方法

### 基本运行

```bash
python twitter_monitor.py
```

### 指定日期

```bash
python twitter_monitor.py --date 2026-03-01
```

### 测试模式（不调用 API）

```bash
python twitter_monitor.py --dry-run
```

### 详细日志

```bash
python twitter_monitor.py --verbose
```

### 指定配置文件

```bash
python twitter_monitor.py --config /path/to/config.yaml
```

### 控制每用户推文数量

```bash
python twitter_monitor.py --max-tweets 50
```

## 输出示例

程序运行后会生成如下文件：

```
info_stream/
├── 2026-03-01.md
├── 2026-03-02.md
└── ...
```

Markdown 文档包含：

- **AI 热点总结**：智能分析当日推文热点
- **Table of Contents**：快速导航
- **各列表推文**：按列表和用户分组展示

## Cron 定时任务设置

### 每日早上 8 点运行

```bash
# 编辑 crontab
crontab -e

# 添加以下行
0 8 * * * /usr/bin/python3 /path/to/twitter_monitor.py >> /path/to/logs/cron.log 2>&1
```

### 每日早上 8 点和晚上 8 点运行

```bash
0 8,20 * * * /usr/bin/python3 /path/to/twitter_monitor.py >> /path/to/logs/cron.log 2>&1
```

### 完整 Crontab 配置示例

```bash
# 环境变量
SHELL=/bin/bash
PATH=/usr/local/bin:/usr/bin:/bin
PYTHON_PATH=/usr/bin/python3

# Twitter List Monitor - 每天早上 8 点
0 8 * * * cd /home/username/twitter-list-monitor && /usr/bin/python3 twitter_monitor.py >> logs/cron.log 2>&1
```

### 验证 Crontab 配置

```bash
# 查看当前 crontab
crontab -l

# 查看 cron 日志
tail -f /var/log/cron.log
# 或
tail -f logs/cron.log
```

## 成本估算

| 服务 | 用量 | 单价 | 每日成本 |
|------|------|------|----------|
| TwitterAPI.io | 50 accounts × 20 tweets | $0.00015/tweet | 约 $0.15 |
| OpenRouter (Kimi K2.5) | ~50K tokens | ~$0.002/1K tokens | 约 $0.01 |
| **合计** | | | **约 $0.16/天** |

### 成本优化建议

1. **减少监控列表数**：只监控核心列表
2. **降低推文数量**：使用 `--max-tweets 10` 减少获取量
3. **选择免费套餐**：TwitterAPI.io 免费版适合小规模使用

## 项目结构

```
twitter-list-monitor/
├── config.yaml          # 主配置文件
├── .env                 # 环境变量（包含 API Keys）
├── twitter_monitor.py   # 主程序入口
├── config_loader.py     # 配置加载模块
├── twitter_api.py      # TwitterAPI.io 客户端
├── openrouter_client.py # OpenRouter AI 客户端
├── markdown_generator.py# Markdown 生成器
├── info_stream/         # 输出的 Markdown 文件目录
└── logs/                # 日志目录
```

## 常见问题

### Q: 程序运行很慢怎么办？

A: TwitterAPI.io 免费版限制较严。解决方案：
1. 升级到付费版（QPS=20）
2. 在 config.yaml 中将 `api_delay_seconds` 调低

### Q: 如何只监控特定用户的推文？

A: 目前仅支持按列表监控。可以在 Twitter 创建包含特定用户的私有列表。

### Q: AI 总结生成失败怎么办？

A: 检查：
1. OpenRouter API Key 是否正确
2. API 配额是否充足
3. 网络连接是否正常

### Q: 如何查看运行日志？

A: 日志默认保存在 `logs/twitter_monitor.log`，或使用 `--verbose` 查看详细输出。

## 许可证

MIT License
