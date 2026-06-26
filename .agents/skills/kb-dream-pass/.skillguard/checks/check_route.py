import json
from pathlib import Path


root = Path.cwd()
contract_path = root / ".skillguard" / "work-contract.json"
contract = json.loads(contract_path.read_text(encoding="utf-8-sig"))
routes = contract.get("routes") or []
decision = "pass" if routes and all(route.get("route_id") for route in routes) else "fail"
print(json.dumps({"check_id": "check_route", "decision": decision, "route_count": len(routes)}))
raise SystemExit(0 if decision == "pass" else 1)
