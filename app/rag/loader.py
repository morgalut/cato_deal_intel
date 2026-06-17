from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

import pandas as pd
from app.observability.logging import get_logger, log_stage
from pandas import Series

logger = get_logger("rag.loader")

AddEvidenceDocument = Callable[
    [
        str,
        str,
        str,
        str | None,
        str | None,
        str | None,
        str,
        dict[str, Any] | None,
    ],
    None,
]


class EvidenceLoader:
    """Adapter for converting exam TSV/MD files into normalized evidence documents.

    Design pattern: Adapter. Each source has a different shape, but agents only
    receive normalized evidence docs with stable IDs, metadata, source type,
    access level, and content.
    """

    def __init__(self, data_dir: str = "data") -> None:
        self.data_dir: Path = Path(data_dir)

    def load_documents(self) -> list[dict[str, Any]]:
        with log_stage(
            logger,
            "evidence.load_documents",
            data_dir=str(self.data_dir),
        ):
            docs: list[dict[str, Any]] = []

            def add(
                stable_id: str,
                source_file: str,
                source_type: str,
                opportunity_id: str | None,
                account_id: str | None,
                access: str | None,
                content: str,
                metadata: dict[str, Any] | None = None,
            ) -> None:
                docs.append(
                    {
                        "stable_source_id": str(stable_id),
                        "source_file": source_file,
                        "source_type": source_type,
                        "opportunity_id": (None if pd.isna(opportunity_id) else opportunity_id),
                        "account_id": None if pd.isna(account_id) else account_id,
                        "source_access_level": access or "standard",
                        "sensitivity": access or "standard",
                        "content": str(content),
                        "metadata": metadata or {},
                    }
                )

            self._load_salesforce(add)
            self._load_gong(add)
            self._load_pricing(add)
            self._load_policy(add)
            self._load_slack(add)

            logger.info(
                "evidence.load.complete",
                documents=len(docs),
                source_types=sorted({str(doc["source_type"]) for doc in docs}),
            )

            return docs

    def _load_salesforce(self, add: AddEvidenceDocument) -> None:
        for relative_path in [
            "salesforce/accounts.tsv",
            "salesforce/opportunities.tsv",
            "salesforce/contacts.tsv",
        ]:
            data = pd.read_csv(
                self.data_dir / relative_path,
                sep="\t",
            )

            logger.info(
                "evidence.load.file",
                file=relative_path,
                rows=len(data),
            )

            for _, raw_row in data.iterrows():
                row: Series[Any] = raw_row
                opportunity_id = row.get("opportunity_id", None)
                account_id = row.get("account_id", None)
                stable_id = str(
                    row.get(
                        "opportunity_id",
                        row.get(
                            "account_id",
                            row.get("contact_id", relative_path),
                        ),
                    )
                )

                add(
                    stable_id,
                    f"synthetic_data/{relative_path}",
                    "salesforce",
                    opportunity_id,
                    account_id,
                    "standard",
                    row.to_json(force_ascii=False),
                    row.to_dict(),
                )

    def _load_gong(self, add: AddEvidenceDocument) -> None:
        gong_path: Path = self.data_dir / "gong/gong_call_summaries.tsv"

        gong = pd.read_csv(
            gong_path,
            sep="\t",
        )

        logger.info(
            "evidence.load.file",
            file="gong/gong_call_summaries.tsv",
            rows=len(gong),
        )

        for _, raw_row in gong.iterrows():
            row: Series[Any] = raw_row

            content: str = (
                f"{row.title}\n"
                f"{row.summary}\n"
                f"Key points: {row.key_points}\n"
                f"Risks: {row.risks}\n"
                f"Next: {row.next_steps}"
            )

            add(
                row.call_id,
                "synthetic_data/gong/gong_call_summaries.tsv",
                "gong",
                row.opportunity_id,
                row.account_id,
                row.source_access_level,
                content,
                row.to_dict(),
            )

        transcript_paths = list((self.data_dir / "gong/transcripts").glob("*.md"))

        for transcript_path in transcript_paths:
            text: str = transcript_path.read_text(
                encoding="utf-8",
            )

            opportunity_id = transcript_path.name.split("_")[0]
            call_id = transcript_path.stem.split("_")[1]
            access = "standard"

            for line in text.splitlines():
                if line.lower().startswith("**source access level:**"):
                    access = line.split(":", 1)[1].strip()

            rows = gong[gong.call_id == call_id]
            account_id = rows.iloc[0].account_id if not rows.empty else None

            add(
                call_id,
                f"synthetic_data/gong/transcripts/{transcript_path.name}",
                "gong",
                opportunity_id,
                account_id,
                access,
                text,
                {"call_id": call_id},
            )

        logger.info(
            "evidence.load.file",
            file="gong/transcripts/*.md",
            rows=len(transcript_paths),
        )

    def _load_pricing(self, add: AddEvidenceDocument) -> None:
        pricing = pd.read_csv(
            self.data_dir / "pricing/pricing_notes.tsv",
            sep="\t",
        )

        opportunities = pd.read_csv(
            self.data_dir / "salesforce/opportunities.tsv",
            sep="\t",
        )

        logger.info(
            "evidence.load.file",
            file="pricing/pricing_notes.tsv",
            rows=len(pricing),
        )

        for _, raw_row in pricing.iterrows():
            row: Series[Any] = raw_row
            opportunity = opportunities[opportunities.opportunity_id == row.opportunity_id].iloc[0]

            access = (
                "sensitive_pricing"
                if bool(opportunity.restricted_access) or row.requested_discount > 10
                else "standard"
            )

            add(
                row.pricing_note_id,
                "synthetic_data/pricing/pricing_notes.tsv",
                "pricing",
                row.opportunity_id,
                opportunity.account_id,
                access,
                row.to_json(force_ascii=False),
                row.to_dict(),
            )

    def _load_policy(self, add: AddEvidenceDocument) -> None:
        policy = (self.data_dir / "policies/deal_desk_policy.md").read_text(encoding="utf-8")

        add(
            "DEAL-DESK-POLICY",
            "synthetic_data/policies/deal_desk_policy.md",
            "policies",
            None,
            None,
            "standard",
            policy,
            {},
        )

    def _load_slack(self, add: AddEvidenceDocument) -> None:
        slack = pd.read_csv(
            self.data_dir / "slack/account_team_updates.tsv",
            sep="\t",
        )

        logger.info(
            "evidence.load.file",
            file="slack/account_team_updates.tsv",
            rows=len(slack),
        )

        for _, raw_row in slack.iterrows():
            row: Series[Any] = raw_row

            add(
                row.update_id,
                "synthetic_data/slack/account_team_updates.tsv",
                "slack",
                row.opportunity_id,
                row.account_id,
                row.source_access_level,
                row.update_text,
                row.to_dict(),
            )
