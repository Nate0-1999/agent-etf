from __future__ import annotations

import os
import re
from datetime import UTC, datetime
from uuid import uuid4

import httpx
from agent_etf_contracts.models import (
    ApprovedModelSet,
    ModelCatalogEntry,
    ModelProposalStatus,
    ModelProviderFamily,
    PendingModelSetProposal,
)
from agent_etf_contracts.store import StrategyStore

_OPENROUTER_MODELS_URL = "https://openrouter.ai/api/v1/models"
_OFFICIAL_DOCS = {
    ModelProviderFamily.openai: "https://developers.openai.com/api/docs/models",
    ModelProviderFamily.anthropic: "https://platform.claude.com/docs/en/about-claude/models/overview",
    ModelProviderFamily.google: "https://ai.google.dev/gemini-api/docs/models",
}
_EXCLUDED_TOKENS = {"preview", "beta", "exp", "experimental", "thinking"}


class OpenRouterModelRegistry:
    def __init__(self, api_key: str | None = None) -> None:
        self._api_key = api_key or os.getenv("OPENROUTER_API_KEY")

    def ensure_current_model_set(self, store: StrategyStore) -> ApprovedModelSet:
        current = store.get_current_model_set()
        if current is not None:
            return current
        catalog = self.fetch_catalog()
        store.replace_model_catalog(catalog)
        current = self._build_model_set(catalog)
        store.save_current_model_set(current)
        return current

    def fetch_catalog(self) -> list[ModelCatalogEntry]:
        headers = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"

        try:
            response = httpx.get(_OPENROUTER_MODELS_URL, headers=headers, timeout=15.0)
            response.raise_for_status()
            payload = response.json()
            rows = payload.get("data", payload)
            if isinstance(rows, list):
                catalog = self._from_openrouter_rows(rows)
                if catalog:
                    return catalog
        except Exception:
            pass

        return self._fallback_catalog()

    def refresh(
        self, store: StrategyStore
    ) -> tuple[list[ModelCatalogEntry], ApprovedModelSet, PendingModelSetProposal | None]:
        current = self.ensure_current_model_set(store)
        catalog = (
            self._test_refresh_catalog(current)
            if os.getenv("AGENTIC_TEST_MODE") == "1"
            else self.fetch_catalog()
        )
        store.replace_model_catalog(catalog)
        proposed = self._build_model_set(catalog)
        if self._same_model_set(current, proposed):
            return catalog, current, None

        existing = self._find_matching_pending(store, proposed)
        if existing is not None:
            return catalog, current, existing

        proposal = PendingModelSetProposal(
            id=str(uuid4()),
            current_set_id=current.id,
            proposed_set=proposed,
            rationale="A newer stable provider trio is available from the registry catalog.",
            status=ModelProposalStatus.pending,
        )
        store.save_model_proposal(proposal)
        return catalog, current, proposal

    def approve(self, store: StrategyStore, proposal_id: str) -> ApprovedModelSet:
        proposal = store.get_model_proposal(proposal_id)
        if proposal is None:
            raise KeyError("Model proposal not found")

        approved = proposal.model_copy(
            update={
                "status": ModelProposalStatus.approved,
                "approved_at": datetime.now(UTC),
            }
        )
        store.save_model_proposal(approved)
        store.save_current_model_set(approved.proposed_set)

        for item in store.list_model_proposals():
            if item.id == proposal_id or item.status != ModelProposalStatus.pending:
                continue
            store.save_model_proposal(
                item.model_copy(update={"status": ModelProposalStatus.superseded})
            )

        return approved.proposed_set

    @staticmethod
    def approved_model_ids(model_set: ApprovedModelSet) -> list[str]:
        return [
            f"openai:{model_set.openai_model.openrouter_slug}",
            f"anthropic:{model_set.anthropic_model.openrouter_slug}",
            f"google:{model_set.google_model.openrouter_slug}",
        ]

    def _find_matching_pending(
        self,
        store: StrategyStore,
        proposed_set: ApprovedModelSet,
    ) -> PendingModelSetProposal | None:
        for proposal in store.list_model_proposals():
            if proposal.status != ModelProposalStatus.pending:
                continue
            if self._same_model_set(proposal.proposed_set, proposed_set):
                return proposal
        return None

    @staticmethod
    def _same_model_set(left: ApprovedModelSet, right: ApprovedModelSet) -> bool:
        return bool(
            left.openai_model.id == right.openai_model.id
            and left.anthropic_model.id == right.anthropic_model.id
            and left.google_model.id == right.google_model.id
        )

    def _build_model_set(self, catalog: list[ModelCatalogEntry]) -> ApprovedModelSet:
        families = {
            ModelProviderFamily.openai: self._pick_latest(catalog, ModelProviderFamily.openai),
            ModelProviderFamily.anthropic: self._pick_latest(
                catalog, ModelProviderFamily.anthropic
            ),
            ModelProviderFamily.google: self._pick_latest(catalog, ModelProviderFamily.google),
        }
        return ApprovedModelSet(
            id=str(uuid4()),
            openai_model=families[ModelProviderFamily.openai],
            anthropic_model=families[ModelProviderFamily.anthropic],
            google_model=families[ModelProviderFamily.google],
        )

    def _pick_latest(
        self,
        catalog: list[ModelCatalogEntry],
        provider: ModelProviderFamily,
    ) -> ModelCatalogEntry:
        eligible = [entry for entry in catalog if entry.provider == provider and entry.is_stable]
        if not eligible:
            fallback = [entry for entry in self._fallback_catalog() if entry.provider == provider]
            eligible = fallback
        return max(
            eligible,
            key=lambda entry: (self._version_key(entry.label), self._version_key(entry.id)),
        )

    def _from_openrouter_rows(self, rows: list[object]) -> list[ModelCatalogEntry]:
        catalog: list[ModelCatalogEntry] = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            identifier = str(row.get("id", "")).strip()
            name = str(row.get("name", identifier)).strip()
            provider = self._provider_for(identifier=identifier, label=name)
            if provider is None:
                continue
            if not self._looks_supported(identifier=identifier, label=name, provider=provider):
                continue
            slug = identifier.split("/")[-1] if "/" in identifier else identifier.split(":")[-1]
            catalog.append(
                ModelCatalogEntry(
                    id=f"{provider.value}-{slug}",
                    provider=provider,
                    family=self._family_name(provider),
                    label=name,
                    openrouter_slug=slug,
                    official_doc_url=_OFFICIAL_DOCS[provider],
                    is_stable=self._is_stable(identifier, name),
                    supports_text=True,
                )
            )
        deduped: dict[str, ModelCatalogEntry] = {}
        for entry in catalog:
            deduped[entry.id] = entry
        return sorted(deduped.values(), key=lambda entry: entry.id)

    @staticmethod
    def _provider_for(identifier: str, label: str) -> ModelProviderFamily | None:
        lowered = f"{identifier} {label}".lower()
        if "gpt" in lowered or identifier.startswith("openai/"):
            return ModelProviderFamily.openai
        if "claude" in lowered or identifier.startswith("anthropic/"):
            return ModelProviderFamily.anthropic
        if "gemini" in lowered or identifier.startswith("google/"):
            return ModelProviderFamily.google
        return None

    @staticmethod
    def _family_name(provider: ModelProviderFamily) -> str:
        return {
            ModelProviderFamily.openai: "GPT-5",
            ModelProviderFamily.anthropic: "Claude 4",
            ModelProviderFamily.google: "Gemini 3",
        }[provider]

    def _looks_supported(
        self,
        identifier: str,
        label: str,
        provider: ModelProviderFamily,
    ) -> bool:
        lowered = f"{identifier} {label}".lower()
        if provider == ModelProviderFamily.openai:
            return "gpt-5" in lowered
        if provider == ModelProviderFamily.anthropic:
            return "claude" in lowered and "4" in lowered
        return "gemini" in lowered and "3" in lowered

    @staticmethod
    def _is_stable(identifier: str, label: str) -> bool:
        lowered = f"{identifier} {label}".lower()
        return not any(token in lowered for token in _EXCLUDED_TOKENS)

    @staticmethod
    def _version_key(value: str) -> tuple[int, ...]:
        matches = re.findall(r"(\d+)", value)
        if not matches:
            return (0,)
        return tuple(int(match) for match in matches[:3])

    @staticmethod
    def _fallback_catalog() -> list[ModelCatalogEntry]:
        return [
            ModelCatalogEntry(
                id="openai-gpt-5.4",
                provider=ModelProviderFamily.openai,
                family="GPT-5",
                label="GPT-5.4",
                openrouter_slug="gpt-5.4",
                official_doc_url=_OFFICIAL_DOCS[ModelProviderFamily.openai],
            ),
            ModelCatalogEntry(
                id="anthropic-claude-4.6",
                provider=ModelProviderFamily.anthropic,
                family="Claude 4",
                label="Claude 4.6",
                openrouter_slug="claude-4.6",
                official_doc_url=_OFFICIAL_DOCS[ModelProviderFamily.anthropic],
            ),
            ModelCatalogEntry(
                id="google-gemini-3.1-pro",
                provider=ModelProviderFamily.google,
                family="Gemini 3",
                label="Gemini 3.1 Pro",
                openrouter_slug="gemini-3.1-pro",
                official_doc_url=_OFFICIAL_DOCS[ModelProviderFamily.google],
            ),
        ]

    @staticmethod
    def _test_refresh_catalog(current: ApprovedModelSet) -> list[ModelCatalogEntry]:
        return [
            current.openai_model,
            current.anthropic_model,
            current.google_model,
            ModelCatalogEntry(
                id="openai-gpt-5.5",
                provider=ModelProviderFamily.openai,
                family="GPT-5",
                label="GPT-5.5",
                openrouter_slug="gpt-5.5",
                official_doc_url=_OFFICIAL_DOCS[ModelProviderFamily.openai],
            ),
            ModelCatalogEntry(
                id="anthropic-claude-4.7",
                provider=ModelProviderFamily.anthropic,
                family="Claude 4",
                label="Claude 4.7",
                openrouter_slug="claude-4.7",
                official_doc_url=_OFFICIAL_DOCS[ModelProviderFamily.anthropic],
            ),
            ModelCatalogEntry(
                id="google-gemini-3.2-pro",
                provider=ModelProviderFamily.google,
                family="Gemini 3",
                label="Gemini 3.2 Pro",
                openrouter_slug="gemini-3.2-pro",
                official_doc_url=_OFFICIAL_DOCS[ModelProviderFamily.google],
            ),
        ]
