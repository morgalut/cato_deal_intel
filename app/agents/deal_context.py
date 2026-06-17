from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd
from app.agents.base import AgentBase
from app.core.exceptions import OpportunityNotFoundError
from app.observability.tracing import TraceBuffer


class DealContextAgent(AgentBase):
    name = "deal_context_agent"
    system_contract = (
        "Load deterministic CRM/account context. No LLM needed for raw facts; cite source rows."
    )

    def __init__(self, trace: TraceBuffer, data_dir: str | Path = "data") -> None:
        super().__init__(trace)
        self.data_dir: Path = Path(data_dir)

    def _run(self, payload: dict[str, Any]) -> dict[str, Any]:
        opportunity_id: str = str(payload["opportunity_id"])
        opportunities_path: Path = self.data_dir / "salesforce" / "opportunities.tsv"

        opportunities = pd.read_csv(opportunities_path, sep="\t")
        matching_rows = opportunities[opportunities["opportunity_id"] == opportunity_id]

        if matching_rows.empty:
            raise OpportunityNotFoundError(opportunity_id)

        row: dict[str, Any] = matching_rows.iloc[0].to_dict()

        return {
            "snapshot": {
                "opportunity_id": row["opportunity_id"],
                "account_id": row["account_id"],
                "account_name": row["account_name"],
                "stage": row["stage"],
                "deal_type": row["type"],
                "acv": float(row["acv"]),
                "tcv": float(row["tcv"]),
                "close_date": row["close_date"],
                "owner": row["owner"],
                "risk_level": row["risk_level"],
                "restricted_access": bool(row["restricted_access"]),
                "citations": [
                    {
                        "source": "synthetic_data/salesforce/opportunities.tsv",
                        "stable_source_id": row["opportunity_id"],
                        "source_type": "salesforce",
                        "quote_or_fact": "CRM opportunity row",
                    }
                ],
            }
        }
