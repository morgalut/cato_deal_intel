from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd
from app.agents.base import AgentBase
from app.observability.tracing import TraceBuffer


class StakeholderMapAgent(AgentBase):
    name = "stakeholder_map_agent"

    system_contract = "Build buying committee from contacts and conversation evidence."

    def __init__(
        self,
        trace: TraceBuffer,
        data_dir: str | Path = "data",
    ) -> None:
        super().__init__(trace)
        self.data_dir: Path = Path(data_dir)

    def _run(self, payload: dict[str, Any]) -> dict[str, Any]:
        opportunity_id: str = str(payload["opportunity_id"])

        opportunities_path: Path = self.data_dir / "salesforce" / "opportunities.tsv"

        contacts_path: Path = self.data_dir / "salesforce" / "contacts.tsv"

        opportunities = pd.read_csv(
            opportunities_path,
            sep="\t",
        )

        matching_opportunities = opportunities[opportunities["opportunity_id"] == opportunity_id]

        if matching_opportunities.empty:
            return {"stakeholders": []}

        account_id: str = str(matching_opportunities.iloc[0]["account_id"])

        contacts = pd.read_csv(
            contacts_path,
            sep="\t",
        )

        account_contacts = contacts[contacts["account_id"] == account_id]

        stakeholders: list[dict[str, Any]] = []

        for _, row in account_contacts.iterrows():
            stakeholders.append(
                {
                    "name": row["full_name"],
                    "title": row["title"],
                    "role_in_deal": row["role_in_deal"],
                    "influence_level": row["influence_level"],
                    "sentiment": row["sentiment"],
                    "notes": row["notes"],
                    "citations": [
                        {
                            "source": ("synthetic_data/salesforce/contacts.tsv"),
                            "stable_source_id": row["contact_id"],
                            "source_type": "salesforce",
                            "quote_or_fact": "Contact row",
                        }
                    ],
                }
            )

        return {
            "stakeholders": stakeholders,
        }
