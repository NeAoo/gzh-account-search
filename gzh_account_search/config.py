"""Configuration loading and validation."""

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field, model_validator

BrowserMode = Literal["auto", "visible", "headless"]


class LLMConfig(BaseModel):
    api_key: str = Field("", description="API key for OpenAI-compatible service")
    base_url: str = Field("https://api.openai.com/v1")
    model: str = Field("gpt-4o-mini")
    workers: int = Field(5, ge=1, le=32, description="Concurrent scoring workers")


class FetchConfig(BaseModel):
    accounts: list[str] = Field(..., min_length=1, description="Public accounts")
    max_articles_per_account: int = Field(10, ge=1, le=100)
    lookback_days: int = Field(7, ge=1, le=365)
    fetch_full_content: bool = Field(True)
    browser_mode: BrowserMode = Field("auto")
    login_timeout_seconds: int = Field(180, ge=30, le=600)

    slow_mo_ms: int = Field(300, ge=0, le=10000)
    action_delay_seconds: float = Field(1.5, ge=0.0, le=120.0)
    article_delay_seconds: float = Field(3.0, ge=0.0, le=120.0)
    page_delay_seconds: float = Field(4.0, ge=0.0, le=120.0)
    account_delay_seconds: float = Field(8.0, ge=0.0, le=600.0)


class ScoringConfig(BaseModel):
    enabled: bool = Field(True)
    prompt_file: str = Field("prompts/scoring.txt")


class OutputConfig(BaseModel):
    dir: str = Field("./output")
    template_file: str = Field("templates/report.md.j2")
    no_score_template_file: str = Field("templates/report_no_score.md.j2")
    top_n: int = Field(10, ge=1, le=1000)
    filename_pattern: str = Field("公众号日报_{date}.md")


class PathsConfig(BaseModel):
    raw_data_dir: str = Field("./raw_data/wechat_mp")
    browser_data: str = Field("./browser_data/wechat_mp_state.json")
    log_file: str = Field("./logs/run.log")


class Config(BaseModel):
    llm: LLMConfig
    fetch: FetchConfig
    scoring: ScoringConfig
    output: OutputConfig
    paths: PathsConfig

    @model_validator(mode="after")
    def validate_api_key_required_when_scoring(self) -> "Config":
        if self.scoring.enabled and not self.llm.api_key.strip():
            raise ValueError(
                "scoring.enabled=true requires llm.api_key; "
                "set scoring.enabled=false to skip scoring"
            )
        return self

    @classmethod
    def from_yaml(cls, path: str | Path) -> "Config":
        config_path = Path(path)
        if not config_path.exists():
            raise FileNotFoundError(f"Config file does not exist: {config_path}")

        with open(config_path, "r", encoding="utf-8") as file:
            data = yaml.safe_load(file)

        if not isinstance(data, dict):
            raise ValueError(f"Config root must be a mapping: {config_path}")

        return cls.model_validate(data)
