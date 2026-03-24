from __future__ import annotations

import json
import os
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from quant_mvp.networking import NetworkRuntimeConfig
from quant_mvp.project import find_repo_root


class PlatformSettings(BaseModel):
    model_config = ConfigDict(extra="ignore")

    mode: str = "local"
    host: str = "127.0.0.1"
    port: int = 8000
    max_concurrent_jobs: int | None = None
    open_browser: bool = False
    repo_root: str | None = None
    platform_db_path: str | None = None
    log_dir: str | None = None
    web_dist_dir: str | None = None
    proxy_url: str | None = None
    ca_bundle_path: str | None = None
    connect_timeout_seconds: float = 5.0
    read_timeout_seconds: float = 15.0
    allow_origins: list[str] = Field(default_factory=lambda: ["http://127.0.0.1:5173", "http://localhost:5173"])

    def normalized_repo_root(self) -> Path:
        return Path(self.repo_root).resolve() if self.repo_root else find_repo_root()

    def resolved_platform_db_path(self) -> Path:
        if self.platform_db_path:
            return Path(self.platform_db_path).resolve()
        return self.normalized_repo_root() / "data" / "platform.db"

    def resolved_log_dir(self) -> Path:
        if self.log_dir:
            return Path(self.log_dir).resolve()
        return self.normalized_repo_root() / "logs" / "platform"

    def resolved_web_dist_dir(self) -> Path:
        if self.web_dist_dir:
            return Path(self.web_dist_dir).resolve()
        return self.normalized_repo_root() / "apps" / "web" / "dist"

    def effective_max_concurrent_jobs(self) -> int:
        if self.max_concurrent_jobs is not None:
            return max(1, int(self.max_concurrent_jobs))
        return 2 if self.mode == "shared" else 1

    def network_config(self) -> NetworkRuntimeConfig:
        return NetworkRuntimeConfig.from_sources(
            proxy_url=self.proxy_url,
            ca_bundle_path=self.ca_bundle_path,
            connect_timeout_seconds=self.connect_timeout_seconds,
            read_timeout_seconds=self.read_timeout_seconds,
        )


def _read_json(path: Path) -> dict:
    if not path.exists():
        return {}
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def load_platform_settings(
    repo_root: Path | None = None,
    overrides: dict | None = None,
) -> PlatformSettings:
    root = (repo_root or find_repo_root()).resolve()
    config_path = root / "appsettings.json"
    payload = _read_json(config_path)

    env_mode = os.getenv("BT_PLATFORM_MODE")
    env_host = os.getenv("BT_PLATFORM_HOST")
    env_port = os.getenv("BT_PLATFORM_PORT")
    env_max_jobs = os.getenv("BT_PLATFORM_MAX_CONCURRENT_JOBS")
    env_proxy_url = os.getenv("BT_PLATFORM_PROXY_URL")
    env_ca_bundle_path = os.getenv("BT_PLATFORM_CA_BUNDLE_PATH")
    env_connect_timeout = os.getenv("BT_PLATFORM_CONNECT_TIMEOUT_SECONDS")
    env_read_timeout = os.getenv("BT_PLATFORM_READ_TIMEOUT_SECONDS")

    if env_mode:
        payload["mode"] = env_mode
    if env_host:
        payload["host"] = env_host
    if env_port:
        payload["port"] = int(env_port)
    if env_max_jobs:
        payload["max_concurrent_jobs"] = int(env_max_jobs)
    if env_proxy_url:
        payload["proxy_url"] = env_proxy_url
    if env_ca_bundle_path:
        payload["ca_bundle_path"] = env_ca_bundle_path
    if env_connect_timeout:
        payload["connect_timeout_seconds"] = float(env_connect_timeout)
    if env_read_timeout:
        payload["read_timeout_seconds"] = float(env_read_timeout)

    payload["repo_root"] = str(root)
    if overrides:
        payload.update(overrides)
    return PlatformSettings.model_validate(payload)
