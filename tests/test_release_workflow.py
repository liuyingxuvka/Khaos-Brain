from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "tests.yml"


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
