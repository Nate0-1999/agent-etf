from __future__ import annotations

from datetime import UTC, datetime

from agent_etf_contracts.models import ApprovalBundle, UserPermissionProfile

from agent_etf_brokers.base import BrokerAdapter, OrderPreview


class IbkrPaperAdapter(BrokerAdapter):
    """IBKR paper adapter stub for controlled development."""

    def __init__(self) -> None:
        self._profiles: dict[str, UserPermissionProfile] = {}

    def link_account(self, user_id: str, account_id: str) -> UserPermissionProfile:
        profile = UserPermissionProfile(
            user_id=user_id,
            broker="ibkr",
            account_id=account_id,
            tradable_asset_types=["etf", "equity", "future", "option", "bond", "cash"],
            tradable_markets=["US", "EU", "APAC"],
            max_leverage=1.0,
            allow_short=False,
            user_limits={"created_at": datetime.now(UTC).isoformat()},
        )
        self._profiles[user_id] = profile
        return profile

    def fetch_permissions(self, user_id: str) -> UserPermissionProfile:
        if user_id not in self._profiles:
            return self.link_account(user_id=user_id, account_id="paper-default")
        return self._profiles[user_id]

    def build_order_preview(self, bundle: ApprovalBundle) -> OrderPreview:
        orders = [
            {
                "symbol": symbol,
                "target_weight": weight,
                "action": "rebalance",
            }
            for symbol, weight in bundle.target_allocations.items()
        ]
        return OrderPreview(
            strategy_id=bundle.strategy_id,
            action=bundle.action.value,
            orders=orders,
        )

    def submit_paper_orders(self, bundle: ApprovalBundle) -> dict[str, str]:
        return {
            "status": "submitted_paper",
            "strategy_id": bundle.strategy_id,
            "bundle_id": bundle.id,
            "submitted_at": datetime.now(UTC).isoformat(),
        }
