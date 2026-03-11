from __future__ import annotations

import hashlib
from typing import Protocol

from agent_etf_contracts.models import (
    BacktestMetrics,
    BacktestRun,
    StrategyDefinition,
    TimeframePerformance,
)


class BacktestEngine(Protocol):
    def run(
        self,
        strategy: StrategyDefinition,
        min_years: int,
        override_min_history: bool,
    ) -> BacktestRun:
        ...


class DeterministicBacktestEngine:
    """Deterministic pseudo-backtest engine scaffold."""

    def _metric_seed(self, strategy_id: str) -> float:
        digest = hashlib.sha256(strategy_id.encode("utf-8")).hexdigest()
        return int(digest[:6], 16) / 0xFFFFFF

    def _timeframe_performance(self, seed: float) -> list[TimeframePerformance]:
        windows = [
            ("1M", 0.008),
            ("3M", 0.021),
            ("6M", 0.038),
            ("1Y", 0.081),
            ("3Y", 0.247),
            ("5Y", 0.438),
            ("Since Inception", 0.612),
        ]
        benchmarks = {
            "sp500": [0.011, 0.028, 0.049, 0.093, 0.263, 0.472, 0.688],
            "gold": [0.006, 0.019, 0.044, 0.071, 0.218, 0.366, 0.522],
            "60_40": [0.007, 0.017, 0.031, 0.066, 0.192, 0.301, 0.421],
            "cash": [0.002, 0.006, 0.012, 0.025, 0.071, 0.122, 0.171],
        }

        rows: list[TimeframePerformance] = []
        for index, (label, base_return) in enumerate(windows):
            adjustment = (seed - 0.5) * 0.08
            strategy_return = round(base_return + adjustment, 4)
            rows.append(
                TimeframePerformance(
                    timeframe=label,
                    strategy_return=strategy_return,
                    benchmark_returns={
                        name: round(values[index], 4) for name, values in benchmarks.items()
                    },
                )
            )
        return rows

    def run(
        self,
        strategy: StrategyDefinition,
        min_years: int,
        override_min_history: bool,
    ) -> BacktestRun:
        years_of_history = max(5, min(20, len(strategy.universe) + 9))
        if years_of_history < min_years and not override_min_history:
            raise ValueError(
                f"Insufficient history ({years_of_history}y) for required minimum {min_years}y"
            )

        seed = self._metric_seed(strategy.id)
        cagr = 0.04 + seed * 0.14
        volatility = 0.10 + seed * 0.18
        sharpe = cagr / max(volatility, 0.01)
        max_drawdown = -(0.08 + seed * 0.35)

        strategy_metrics = BacktestMetrics(
            cagr=round(cagr, 4),
            volatility=round(volatility, 4),
            sharpe=round(sharpe, 4),
            max_drawdown=round(max_drawdown, 4),
            years_of_history=years_of_history,
        )

        benchmark_metrics = {
            "sp500": BacktestMetrics(
                cagr=0.091,
                volatility=0.165,
                sharpe=0.5515,
                max_drawdown=-0.51,
                years_of_history=20,
            ),
            "gold": BacktestMetrics(
                cagr=0.066,
                volatility=0.152,
                sharpe=0.4342,
                max_drawdown=-0.45,
                years_of_history=20,
            ),
            "60_40": BacktestMetrics(
                cagr=0.071,
                volatility=0.11,
                sharpe=0.6455,
                max_drawdown=-0.32,
                years_of_history=20,
            ),
            "cash": BacktestMetrics(
                cagr=0.025,
                volatility=0.01,
                sharpe=2.5,
                max_drawdown=-0.01,
                years_of_history=20,
            ),
        }

        return BacktestRun(
            strategy_id=strategy.id,
            assumptions={
                "frequency": "EOD",
                "transaction_cost_bps": 10,
                "slippage_bps": 5,
                "paper_only": True,
            },
            metrics=strategy_metrics,
            benchmark_metrics=benchmark_metrics,
            timeframe_performance=self._timeframe_performance(seed),
        )
