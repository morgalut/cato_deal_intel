from __future__ import annotations


class OpportunityNotFoundError(Exception):
    def __init__(self, opportunity_id: str) -> None:
        self.opportunity_id = opportunity_id

        super().__init__(f"Opportunity not found: {opportunity_id}")
