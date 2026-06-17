from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd


class PermissionDeniedError(Exception):
    def __init__(self, reason: str = "access_denied") -> None:
        self.reason: str = reason
        super().__init__(reason)


class PermissionService:
    """Central authorization service.

    Unauthorized sources must not be retrieved, summarized, cited,
    or leaked as metadata.
    """

    def __init__(self, data_dir: str = "data") -> None:
        self.data_dir: Path = Path(data_dir)

        self.permissions = pd.read_csv(
            self.data_dir / "policies" / "access_permissions.tsv",
            sep="\t",
        )

        self.opportunities = pd.read_csv(
            self.data_dir / "salesforce" / "opportunities.tsv",
            sep="\t",
        )

    def profile(self, user_id: str) -> dict[str, Any]:
        rows = self.permissions[self.permissions.user_id == user_id]

        if rows.empty:
            raise PermissionDeniedError("unknown_requester")

        return rows.iloc[0].to_dict()

    def authorize_opportunity(
        self,
        user_id: str,
        opportunity_id: str,
    ) -> dict[str, Any]:
        profile: dict[str, Any] = self.profile(user_id)

        opportunity_rows = self.opportunities[self.opportunities.opportunity_id == opportunity_id]

        if opportunity_rows.empty:
            raise PermissionDeniedError("opportunity_not_accessible")

        opportunity: dict[str, Any] = opportunity_rows.iloc[0].to_dict()

        allowed_accounts: set[str] = set(str(profile["allowed_account_ids"]).split(","))

        if opportunity["account_id"] not in allowed_accounts:
            raise PermissionDeniedError()

        if bool(opportunity.get("restricted_access")) and not bool(
            profile.get("can_view_restricted_account")
        ):
            raise PermissionDeniedError()

        return {
            "profile": profile,
            "opportunity": opportunity,
        }

    def allowed_source_types(self, user_id: str) -> set[str]:
        return set(str(self.profile(user_id)["allowed_source_types"]).split(","))

    def can_retrieve_doc(
        self,
        user_id: str,
        doc: dict[str, Any],
    ) -> bool:
        profile: dict[str, Any] = self.profile(user_id)

        source_allowed: bool = doc.get("source_type") in self.allowed_source_types(user_id)

        restricted_allowed: bool = not (
            doc.get("source_access_level") == "restricted"
            and not bool(profile.get("can_view_restricted_account"))
        )

        pricing_allowed: bool = not (
            doc.get("source_access_level") == "sensitive_pricing"
            and not bool(profile.get("can_view_sensitive_pricing"))
        )

        return source_allowed and restricted_allowed and pricing_allowed
