from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path
from typing import Protocol

from agent_etf_contracts.models import StrategyArtifact, StrategyDefinition


class StrategyCompiler(Protocol):
    def compile(self, strategy: StrategyDefinition) -> StrategyArtifact:
        ...


class DeterministicStrategyCompiler:
    def __init__(self, output_dir: Path | None = None) -> None:
        self._output_dir = output_dir or Path("generated_strategies")
        self._output_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _git_commit() -> str:
        try:
            completed = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                check=True,
                capture_output=True,
                text=True,
            )
            return completed.stdout.strip()
        except Exception:
            return "uncommitted"

    def compile(self, strategy: StrategyDefinition) -> StrategyArtifact:
        payload = strategy.model_dump(mode="json")
        stable_json = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        config_hash = hashlib.sha256(stable_json.encode("utf-8")).hexdigest()

        sorted_universe = sorted(strategy.universe, key=lambda item: item.symbol)
        symbols = [item.symbol for item in sorted_universe]

        source_code = (
            "# Auto-generated deterministic strategy artifact\n"
            f"STRATEGY_ID = '{strategy.id}'\n"
            f"NAME = {strategy.name!r}\n"
            f"WEIGHTING_METHOD = {strategy.weighting_method!r}\n"
            f"REBALANCE_RULE = {strategy.rebalance_rule!r}\n"
            f"UPDATE_RULE = {strategy.update_rule!r}\n"
            f"UNIVERSE = {symbols!r}\n"
        )

        file_name = f"{strategy.id}_{config_hash[:12]}.py"
        output_file = self._output_dir / file_name
        output_file.write_text(source_code, encoding="utf-8")

        return StrategyArtifact(
            strategy_id=strategy.id,
            git_commit=self._git_commit(),
            config_hash=config_hash,
            source_code=source_code,
        )
