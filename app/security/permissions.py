from __future__ import annotations

from typing import Any

from app.contracts.brief import EvidenceCitation, StrategicDealBrief
from app.repositories.database import Database


class PermissionDeniedError(Exception):
    def __init__(self, reason: str = "access_denied") -> None:
        self.reason: str = reason
        super().__init__(reason)


class PermissionService:
    """DB-backed authorization service.

    Enforces permissions before retrieval and before returning generated output.
    """

    def __init__(self, db: Database | None = None) -> None:
        self.db: Database = db or Database()

    def get_user_profile(self, user_id: str) -> dict[str, Any]:
        with self.db.connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    user_id,
                    role,
                    allowed_account_ids,
                    allowed_source_types,
                    can_view_restricted_account,
                    can_view_sensitive_pricing
                FROM access_permissions
                WHERE user_id = %s
                """,
                (user_id,),
            )

            row = cur.fetchone()

            if row is None:
                raise PermissionDeniedError("unknown_requester")

            return self._row_to_dict(cur, row)

    def allowed_source_types(
        self,
        profile: dict[str, Any],
    ) -> list[str]:
        return [str(source_type) for source_type in profile["allowed_source_types"]]

    def allowed_access_levels(
        self,
        profile: dict[str, Any],
    ) -> list[str]:
        allowed: list[str] = ["standard"]

        if bool(profile.get("can_view_restricted_account")):
            allowed.append("restricted")

        if bool(profile.get("can_view_sensitive_pricing")):
            allowed.append("sensitive_pricing")

        return allowed

    def authorize_opportunity(
        self,
        user_id: str,
        opportunity_id: str,
    ) -> dict[str, Any]:
        profile: dict[str, Any] = self.get_user_profile(user_id)

        with self.db.connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    opportunity_id,
                    account_id,
                    account_name,
                    stage,
                    type,
                    acv,
                    tcv,
                    close_date,
                    owner,
                    risk_level,
                    restricted_access
                FROM opportunities
                WHERE opportunity_id = %s
                """,
                (opportunity_id,),
            )

            row = cur.fetchone()

            if row is None:
                raise PermissionDeniedError("opportunity_not_accessible")

            opportunity: dict[str, Any] = self._row_to_dict(cur, row)

        allowed_accounts: set[str] = set(profile["allowed_account_ids"])

        if str(opportunity["account_id"]) not in allowed_accounts:
            raise PermissionDeniedError("access_denied")

        if bool(opportunity.get("restricted_access")) and not bool(
            profile.get("can_view_restricted_account"),
        ):
            raise PermissionDeniedError("access_denied")

        return {
            "profile": profile,
            "opportunity": opportunity,
        }

    def can_retrieve_doc(
        self,
        profile: dict[str, Any],
        doc: dict[str, Any],
    ) -> bool:
        allowed_source_types: set[str] = set(profile["allowed_source_types"])

        if doc.get("source_type") not in allowed_source_types:
            return False

        if doc.get("source_access_level") == "restricted" and not bool(
            profile.get("can_view_restricted_account"),
        ):
            return False

        return not (
            doc.get("source_access_level") == "sensitive_pricing"
            and not bool(profile.get("can_view_sensitive_pricing"))
        )

    def validate_and_sanitize_response(
        self,
        profile: dict[str, Any],
        brief: StrategicDealBrief,
    ) -> StrategicDealBrief:
        """Final pre-response guardrail.

        Ensures every citation in the generated brief points only to evidence
        that exists in the already-authorized source_evidence list.
        """

        allowed_source_types: set[str] = set(profile["allowed_source_types"])

        allowed_evidence: dict[tuple[str, str], str] = {
            (
                evidence.source_type,
                evidence.stable_source_id,
            ): evidence.source_access_level
            for evidence in brief.source_evidence
        }

        for citation in self._collect_brief_citations(brief):
            key = (
                citation.source_type,
                citation.stable_source_id,
            )

            if citation.source_type not in allowed_source_types:
                raise PermissionDeniedError("leakage_detected_source_type")

            if key not in allowed_evidence:
                raise PermissionDeniedError("leakage_detected_unknown_citation")

            access_level = allowed_evidence[key]

            if access_level == "restricted" and not bool(
                profile.get("can_view_restricted_account"),
            ):
                raise PermissionDeniedError("leakage_detected_restricted_source")

            if access_level == "sensitive_pricing" and not bool(
                profile.get("can_view_sensitive_pricing"),
            ):
                raise PermissionDeniedError("leakage_detected_pricing_source")

        return brief

    def _collect_brief_citations(
        self,
        brief: StrategicDealBrief,
    ) -> list[EvidenceCitation]:
        citations: list[EvidenceCitation] = []

        citations.extend(brief.deal_snapshot.citations)

        for finding in brief.buyer_goals_and_business_drivers:
            citations.extend(finding.citations)

        for finding in brief.negotiation_state:
            citations.extend(finding.citations)

        for stakeholder in brief.stakeholder_map:
            citations.extend(stakeholder.citations)

        for recommendation in brief.recommended_next_actions:
            citations.extend(recommendation.citations)

        return citations

    def _row_to_dict(
        self,
        cursor: Any,
        row: Any,
    ) -> dict[str, Any]:
        if isinstance(row, dict):
            return row

        columns = [description[0] for description in cursor.description]

        return dict(zip(columns, row, strict=False))
