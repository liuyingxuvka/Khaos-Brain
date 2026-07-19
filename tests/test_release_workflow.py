from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "tests.yml"
REQUIREMENTS = REPO_ROOT / "requirements.txt"
DEV_REQUIREMENTS = REPO_ROOT / "requirements-dev.txt"


def test_tag_ci_consumes_exact_main_receipt_without_rerunning_install() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    required_in_order = (
        "tag-release-receipt:",
        "name: Verify tag release receipt",
        "if: ${{ startsWith(github.ref, 'refs/tags/') }}",
        'test "$(git rev-parse HEAD)" = "$GITHUB_SHA"',
        "git fetch --no-tags --depth=1 origin main",
        'test "$(git rev-parse origin/main)" = "$GITHUB_SHA"',
        'gh api --method GET "repos/$GITHUB_REPOSITORY/actions/runs"',
        'run.get("head_branch") == "main"',
        'run.get("head_sha") == sha',
        'run.get("conclusion") == "success"',
    )

    positions = [text.index(fragment) for fragment in required_in_order]
    assert positions == sorted(positions)
    tag_job = text.split("  tag-release-receipt:", 1)[1]
    assert "Install Codex KB integration" not in tag_job
    assert "git checkout -B main" not in tag_job


def test_full_validation_job_never_runs_for_a_tag() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    full_job = text.split("  python-tests:", 1)[1].split(
        "  tag-release-receipt:", 1
    )[0]

    assert "if: ${{ ! startsWith(github.ref, 'refs/tags/') }}" in full_job
    assert "Install Codex KB integration" in full_job


def test_researchguard_dependency_uses_one_public_pinned_path() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")
    requirements = REQUIREMENTS.read_text(encoding="utf-8")
    full_job = workflow.split("  python-tests:", 1)[1].split(
        "  tag-release-receipt:", 1
    )[0]
    pinned_dependency = (
        "researchguard @ "
        "git+https://github.com/liuyingxuvka/ResearchGuard.git"
        "@31daa62268e2d57ae61e9833a0686a6c612e4cfc"
    )

    assert pinned_dependency in requirements
    assert "github.com/liuyingxuvka/LogicGuard.git" not in requirements
    assert "git+ssh" not in requirements
    assert "LOGICGUARD_DEPLOY_KEY" not in workflow
    assert "Configure read-only LogicGuard deploy key" not in full_job
    assert "GH_TOKEN" not in full_job
    assert "github.token" not in full_job


def test_ci_pins_final_flowguard_validation_commit() -> None:
    requirements = DEV_REQUIREMENTS.read_text(encoding="utf-8")

    assert (
        "flowguard @ "
        "git+https://github.com/liuyingxuvka/FlowGuard.git"
        "@7c2046bfb0a5ad458deefcbb4edbf8f3b90b7dc3"
    ) in requirements
