from __future__ import annotations

from typing import Any


class CitationGuardrail:
    name = "validate_citations"

    def run(
        self,
        claims: list[dict[str, Any]],
    ) -> list[str]:
        return [
            f"Unsupported claim: {claim.get('claim', '<missing>')}"
            for claim in claims
            if not claim.get("citations")
        ]


class LeakageGuardrail:
    name = "prevent_permission_leakage"

    def run(
        self,
        denied: bool,
        output: str,
    ) -> str:
        if denied:
            return "Access denied. The requested opportunity is unavailable for this requester."

        return output
