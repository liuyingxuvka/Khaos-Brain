import json
from pathlib import Path


root = Path.cwd()
contract = json.loads((root / ".skillguard" / "work-contract.json").read_text(encoding="utf-8-sig"))
floors = contract.get("quality_floors") or []
shortcuts = contract.get("forbidden_shortcuts") or []
ok = bool(floors) and bool(shortcuts)
print(json.dumps({"check_id": "check_quality_floor", "decision": "pass" if ok else "fail", "quality_floor_count": len(floors)}))
raise SystemExit(0 if ok else 1)
