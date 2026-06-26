import json
from pathlib import Path


root = Path.cwd()
contract = json.loads((root / ".skillguard" / "work-contract.json").read_text(encoding="utf-8-sig"))
phases = contract.get("phases") or []
phase_ids = [phase.get("phase_id") for phase in phases]
ok = bool(phase_ids) and len(phase_ids) == len(set(phase_ids))
for route in contract.get("routes") or []:
    order = route.get("phase_order") or []
    ok = ok and bool(order) and all(phase_id in phase_ids for phase_id in order)
print(json.dumps({"check_id": "check_phase_order", "decision": "pass" if ok else "fail", "phase_count": len(phases)}))
raise SystemExit(0 if ok else 1)
