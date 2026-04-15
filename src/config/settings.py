"""
配置管理模块

优先级（从高到低）：
1. CLI 参数
2. 环境变量
3. .env 文件（项目根目录或 ~/.Zclaw/.env）
4. 项目级配置文件 (.Zclaw.yaml)
5. 全局配置文件 (~/.Zclaw/config.yaml)
6. 默认值
"""

from __future__ import annotations

import logging
import os
import re
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings

logger = logging.getLogger(__name__)


class ProviderConfig(BaseModel):
    """单个 LLM 提供者的配置"""
    base_url: str
    api_key: str
    model: str
    max_context_tokens: int = 32768
    supports_tools: bool = False
    supports_vision: bool = False
    supports_streaming: bool = True


class LLMConfig(BaseModel):
    """LLM 模块配置"""
    default_provider: str = "bailian"
    fallback_providers: list[str] = Field(default_factory=list)
    temperature: float = 0.3
    max_tokens: int = 8192
    providers: dict[str, ProviderConfig] = Field(default_factory=dict)


class AgentConfig(BaseModel):
    """Agent 行为配置"""
    max_loop_rounds: int = 50
    planning_mode: str = "auto"


class MemoryConfig(BaseModel):
    """记忆引擎配置"""
    storage_path: str = ".Zclaw/memory"  # 相对路径，解析为项目根目录
    working_memory_max_tokens: int = 30000
    episodic_max_age_days: int = 90


class ContextConfig(BaseModel):
    """上下文管理配置"""
    safety_margin_ratio: float = 0.1


class MCPConfig(BaseModel):
    """MCP 服务器集成配置"""
    enabled: bool = True
    config_path: str = ".Zclaw/mcp_servers.json"  # 相对路径，解析为项目根目录
    auto_connect: bool = True  # 启动时自动连接所有已配置的服务器


class WebConfig(BaseModel):
    """Web UI 配置"""
    enabled: bool = True
    host: str = "0.0.0.0"
    port: int = 8080
    cors_origins: list[str] = Field(default_factory=lambda: ["*"])
    static_dir: str = ""  # 默认使用内置静态文件


class SecurityConfig(BaseModel):
    """安全与权限配置"""
    path_restrictions: dict[str, list[str]] = Field(default_factory=lambda: {
        "allow": ["."],
        "deny": ["/etc", "/usr", "/bin", "/sbin", "/boot", "/proc", "/sys"],
    })
    auto_approve: list[str] = Field(default_factory=lambda: [
        "file_read", "directory", "file_search",
    ])
    audit_log: bool = True
    audit_log_path: str = "~/.Zclaw/audit/"
    blocked_patterns: list[str] = Field(default_factory=lambda: [
        r"rm\s+-rf\s+/", r"sudo\s+", r"mkfs", r"dd\s+if=", r":\(\)\{",
    ])


class SkillsConfig(BaseModel):
    """Skills 模块配置"""
    enabled: bool = True
    global_path: str = "~/.zclaw/skills"
    project_path: str = "skills"  # 相对于项目根目录
    auto_load: bool = True
    inject_to_prompt: bool = True


class Settings(BaseModel):
    """应用全局配置"""
    llm: LLMConfig = Field(default_factory=LLMConfig)
    agent: AgentConfig = Field(default_factory=AgentConfig)
    memory: MemoryConfig = Field(default_factory=MemoryConfig)
    context: ContextConfig = Field(default_factory=ContextConfig)
    mcp: MCPConfig = Field(default_factory=MCPConfig)
    web: WebConfig = Field(default_factory=WebConfig)
    security: SecurityConfig = Field(default_factory=SecurityConfig)
    skills: SkillsConfig = Field(default_factory=SkillsConfig)


_ENV_VAR_PATTERN = re.compile(r"\$\{([^}]+)\}")


def _resolve_env_vars(value: Any) -> Any:
    """递归替换值中的 ${ENV_VAR} 为实际环境变量值。"""
    if isinstance(value, str):
        def _replace(match: re.Match) -> str:
            env_name = match.group(1)
            env_val = os.environ.get(env_name, "")
            if not env_val:
                return match.group(0)
            return env_val
        return _ENV_VAR_PATTERN.sub(_replace, value)
    elif isinstance(value, dict):
        return {k: _resolve_env_vars(v) for k, v in value.items()}
    elif isinstance(value, list):
        return [_resolve_env_vars(item) for item in value]
    return value


def _get_project_root() -> Path:
    """获取项目根目录（src/ 的上级目录）。"""
    src_dir = Path(__file__).resolve().parent
    return src_dir.parent


def _find_env_file() -> Path | None:
    """查找 .env 文件。

    查找顺序：
    1. 当前工作目录 (.env)
    2. 项目根目录（settings.py 上两级目录）
    3. ~/.Zclaw/.env
    """
    # 1. 当前工作目录
    p = Path.cwd() / ".env"
    if p.exists():
        return p
    # 2. 项目根目录（基于 settings.py 的位置）
    p = Path(__file__).resolve().parent.parent / ".env"
    if p.exists():
        return p
    # 3. ~/.Zclaw/.env
    p = Path.home() / ".Zclaw" / ".env"
    if p.exists():
        return p
    return None


def load_dot_env(env_path: Path | None = None) -> dict[str, str]:
    """
    加载 .env 文件并返回键值对。

    支持两种格式：
    - 简单格式: KEY=VALUE
    - 注释行: # 开头
    - 空行自动跳过

    值中的引号会被自动去除。
    """
    if env_path is None:
        env_path = _find_env_file()
    if env_path is None or not env_path.exists():
        return {}

    env_vars: dict[str, str] = {}
    with open(env_path, "r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                logger.warning(f"{env_path}:{line_num}: skipping invalid line: {line}")
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip()
            # 去除值两端的引号
            if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
                value = value[1:-1]
            env_vars[key] = value

    # 注入到 os.environ（不覆盖已有值，除非 .env 中明确指定）
    for k, v in env_vars.items():
        if k not in os.environ or os.environ[k] == "":
            os.environ[k] = v

    logger.debug(f"Loaded {len(env_vars)} variables from {env_path}")
    return env_vars


def load_settings_from_env(
    env_path: Path | None = None,
    config_path: Path | None = None,
) -> Settings:
    """
    从 .env 文件加载配置。

    支持的环境变量：
    - ZCLAW_PROVIDER: LLM 提供者名称 (如 bailian, ollama)
    - ZCLAW_MODEL: 模型名称 (如 qwen-plus, qwen2.5:latest)
    - ZCLAW_API_KEY: API Key
    - ZCLAW_BASE_URL: API 基础 URL
    - ZCLAW_MAX_CONTEXT_TOKENS: 最大上下文 token 数
    - ZCLAW_TEMPERATURE: 温度参数
    - ZCLAW_MAX_TOKENS: 最大生成 token 数
    - ZCLAW_MAX_LOOP_ROUNDS: 最大循环轮数

    加载顺序：
    1. 加载 .env 文件到 os.environ
    2. 读取环境变量构建配置
    3. 叠加 YAML 配置（如有）
    """
    # Step 1: 加载 .env
    load_dot_env(env_path)

    # Step 2: 从环境变量读取
    provider_name = os.environ.get("ZCLAW_PROVIDER", "bailian")
    model_name = os.environ.get("ZCLAW_MODEL", "qwen-plus")
    api_key = os.environ.get("ZCLAW_API_KEY", "")
    base_url = os.environ.get(
        "ZCLAW_BASE_URL",
        "https://dashscope.aliyuncs.com/compatible-mode/v1"
    )
    max_context = int(os.environ.get("ZCLAW_MAX_CONTEXT_TOKENS", "131072"))
    temperature = float(os.environ.get("ZCLAW_TEMPERATURE", "0.3"))
    max_tokens = int(os.environ.get("ZCLAW_MAX_TOKENS", "8192"))
    max_rounds = int(os.environ.get("ZCLAW_MAX_LOOP_ROUNDS", "50"))

    # Step 3: 构建配置字典
    config_data: dict[str, Any] = {
        "llm": {
            "default_provider": provider_name,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "providers": {
                provider_name: {
                    "base_url": base_url,
                    "api_key": api_key,
                    "model": model_name,
                    "max_context_tokens": max_context,
                    "supports_tools": True,
                    "supports_vision": False,
                    "supports_streaming": True,
                }
            },
        },
        "agent": {
            "max_loop_rounds": max_rounds,
        },
        "memory": {
            "storage_path": ".Zclaw/memory",
        },
        "security": {
            "audit_log_path": ".Zclaw/audit",
        },
    }

    # Step 4: 叠加 YAML 配置（如有）
    yaml_data = load_yaml_config(config_path)
    if yaml_data:
        config_data = _deep_merge(yaml_data, config_data)

    logger.info(f"Settings loaded from env (provider={provider_name}, model={model_name})")
    return Settings.model_validate(config_data)


def _find_config_file() -> Path | None:
    """查找配置文件。"""
    for name in (".Zclaw.yaml", ".Zclaw.yml"):
        p = Path.cwd() / name
        if p.exists():
            return p
    home = Path.home()
    for name in ("config.yaml", "config.yml"):
        p = home / ".Zclaw" / name
        if p.exists():
            return p
    return None


def load_yaml_config(path: Path | None = None) -> dict[str, Any]:
    """从 YAML 文件加载配置，并进行环境变量替换。"""
    if path is None:
        path = _find_config_file()
    if path is None or not path.exists():
        return {}
    with open(path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}
    resolved = _resolve_env_vars(raw)
    return resolved


def load_settings(
    config_path: Path | None = None,
    overrides: dict[str, Any] | None = None,
    use_env: bool = False,
) -> Settings:
    """
    加载并返回全局配置。

    Args:
        config_path: YAML 配置文件路径
        overrides: 覆盖配置字典
        use_env: 是否优先使用 .env 环境变量配置
    """
    if use_env:
        return load_settings_from_env(config_path=config_path)

    yaml_data = load_yaml_config(config_path)
    if overrides:
        yaml_data = _deep_merge(yaml_data, overrides)
    return Settings.model_validate(yaml_data)


def _deep_merge(base: dict, override: dict) -> dict:
    """深度合并两个字典，override 中的值优先。"""
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result
