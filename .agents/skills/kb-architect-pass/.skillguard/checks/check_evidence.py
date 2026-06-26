import json
from pathlib import Path


root = Path.cwd()
contract = json.loads((root / ".skillguard" / "work-contract.json").read_text(encoding="utf-8-sig"))
required = contract.get("required_evidence") or []
phase_ids = {phase.get("phase_id") for phase in contract.get("phases") or []}
ok = bool(required) and all(row.get("evidence_id") and row.get("phase_id") in phase_ids for row in required)
print(json.dumps({"check_id": "check_evidence", "decision": "pass" if ok else "fail", "required_evidence_count": len(required)}))
raise SystemExit(0 if ok else 1)
