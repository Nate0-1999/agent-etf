from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from agent_etf_contracts.models import ApprovalBundle, UserPermissionProfile


@dataclass
class OrderPreview:
    strategy_id: str
    action: str
    orders: list[dict[str, float | str]]


class BrokerAdapter(Protocol):
    """Broker execution contract.

    Implementations must never submit live orders in MVP.
    """

    def link_account(self, user_id: str, account_id: str) -> UserPermissionProfile:
        ...

    def fetch_permissions(self, user_id: str) -> UserPermissionProfile:
        ...

    def build_order_preview(self, bundle: ApprovalBundle) -> OrderPreview:
        ...

    def submit_paper_orders(self, bundle: ApprovalBundle) -> dict[str, str]:
        ...
