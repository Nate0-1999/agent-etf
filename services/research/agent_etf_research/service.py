from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from agent_etf_contracts.models import CandidateInstrument, IdeaSpec, UserPermissionProfile
from agent_etf_llm_gateway import OpenRouterModelService


@dataclass
class SearchHit:
    title: str
    url: str


class SearchProvider(Protocol):
    def search(self, query: str, limit: int = 5) -> list[SearchHit]:
        ...


class ExaSearchProvider:
    """Exa-like search provider stub for deterministic scaffolding."""

    def search(self, query: str, limit: int = 5) -> list[SearchHit]:
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

        self._catalog: list[dict[str, str | float]] = [
            {
                "symbol": "PICK",
                "name": "iShares MSCI Global Metals & Mining Producers ETF",
                "asset_type": "etf",
                "exchange": "NYSE",
                "score": 0.86,
                "tag": "metals",
            },
            {
                "symbol": "XME",
                "name": "SPDR S&P Metals and Mining ETF",
                "asset_type": "etf",
                "exchange": "NYSE",
                "score": 0.84,
                "tag": "metals",
            },
            {
                "symbol": "REMX",
                "name": "VanEck Rare Earth/Strategic Metals ETF",
                "asset_type": "etf",
                "exchange": "NYSE",
                "score": 0.79,
                "tag": "rare-earth",
            },
            {
                "symbol": "PPLT",
                "name": "abrdn Physical Platinum Shares ETF",
                "asset_type": "etf",
                "exchange": "NYSE",
                "score": 0.81,
                "tag": "platinum",
            },
            {
                "symbol": "PALL",
                "name": "abrdn Physical Palladium Shares ETF",
                "asset_type": "etf",
                "exchange": "NYSE",
                "score": 0.8,
                "tag": "palladium",
            },
            {
                "symbol": "GC",
                "name": "COMEX Gold Futures",
                "asset_type": "future",
                "exchange": "CME",
                "score": 0.72,
                "tag": "precious",
            },
            {
                "symbol": "PL",
                "name": "COMEX Platinum Futures",
                "asset_type": "future",
                "exchange": "CME",
                "score": 0.78,
                "tag": "platinum",
            },
            {
                "symbol": "PA",
                "name": "NYMEX Palladium Futures",
                "asset_type": "future",
                "exchange": "NYMEX",
                "score": 0.77,
                "tag": "palladium",
            },
            {
                "symbol": "RIO",
                "name": "Rio Tinto plc",
                "asset_type": "equity",
                "exchange": "NYSE",
                "score": 0.74,
                "tag": "miner",
            },
        ]

    def discover_candidates(
        self,
        idea: IdeaSpec,
        permissions: UserPermissionProfile,
    ) -> list[CandidateInstrument]:
        query = idea.objective or idea.raw_idea
        hits = self._search.search(query=query, limit=4)

        tradable = set(item.lower() for item in permissions.tradable_asset_types)

        candidates: list[CandidateInstrument] = []
        for row in self._catalog:
            asset_type = str(row["asset_type"]).lower()
            if asset_type not in tradable:
                continue

            sources = [hit.url for hit in hits]
            candidates.append(
                CandidateInstrument(
                    symbol=str(row["symbol"]),
                    name=str(row["name"]),
                    asset_type=asset_type,
                    exchange=str(row["exchange"]),
                    relevance_score=float(row["score"]),
                    rationale=f"Matches thematic exposure tag: {row['tag']}",
                    sources=sources,
                )
            )

        ranked = self._models.rank_candidates(raw_idea=idea.raw_idea, candidates=candidates)
        filtered = [candidate for candidate in ranked if candidate.relevance_score >= 0.72]
        return filtered[:12]
