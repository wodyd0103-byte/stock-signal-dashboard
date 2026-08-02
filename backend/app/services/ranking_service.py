from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd


class RankingService:
    """Cross-sectional ranking for broad market signal scans."""

    def rank_universe_signals(self, items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if not items:
            return []

        frame = pd.DataFrame(items)
        frame["buy_score_percentile"] = self._percentile(frame.get("final_buy_score", frame.get("buy_score")), higher_is_better=True)
        frame["sell_score_percentile"] = self._percentile(frame.get("final_sell_score", frame.get("sell_score")), higher_is_better=True)
        frame["relative_strength_rank"] = self._percentile(frame.get("return_20d"), higher_is_better=True)
        frame["liquidity_rank"] = self._percentile(frame.get("volume_value_20d"), higher_is_better=True)
        frame["risk_rank"] = self._percentile(frame.get("risk_score"), higher_is_better=False)

        ranked: list[dict[str, Any]] = []
        for index, item in enumerate(items):
            enriched = dict(item)
            enriched["buy_score_percentile"] = round(float(frame.iloc[index]["buy_score_percentile"]), 2)
            enriched["sell_score_percentile"] = round(float(frame.iloc[index]["sell_score_percentile"]), 2)
            enriched["relative_strength_rank"] = round(float(frame.iloc[index]["relative_strength_rank"]), 2)
            enriched["liquidity_rank"] = round(float(frame.iloc[index]["liquidity_rank"]), 2)
            enriched["risk_rank"] = round(float(frame.iloc[index]["risk_rank"]), 2)
            ranked.append(enriched)
        return ranked

    def _percentile(self, series: pd.Series | None, *, higher_is_better: bool) -> pd.Series:
        if series is None:
            return pd.Series(np.full(1, 50.0))

        values = pd.to_numeric(series, errors="coerce").fillna(0.0)
        if len(values) <= 1 or values.nunique() <= 1:
            return pd.Series(np.full(len(values), 50.0), index=values.index)

        ranked_values = values if higher_is_better else -values
        return ranked_values.rank(method="average", pct=True) * 100
