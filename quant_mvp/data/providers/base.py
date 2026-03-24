from __future__ import annotations

from abc import ABC, abstractmethod

import pandas as pd

from ..contracts import ProviderFetchRequest


class MarketDataProvider(ABC):
    name: str

    @abstractmethod
    def normalize_symbol(self, symbol: str) -> str:
        raise NotImplementedError

    @abstractmethod
    def fetch_daily_bars(self, request: ProviderFetchRequest) -> pd.DataFrame:
        raise NotImplementedError
