from __future__ import annotations

import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import urlparse

import httpx


def make_issue(
    code: str,
    message: str,
    *,
    suggestion: str | None = None,
    detail: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "code": code,
        "message": message,
        "suggestion": suggestion,
        "detail": detail or {},
    }


@dataclass(frozen=True)
class NetworkRuntimeConfig:
    proxy_url: str | None = None
    ca_bundle_path: str | None = None
    connect_timeout_seconds: float = 5.0
    read_timeout_seconds: float = 15.0

    @classmethod
    def from_sources(
        cls,
        *,
        proxy_url: str | None = None,
        ca_bundle_path: str | None = None,
        connect_timeout_seconds: float | None = None,
        read_timeout_seconds: float | None = None,
        env: Mapping[str, str] | None = None,
    ) -> "NetworkRuntimeConfig":
        source_env = dict(env or os.environ)
        proxy = proxy_url if proxy_url is not None else source_env.get("BT_PLATFORM_PROXY_URL")
        if proxy in {"", None}:
            proxy = source_env.get("HTTPS_PROXY") or source_env.get("HTTP_PROXY")

        ca_bundle = ca_bundle_path if ca_bundle_path is not None else source_env.get("BT_PLATFORM_CA_BUNDLE_PATH")
        if ca_bundle in {"", None}:
            ca_bundle = source_env.get("REQUESTS_CA_BUNDLE") or source_env.get("SSL_CERT_FILE")

        connect_timeout = connect_timeout_seconds
        if connect_timeout is None:
            raw = source_env.get("BT_PLATFORM_CONNECT_TIMEOUT_SECONDS")
            connect_timeout = float(raw) if raw not in {None, ""} else 5.0

        read_timeout = read_timeout_seconds
        if read_timeout is None:
            raw = source_env.get("BT_PLATFORM_READ_TIMEOUT_SECONDS")
            read_timeout = float(raw) if raw not in {None, ""} else 15.0

        return cls(
            proxy_url=proxy or None,
            ca_bundle_path=ca_bundle or None,
            connect_timeout_seconds=float(connect_timeout),
            read_timeout_seconds=float(read_timeout),
        )

    def ca_bundle_exists(self) -> bool:
        if not self.ca_bundle_path:
            return True
        return Path(self.ca_bundle_path).expanduser().resolve().exists()

    def proxy_is_valid(self) -> bool:
        if not self.proxy_url:
            return True
        parsed = urlparse(self.proxy_url)
        return parsed.scheme in {"http", "https"} and bool(parsed.netloc)

    def validation_issue_details(self) -> list[dict[str, Any]]:
        issues: list[dict[str, Any]] = []
        if self.connect_timeout_seconds <= 0:
            issues.append(
                make_issue(
                    "proxy_misconfigured",
                    "连接超时必须大于 0 秒。",
                    suggestion="请检查 appsettings.json 或环境变量 BT_PLATFORM_CONNECT_TIMEOUT_SECONDS。",
                )
            )
        if self.read_timeout_seconds <= 0:
            issues.append(
                make_issue(
                    "proxy_misconfigured",
                    "读取超时必须大于 0 秒。",
                    suggestion="请检查 appsettings.json 或环境变量 BT_PLATFORM_READ_TIMEOUT_SECONDS。",
                )
            )
        if self.proxy_url and not self.proxy_is_valid():
            issues.append(
                make_issue(
                    "proxy_misconfigured",
                    f"代理地址格式无效：{self.proxy_url}",
                    suggestion="代理地址必须是 http://host:port 或 https://host:port 形式。",
                )
            )
        if self.ca_bundle_path and not self.ca_bundle_exists():
            issues.append(
                make_issue(
                    "ca_bundle_missing",
                    f"CA 证书文件不存在：{self.ca_bundle_path}",
                    suggestion="请确认 BT_PLATFORM_CA_BUNDLE_PATH 或 appsettings.json 中的证书路径。",
                )
            )
        return issues

    def validation_issues(self) -> list[str]:
        return [item["message"] for item in self.validation_issue_details()]

    def verify_value(self) -> str | bool:
        if self.ca_bundle_path:
            return str(Path(self.ca_bundle_path).expanduser().resolve())
        return True

    def timeout(self) -> httpx.Timeout:
        return httpx.Timeout(
            connect=self.connect_timeout_seconds,
            read=self.read_timeout_seconds,
            write=self.read_timeout_seconds,
            pool=self.read_timeout_seconds,
        )

    def apply_to_env(self, env: Mapping[str, str] | None = None) -> dict[str, str]:
        merged = dict(env or os.environ)
        if self.proxy_url:
            merged["HTTP_PROXY"] = self.proxy_url
            merged["HTTPS_PROXY"] = self.proxy_url
        else:
            merged.pop("HTTP_PROXY", None)
            merged.pop("HTTPS_PROXY", None)
        if self.ca_bundle_path:
            resolved = str(Path(self.ca_bundle_path).expanduser().resolve())
            merged["REQUESTS_CA_BUNDLE"] = resolved
            merged["SSL_CERT_FILE"] = resolved
        else:
            merged.pop("REQUESTS_CA_BUNDLE", None)
            merged.pop("SSL_CERT_FILE", None)
        return merged

    def apply_to_process(self) -> None:
        merged = self.apply_to_env()
        for key in ("HTTP_PROXY", "HTTPS_PROXY", "REQUESTS_CA_BUNDLE", "SSL_CERT_FILE"):
            value = merged.get(key)
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def create_httpx_client(self, *, headers: Mapping[str, str] | None = None) -> httpx.Client:
        return httpx.Client(
            proxy=self.proxy_url,
            verify=self.verify_value(),
            timeout=self.timeout(),
            trust_env=False,
            follow_redirects=True,
            headers=dict(headers or {}),
        )


def classify_network_exception(
    exc: Exception,
    network_cfg: NetworkRuntimeConfig,
    *,
    upstream_label: str | None = None,
) -> dict[str, Any]:
    prefix = f"{upstream_label} " if upstream_label else ""
    if network_cfg.ca_bundle_path and not network_cfg.ca_bundle_exists():
        return make_issue(
            "ca_bundle_missing",
            f"{prefix}CA 证书文件不存在：{network_cfg.ca_bundle_path}",
            suggestion="请检查平台代理证书路径是否正确。",
        )
    if isinstance(exc, httpx.ProxyError):
        return make_issue(
            "proxy_misconfigured",
            f"{prefix}代理连接失败：{exc}",
            suggestion="请检查 proxy_url、代理服务状态和访问权限。",
        )
    if isinstance(exc, httpx.TimeoutException):
        return make_issue(
            "upstream_timeout",
            f"{prefix}上游接口连接超时：{exc}",
            suggestion="请检查网络、代理，或适当增大 connect/read timeout。",
        )
    if isinstance(exc, httpx.HTTPStatusError):
        status_code = exc.response.status_code if exc.response is not None else None
        return make_issue(
            "upstream_http_error",
            f"{prefix}上游接口返回 HTTP {status_code}。",
            suggestion="请确认上游网站当前可访问，必要时稍后重试。",
            detail={"status_code": status_code},
        )

    message = str(exc)
    lowered = message.lower()
    if "ssl" in lowered or "certificate" in lowered or "cert" in lowered:
        return make_issue(
            "tls_validation_failed",
            f"{prefix}TLS/CA 校验失败：{message}",
            suggestion="请检查平台代理证书是否可用，且证书链完整。",
        )
    if "proxy" in lowered or "407" in lowered:
        return make_issue(
            "proxy_misconfigured",
            f"{prefix}代理连接失败：{message}",
            suggestion="请检查 proxy_url、代理服务状态和访问权限。",
        )
    if "timeout" in lowered or "timed out" in lowered:
        return make_issue(
            "upstream_timeout",
            f"{prefix}上游接口连接超时：{message}",
            suggestion="请检查网络、代理，或适当增大 connect/read timeout。",
        )
    return make_issue(
        "upstream_http_error",
        f"{prefix}远程请求失败：{message}",
        suggestion="请检查网络、代理和上游网站状态。",
    )


def request_with_retry(
    network_cfg: NetworkRuntimeConfig,
    *,
    method: str,
    url: str,
    headers: Mapping[str, str] | None = None,
    params: Mapping[str, Any] | None = None,
    data: Mapping[str, Any] | None = None,
    attempts: int = 3,
    backoff_seconds: float = 0.5,
) -> tuple[httpx.Response, float]:
    last_exc: Exception | None = None
    last_latency_ms = 0.0
    for attempt in range(max(1, attempts)):
        started_at = time.perf_counter()
        try:
            with network_cfg.create_httpx_client(headers=headers) as client:
                response = client.request(method.upper(), url, params=params, data=data)
            latency_ms = round((time.perf_counter() - started_at) * 1000, 2)
            if response.status_code >= 500 and attempt < attempts - 1:
                time.sleep(backoff_seconds * (2**attempt))
                continue
            return response, latency_ms
        except Exception as exc:
            last_exc = exc
            last_latency_ms = round((time.perf_counter() - started_at) * 1000, 2)
            if attempt < attempts - 1:
                time.sleep(backoff_seconds * (2**attempt))
                continue
            break

    if last_exc is not None:
        setattr(last_exc, "_bt_latency_ms", last_latency_ms)
        raise last_exc
    raise RuntimeError("远程请求失败，且未捕获到具体异常。")
