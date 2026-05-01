# gzh-account-search

按指定公众号名称批量抓取微信公众号文章，支持可选 AI 通用五维评分，并输出 Markdown 报告。

> **重要前置条件: 你必须拥有自己的微信公众号。** 本工具登录的是 `mp.weixin.qq.com` 公众号管理后台，只有公众号注册者或有权限的运营者才能扫码登录。没有公众号后台权限的用户无法使用本工具。

> **使用风险与免责声明:**
> 1. 本工具利用公众号后台的文章选择能力采集公开文章信息，微信平台页面和政策可能随时变化，工具可能失效。
> 2. 大规模、高频抓取可能触发风控，甚至影响你的公众号后台使用。使用者自行承担风险。
> 3. 本项目面向个人学习、调研和内容整理，不鼓励也不支持商业化大规模抓取、搬运或侵权转载。
> 4. 抓取到的文章版权归原公众号或原作者所有。

## 功能特性

- 按公众号名称批量抓取最近 N 天文章
- 可选 AI 打分，支持 OpenAI 兼容接口
- 公开通用五维评分: 热度、权威性、内容质量、实用性、时效性
- 提示词模板和 Markdown 模板均可自定义
- 浏览器三态: `auto`、`visible`、`headless`
- 保留节奏控制参数，降低页面不稳定和平台风控风险
- 原始 JSON 数据按日期和公众号归档

## 快速开始

### 1. 克隆仓库

```bash
git clone https://github.com/NeAoo/gzh-account-search.git
cd gzh-account-search
```

### 2. 安装依赖

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium
```

Windows PowerShell 激活虚拟环境:

```powershell
.venv\Scripts\Activate.ps1
```

### 3. 创建配置

```bash
cp config.yaml.example config.yaml
```

至少填写:

- `fetch.accounts`: 要抓取的公众号名称列表
- `llm.api_key`: 仅在 `scoring.enabled: true` 时需要

如果只想抓取不打分:

```yaml
scoring:
  enabled: false
```

### 4. 运行

```bash
python main.py --config config.yaml
```

首次运行会打开可见浏览器，请扫码登录你自己的公众号后台。登录态会保存到 `browser_data/`，后续 `fetch.browser_mode: auto` 会优先尝试 headless 复用。

### 5. 查看结果

- Markdown 报告: `output/`
- 原始 JSON: `raw_data/wechat_mp/<日期>/<公众号>/`
- 运行日志: `logs/`

## 配置说明

浏览器模式:

```yaml
fetch:
  browser_mode: "auto"      # 推荐
  login_timeout_seconds: 180
```

节奏控制:

```yaml
fetch:
  slow_mo_ms: 300
  action_delay_seconds: 1.5
  article_delay_seconds: 3.0
  page_delay_seconds: 4.0
  account_delay_seconds: 8.0
```

如果页面经常加载失败或账号较敏感，优先调大这些值。

## 自定义评分

编辑 `prompts/scoring.txt` 可以调整评分说明和权重。代码读取以下 JSON key，请保留:

- `heat`
- `authority`
- `quality`
- `practicality`
- `timeliness`
- `overall`
- `reason`

## 自定义输出

编辑:

- `templates/report.md.j2`: 打分模式模板
- `templates/report_no_score.md.j2`: 不打分模式模板

模板可访问 `articles`、`generated_at`、`max_score`、`avg_score`。

## 作为库使用

```python
from pathlib import Path

from gzh_account_search import Config, Pipeline

config = Config.from_yaml(Path("config.yaml"))
output_file = Pipeline(config).run()
print(output_file)
```

也可以单独使用爬虫:

```python
from pathlib import Path

from gzh_account_search import BrowserSession, Config, WechatMpCrawler

config = Config.from_yaml(Path("config.yaml"))

with BrowserSession(
    storage_state_path=Path(config.paths.browser_data),
    browser_mode=config.fetch.browser_mode,
    login_timeout_seconds=config.fetch.login_timeout_seconds,
    slow_mo_ms=config.fetch.slow_mo_ms,
) as (context, page, token):
    crawler = WechatMpCrawler(config.fetch, Path(config.paths.raw_data_dir))
    result = crawler.collect(context, page, token)
```

## 项目结构

```text
gzh-account-search/
├── main.py
├── config.yaml.example
├── gzh_account_search/
│   ├── browser.py
│   ├── config.py
│   ├── crawler.py
│   ├── models.py
│   ├── pipeline.py
│   ├── renderer.py
│   └── scorer.py
├── prompts/
│   └── scoring.txt
├── templates/
│   ├── report.md.j2
│   └── report_no_score.md.j2
└── tests/
```

## 常见问题

**运行时报 `api_key` 错误怎么办？**

你启用了 `scoring.enabled: true`，但没有填写 `llm.api_key`。填写 key，或关闭打分。

**浏览器一直停在登录页怎么办？**

确认你有公众号后台权限，并在 `login_timeout_seconds` 时间内完成扫码。必要时设置 `fetch.browser_mode: visible` 观察页面状态。

**抓取时报找不到元素怎么办？**

微信后台页面结构可能变更。先用 `fetch.browser_mode: visible` 复现，再根据页面实际 DOM 更新选择器。

## 测试

```bash
python -m pytest -v
```

## License

MIT License. 使用本工具产生的任何后果由使用者自行承担。
