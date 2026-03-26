from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class ProviderFetchRequest:
    symbol: str
    start_date: str
    end_date: str
    frequency: str = "1d"
    adjust: str = "qfq"
    market: str = "CN-A"


@dataclass(frozen=True)
class DataFinding:
    code: str
    severity: str
    message: str
    count: int = 0


@dataclass
class DataQualityReport:
    project: str
    frequency: str
    source_provider: str
    coverage_ratio: float
    covered_symbols: int
    universe_symbols: int
    raw_rows: int
    cleaned_rows: int
    validated_rows: int
    duplicate_rows: int
    missing_rows: int
    zero_volume_rows: int
    limit_locked_rows: int
    suspended_rows: int
    findings: list[DataFinding] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["findings"] = [asdict(item) for item in self.findings]
        return payload
