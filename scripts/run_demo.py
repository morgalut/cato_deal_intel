from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from app.dependencies.container import get_brief_workflow
from app.security.permissions import PermissionDeniedError


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate a Strategic Deal Intelligence Brief.",
    )
    parser.add_argument("--user", required=True)
    parser.add_argument("--opp", required=True)
    parser.add_argument("--out", default="artifacts/brief.json")
    return parser.parse_args()


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )
    path.write_text(
        json.dumps(
            payload,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def main() -> int:
    args = parse_args()
    output_path = Path(args.out)

    try:
        result: dict[str, Any] = get_brief_workflow().run(
            args.user,
            args.opp,
        )

    except PermissionDeniedError as exc:
        denied_payload: dict[str, Any] = {
            "status": "denied",
            "reason": exc.reason,
            "message": "Access denied without leaking restricted metadata.",
        }

        print(
            json.dumps(
                denied_payload,
                indent=2,
                ensure_ascii=False,
            )
        )

        return 2

    write_json(
        output_path,
        result,
    )

    brief: dict[str, Any] = result["brief"]

    print(
        json.dumps(
            {
                "status": "ok",
                "output": str(output_path),
                "recommendations": len(brief["recommended_next_actions"]),
                "trace_events": len(brief["trace"]),
            },
            indent=2,
            ensure_ascii=False,
        )
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
