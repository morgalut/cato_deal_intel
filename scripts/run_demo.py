import argparse, json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from cato_deal_intel.app.workflows.brief_workflow import BriefWorkflow
from cato_deal_intel.app.security.permissions import PermissionDeniedError

parser = argparse.ArgumentParser()
parser.add_argument("--user", required=True)
parser.add_argument("--opp", required=True)
parser.add_argument("--out", default="artifacts/brief.json")
args = parser.parse_args()
try:
    brief = BriefWorkflow(data_dir=str(ROOT / "data")).run(args.user, args.opp)
except PermissionDeniedError:
    print(
        json.dumps(
            {"status": "denied", "message": "Access denied without leaking restricted metadata."},
            indent=2,
        )
    )
    raise SystemExit(2)
Path(ROOT / args.out).parent.mkdir(parents=True, exist_ok=True)
Path(ROOT / args.out).write_text(json.dumps(brief, indent=2, ensure_ascii=False), encoding="utf-8")
print(
    json.dumps(
        {
            "status": "ok",
            "output": args.out,
            "recommendations": len(brief["recommended_next_actions"]),
            "trace_events": len(brief["trace"]),
        },
        indent=2,
    )
)
