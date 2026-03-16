from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


BASE_HOME = Path("~/.coresearcher").expanduser()


def _home_path(*parts: str) -> str:
    return str((BASE_HOME / Path(*parts)).expanduser())


class ProviderConfig(BaseModel):
    model_config = ConfigDict(extra="ignore")

    enabled: bool = False
    model: str | None = None
    api_key: str | None = None
    api_base: str | None = None
    extra_headers: dict[str, str] = Field(default_factory=dict)


class ProvidersConfig(BaseModel):
    model_config = ConfigDict(extra="ignore")

    default: str = "openai"
    default_model: str = "gpt-4o-mini"
    openai: ProviderConfig = Field(default_factory=lambda: ProviderConfig(enabled=True, model="gpt-4o-mini"))
    anthropic: ProviderConfig = Field(default_factory=ProviderConfig)
    openrouter: ProviderConfig = Field(default_factory=ProviderConfig)
    deepseek: ProviderConfig = Field(default_factory=ProviderConfig)
    gemini: ProviderConfig = Field(default_factory=ProviderConfig)
    dashscope: ProviderConfig = Field(default_factory=ProviderConfig)
    moonshot: ProviderConfig = Field(default_factory=ProviderConfig)
    minimax: ProviderConfig = Field(default_factory=ProviderConfig)
    siliconflow: ProviderConfig = Field(default_factory=ProviderConfig)
    volcengine: ProviderConfig = Field(default_factory=ProviderConfig)
    aihubmix: ProviderConfig = Field(default_factory=ProviderConfig)
    groq: ProviderConfig = Field(default_factory=ProviderConfig)
    vllm: ProviderConfig = Field(default_factory=ProviderConfig)
    custom: ProviderConfig = Field(default_factory=ProviderConfig)
    mock: ProviderConfig = Field(default_factory=lambda: ProviderConfig(model="mock/default", enabled=False))
    openai_codex: ProviderConfig = Field(default_factory=lambda: ProviderConfig(model="openai-codex/gpt-5.1-codex"))
    github_copilot: ProviderConfig = Field(default_factory=ProviderConfig)

    def resolve(self, name: str | None = None) -> tuple[str, ProviderConfig]:
        provider_name = (name or self.default).replace("-", "_")
        cfg = getattr(self, provider_name, None)
        if cfg is None:
            raise ValueError(f"Unknown provider: {provider_name}")
        if cfg.model is None:
            cfg = cfg.model_copy(update={"model": self.default_model})
        return provider_name, cfg


class FeishuConfig(BaseModel):
    model_config = ConfigDict(extra="ignore")

    enabled: bool = False
    app_id: str | None = None
    app_secret: str | None = None
    encrypt_key: str | None = None
    verification_token: str | None = None
    allow_from: list[str] = Field(default_factory=list)
    upload_dir: str = _home_path("uploads", "feishu")


class QQConfig(BaseModel):
    model_config = ConfigDict(extra="ignore")

    enabled: bool = False
    app_id: str | None = None
    secret: str | None = None
    token: str | None = None
    sandbox: bool = False
    allow_from: list[str] = Field(default_factory=list)


class CLIChannelConfig(BaseModel):
    model_config = ConfigDict(extra="ignore")

    enabled: bool = True


class ChannelsConfig(BaseModel):
    model_config = ConfigDict(extra="ignore")

    cli: CLIChannelConfig = Field(default_factory=CLIChannelConfig)
    feishu: FeishuConfig = Field(default_factory=FeishuConfig)
    qq: QQConfig = Field(default_factory=QQConfig)

    def enabled_names(self) -> list[str]:
        names: list[str] = []
        for name in ("cli", "feishu", "qq"):
            cfg = getattr(self, name)
            if getattr(cfg, "enabled", False):
                names.append(name)
        return names


class ExecToolConfig(BaseModel):
    model_config = ConfigDict(extra="ignore")

    timeout: int = 60
    block_dangerous: bool = True


class WebSearchConfig(BaseModel):
    model_config = ConfigDict(extra="ignore")

    api_key: str | None = None
    base_url: str = "https://api.search.brave.com/res/v1/web/search"
    max_results: int = 5


class WebToolConfig(BaseModel):
    model_config = ConfigDict(extra="ignore")

    search: WebSearchConfig = Field(default_factory=WebSearchConfig)
    fetch_timeout: int = 20


class MCPServerConfig(BaseModel):
    model_config = ConfigDict(extra="ignore")

    command: str
    args: list[str] = Field(default_factory=list)
    cwd: str | None = None
    env: dict[str, str] = Field(default_factory=dict)


class ToolsConfig(BaseModel):
    model_config = ConfigDict(extra="ignore")

    exec: ExecToolConfig = Field(default_factory=ExecToolConfig)
    web: WebToolConfig = Field(default_factory=WebToolConfig)
    restrict_to_workspace: bool = True
    allowed_dir: str = _home_path("workspace")
    mcp_servers: dict[str, MCPServerConfig] = Field(default_factory=dict)

    @property
    def shell_timeout_seconds(self) -> int:
        return self.exec.timeout

    @property
    def web_search_api_key(self) -> str | None:
        return self.web.search.api_key

    @property
    def web_search_base_url(self) -> str:
        return self.web.search.base_url

    @property
    def max_web_results(self) -> int:
        return self.web.search.max_results


class MemoryConfig(BaseModel):
    model_config = ConfigDict(extra="ignore")

    directory: str = _home_path("workspace", "memory")
    session_dir: str = _home_path("sessions")
    recent_days: int = 1
    vector_top_k: int = 5


class AgentDefaultsConfig(BaseModel):
    model_config = ConfigDict(extra="ignore")

    model: str = "gpt-4o-mini"
    temperature: float = 0.7
    max_tokens: int = 4096
    memory_window: int = 50
    max_iterations: int = 20


class ReflexionConfig(BaseModel):
    model_config = ConfigDict(extra="ignore")

    enabled: bool = False
    max_attempts: int = 3
    pass_threshold: float = 0.7
    critic_provider: str | None = None
    critic_model: str | None = None


class AgentConfig(BaseModel):
    model_config = ConfigDict(extra="ignore")

    defaults: AgentDefaultsConfig = Field(default_factory=AgentDefaultsConfig)
    reflexion: ReflexionConfig = Field(default_factory=ReflexionConfig)
    max_context_tokens: int = 128_000
    compression_ratio: float = 0.75
    summary_ratio: float = 0.90
    enable_planning: bool = True
    enable_reflexion: bool = False
    enable_rag: bool = True
    planner_min_length: int = 120
    max_parallel_steps: int = 3

    @property
    def max_iterations(self) -> int:
        return self.defaults.max_iterations


class CronConfig(BaseModel):
    model_config = ConfigDict(extra="ignore")

    enabled: bool = True
    heartbeat_minutes: int = 30
    store_path: str = _home_path("cron_jobs.json")


class WorkspaceConfig(BaseModel):
    model_config = ConfigDict(extra="ignore")

    path: str = _home_path("workspace")
    template_dir: str | None = None


class Config(BaseModel):
    model_config = ConfigDict(extra="ignore")

    agents: AgentConfig = Field(default_factory=AgentConfig)
    providers: ProvidersConfig = Field(default_factory=ProvidersConfig)
    channels: ChannelsConfig = Field(default_factory=ChannelsConfig)
    tools: ToolsConfig = Field(default_factory=ToolsConfig)
    memory: MemoryConfig = Field(default_factory=MemoryConfig)
    cron: CronConfig = Field(default_factory=CronConfig)
    workspace: WorkspaceConfig = Field(default_factory=WorkspaceConfig)
    metadata: dict[str, Any] = Field(default_factory=dict)
