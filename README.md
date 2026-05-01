# gzh-account-search

![Targeted gzh Collection](assets/hero.png)

**指定 gzh 账号定点采集工具。**  
不是关键词泛搜，不依赖 Sogou 式公开索引；你给账号列表，它按目标账号稳定拉取近期或历史内容，归档 JSON，并可选 AI 五维评分输出 Markdown 报告。

> 市面上很多方案走 Sogou 式泛搜：索引慢、旧内容多、账号不可控。  
> `gzh-account-search` 做的是指定账号采集：目标明确、新内容优先、可归档、可评分。

## 核心卖点

| 能力 | 说明 |
|---|---|
| 定点账号 | 配置目标 gzh 列表，不靠关键词碰运气 |
| 内容更新 | `lookback_days` 控制近期窗口，适合日报/周报/监控 |
| 尽量扫全 | 调大 `lookback_days` + `max_articles_per_account`，可沿历史列表持续翻页 |
| 原始归档 | 按日期和账号保存 JSON，方便二次分析或入库 |
| AI 评分 | 热度、权威性、内容质量、实用性、时效性 |
| 可控节奏 | 操作、翻页、文章、账号间隔都可配置 |

## 本地测试跑哪个脚本

入口就是根目录的 `main.py`。

```bash
cp config.yaml.example config.yaml
python main.py --config config.yaml
```

第一次建议先关评分，只验证采集链路：

```yaml
scoring:
  enabled: false
```

然后在 `config.yaml` 填目标账号：

```yaml
fetch:
  accounts:
    - "目标gzh账号A"
    - "目标gzh账号B"
```

启用评分时再填：

```yaml
llm:
  api_key: "sk-..."
  base_url: "https://api.openai.com/v1"
  model: "gpt-4o-mini"

scoring:
  enabled: true
```

## 安装

```bash
git clone https://github.com/NeAoo/gzh-account-search.git
cd gzh-account-search

python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium

cp config.yaml.example config.yaml
```

Windows PowerShell:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
playwright install chromium
```

首次运行会打开可见浏览器，需要完成登录。登录态保存到 `browser_data/`，后续 `browser_mode: auto` 会优先无界面复用。

## 常用配置

### 竞品日报

```yaml
fetch:
  accounts:
    - "竞品A"
    - "竞品B"
    - "竞品C"
  lookback_days: 1
  max_articles_per_account: 10

scoring:
  enabled: true

output:
  filename_pattern: "竞品gzh日报_{date}.md"
```

### 历史归档

```yaml
fetch:
  accounts:
    - "目标账号A"
  lookback_days: 365
  max_articles_per_account: 200
  fetch_full_content: true

scoring:
  enabled: false
```

### 快速只抓标题和链接

```yaml
fetch:
  accounts:
    - "目标账号A"
    - "目标账号B"
  fetch_full_content: false

scoring:
  enabled: false
```

## 节奏控制

页面不稳定、账号多、采集范围大时，优先调大这些值：

```yaml
fetch:
  slow_mo_ms: 300
  action_delay_seconds: 1.5
  article_delay_seconds: 3.0
  page_delay_seconds: 4.0
  account_delay_seconds: 8.0
```

## 输出

```text
output/
└── gzh日报_20260501.md

raw_data/
└── gzh/
    └── 2026-05-01/
        ├── 目标账号A/
        │   └── articles_20260501_120000.json
        └── all_accounts_20260501_120000.json
```

## 自定义

- 评分提示词：`prompts/scoring.txt`
- 评分报告模板：`templates/report.md.j2`
- 不评分报告模板：`templates/report_no_score.md.j2`

评分 JSON key 请保留：

```text
heat, authority, quality, practicality, timeliness, overall, reason
```

## 测试

```bash
python -m pytest -v
```

## License

MIT License. 使用本工具产生的任何后果由使用者自行承担。
