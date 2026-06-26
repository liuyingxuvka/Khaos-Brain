import json
from pathlib import Path


root = Path.cwd()
contract = json.loads((root / ".skillguard" / "work-contract.json").read_text(encoding="utf-8-sig"))
rules = contract.get("closure_rules") or []
ok = bool(rules) and all(rule.get("required_checks") and rule.get("required_evidence") for rule in rules)
print(json.dumps({"check_id": "check_closure", "decision": "pass" if ok else "fail", "closure_rule_count": len(rules)}))
raise SystemExit(0 if ok else 1)
