import json
from pathlib import Path


root = Path.cwd()
contract_path = root / ".skillguard" / "work-contract.json"
contract = json.loads(contract_path.read_text(encoding="utf-8-sig"))
routes = contract.get("routes") or []
failures = []
if not routes or not all(route.get("route_id") for route in routes):
    failures.append("missing_route_id")
mode = contract.get("integration_mode")
if mode not in {"native-integrated", "hybrid-extension", "skillguard-runtime"}:
    failures.append("invalid_integration_mode")
if contract.get("may_define_parallel_execution_route") is not False:
    failures.append("duplicate_skillguard_execution_paths_not_forbidden")
expected_role = {
    "native-integrated": "native_contract_executor",
    "hybrid-extension": "hybrid_contract_executor",
    "skillguard-runtime": "runtime_owner",
}.get(mode)
if contract.get("skillguard_role") != expected_role:
    failures.append("wrong_skillguard_role_for_integration_mode")
if mode in {"native-integrated", "hybrid-extension"}:
    if not contract.get("native_route_owner"):
        failures.append("missing_native_route_owner")
    if contract.get("may_define_skillguard_runtime_route") is not False:
        failures.append("skillguard_runtime_route_not_forbidden")
    if not contract.get("native_route_bindings"):
        failures.append("missing_native_route_bindings")
    if not contract.get("native_check_bindings"):
        failures.append("missing_native_check_bindings")
    boundary = str(contract.get("integration_claim_boundary") or "").lower()
    if "duplicate skillguard-owned execution paths are invalid" not in boundary:
        failures.append("integration_boundary_missing_duplicate_path_block")
if mode == "skillguard-runtime":
    if contract.get("may_define_skillguard_runtime_route") is not True:
        failures.append("skillguard_runtime_route_not_enabled_for_runtime_owner")
for route in routes:
    route_id = route.get("route_id", "<missing>")
    if mode == "native-integrated" and route.get("route_source") != "native_binding":
        failures.append(f"{route_id}:route_source_not_native_binding")
    if mode == "hybrid-extension" and route.get("route_source") not in {"native_binding", "hybrid_extension"}:
        failures.append(f"{route_id}:route_source_not_hybrid_or_native")
    if mode == "skillguard-runtime" and route.get("route_source") != "skillguard_runtime":
        failures.append(f"{route_id}:route_source_not_skillguard_runtime")
    summary = str(route.get("summary") or "").lower()
    if mode in {"native-integrated", "hybrid-extension"} and "duplicate skillguard-owned execution paths are invalid" not in summary and "without replacing" not in summary:
        failures.append(f"{route_id}:summary_missing_native_attachment_boundary")
decision = "pass" if not failures else "fail"
print(json.dumps({"check_id": "check_route", "decision": decision, "route_count": len(routes), "failures": failures}))
raise SystemExit(0 if decision == "pass" else 1)
