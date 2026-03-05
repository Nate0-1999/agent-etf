from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Protocol, cast

import httpx
from agent_etf_contracts.models import CandidateInstrument, IdeaSpec, UserPermissionProfile
from agent_etf_llm_gateway import OpenRouterModelService
from agent_etf_research.heavy_metals import derive_heavy_metal_profile


@dataclass
class SearchHit:
    title: str
    url: str


class SearchProvider(Protocol):
    def search(self, query: str, limit: int = 5) -> list[SearchHit]:
        ...


class ExaSearchProvider:
    """Search provider with Exa support and deterministic fallback."""

    def __init__(self, api_key: str | None = None) -> None:
        self._api_key = api_key or os.getenv("EXA_API_KEY")

    def search(self, query: str, limit: int = 5) -> list[SearchHit]:
        if not self._api_key:
            cleaned = query.lower().replace(" ", "-")
            return [
                SearchHit(
                    title=f"Research result {index + 1}",
                    url=f"https://example.com/{cleaned}/{index + 1}",
                )
                for index in range(limit)
            ]

        try:
            response = httpx.post(
                "https://api.exa.ai/search",
                headers={
                    "Content-Type": "application/json",
                    "x-api-key": self._api_key,
                },
                json={
                    "query": query,
                    "numResults": limit,
                    "contents": {"text": False},
                },
                timeout=15.0,
            )
            response.raise_for_status()
            body = response.json()
            hits: list[SearchHit] = []
            for item in cast(list[dict[str, Any]], body.get("results", [])):
                hits.append(
                    SearchHit(
                        title=str(item.get("title", "Untitled result")),
                        url=str(item.get("url", "")),
                    )
                )
            if hits:
                return hits
        except Exception:
            pass

        cleaned = query.lower().replace(" ", "-")
        return [
            SearchHit(
                title=f"Research result {index + 1}",
                url=f"https://example.com/{cleaned}/{index + 1}",
            )
            for index in range(limit)
        ]


class ResearchService:
    def __init__(
        self,
        search_provider: SearchProvider,
        model_service: OpenRouterModelService,
    ) -> None:
        self._search = search_provider
        self._models = model_service

        self._catalog: list[dict[str, object]] = [
            {
                "symbol": "PPLT",
                "name": "abrdn Physical Platinum Shares ETF",
                "asset_type": "etf",
                "exchange": "NYSE",
                "score": 0.88,
                "elements": ["Pt"],
                "theme": "physical",
            },
            {
                "symbol": "PALL",
                "name": "abrdn Physical Palladium Shares ETF",
                "asset_type": "etf",
                "exchange": "NYSE",
                "score": 0.87,
                "elements": ["Pd"],
                "theme": "physical",
            },
            {
                "symbol": "GLTR",
                "name": "abrdn Physical Precious Metals Basket Shares ETF",
                "asset_type": "etf",
                "exchange": "NYSE",
                "score": 0.84,
                "elements": ["Au", "Ag", "Pt", "Pd"],
                "theme": "basket",
            },
            {
                "symbol": "GLD",
                "name": "SPDR Gold Shares",
                "asset_type": "etf",
                "exchange": "NYSE",
                "score": 0.81,
                "elements": ["Au"],
                "theme": "physical",
            },
            {
                "symbol": "SLV",
                "name": "iShares Silver Trust",
                "asset_type": "etf",
                "exchange": "NYSE",
                "score": 0.8,
                "elements": ["Ag"],
                "theme": "physical",
            },
            {
                "symbol": "PICK",
                "name": "iShares MSCI Global Metals & Mining Producers ETF",
                "asset_type": "etf",
                "exchange": "NYSE",
                "score": 0.83,
                "elements": ["Mo", "Ag", "Sn", "Te", "W", "Re", "Pt", "Au"],
                "theme": "miners",
            },
            {
                "symbol": "XME",
                "name": "SPDR S&P Metals and Mining ETF",
                "asset_type": "etf",
                "exchange": "NYSE",
                "score": 0.8,
                "elements": ["Mo", "Ag", "W", "Au"],
                "theme": "miners",
            },
            {
                "symbol": "GC",
                "name": "COMEX Gold Futures",
                "asset_type": "future",
                "exchange": "CME",
                "score": 0.82,
                "elements": ["Au"],
                "theme": "futures",
            },
            {
                "symbol": "SI",
                "name": "COMEX Silver Futures",
                "asset_type": "future",
                "exchange": "CME",
                "score": 0.8,
                "elements": ["Ag"],
                "theme": "futures",
            },
            {
                "symbol": "PL",
                "name": "COMEX Platinum Futures",
                "asset_type": "future",
                "exchange": "CME",
                "score": 0.86,
                "elements": ["Pt"],
                "theme": "futures",
            },
            {
                "symbol": "PA",
                "name": "NYMEX Palladium Futures",
                "asset_type": "future",
                "exchange": "NYMEX",
                "score": 0.85,
                "elements": ["Pd"],
                "theme": "futures",
            },
            {
                "symbol": "RIO",
                "name": "Rio Tinto plc",
                "asset_type": "equity",
                "exchange": "NYSE",
                "score": 0.76,
                "elements": ["Ag", "Mo", "Te", "W", "Au"],
                "theme": "miners",
            },
            {
                "symbol": "BHP",
                "name": "BHP Group Limited",
                "asset_type": "equity",
                "exchange": "NYSE",
                "score": 0.75,
                "elements": ["Ag", "Mo", "Au"],
                "theme": "miners",
            },
        ]

    @staticmethod
    def _theme_profile(idea: IdeaSpec) -> dict[str, object] | None:
        periodic_table = idea.constraints.get("periodic_table")
        if isinstance(periodic_table, dict):
            return cast(dict[str, object], periodic_table)
        profile = derive_heavy_metal_profile(idea.objective or idea.raw_idea)
        return cast(dict[str, object] | None, profile)

    @staticmethod
    def _element_overlap(
        theme_profile: dict[str, object] | None,
        row: dict[str, object],
    ) -> list[str]:
        if theme_profile is None:
            return []
        target_symbols = {
            str(symbol)
            for symbol in cast(list[object], theme_profile.get("element_symbols", []))
        }
        row_symbols = [str(symbol) for symbol in cast(list[object], row.get("elements", []))]
        return [symbol for symbol in row_symbols if symbol in target_symbols]

    def discover_candidates(
        self,
        idea: IdeaSpec,
        permissions: UserPermissionProfile,
    ) -> list[CandidateInstrument]:
        query = idea.objective or idea.raw_idea
        hits = self._search.search(query=f"{query} investment vehicles", limit=4)
        theme_profile = self._theme_profile(idea)

        tradable = set(item.lower() for item in permissions.tradable_asset_types)
        allowed_assets = {
            str(item).lower()
            for item in cast(list[object], idea.constraints.get("allowed_assets", []))
        }

        candidates: list[CandidateInstrument] = []
        for row in self._catalog:
            asset_type = str(row["asset_type"]).lower()
            if asset_type not in tradable:
                continue
            if allowed_assets and asset_type not in allowed_assets:
                continue

            overlap_symbols = self._element_overlap(theme_profile, row)
            if theme_profile is not None and not overlap_symbols:
                continue

            base_score = float(cast(float | int | str, row["score"]))
            overlap_bonus = 0.04 * len(overlap_symbols)
            sources = [hit.url for hit in hits]

            rationale = f"Theme={row['theme']}"
            if overlap_symbols:
                rationale += ", element overlap=" + ", ".join(overlap_symbols)

            candidates.append(
                CandidateInstrument(
                    symbol=str(row["symbol"]),
                    name=str(row["name"]),
                    asset_type=asset_type,
                    exchange=str(row["exchange"]),
                    relevance_score=min(0.99, base_score + overlap_bonus),
                    rationale=rationale,
                    sources=sources,
                )
            )

        ranked = self._models.rank_candidates(raw_idea=idea.raw_idea, candidates=candidates)
        filtered = [candidate for candidate in ranked if candidate.relevance_score >= 0.75]
        return filtered[:12]
