from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "tests.yml"


def test_tag_ci_materializes_main_only_for_the_exact_main_sha() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    required_in_order = (
        "if: startsWith(github.ref, 'refs/tags/')",
        'test "$(git rev-parse HEAD)" = "$GITHUB_SHA"',
        "git fetch --no-tags --depth=1 origin main",
        'test "$(git rev-parse origin/main)" = "$GITHUB_SHA"',
        'git checkout -B main "$GITHUB_SHA"',
        "git branch --set-upstream-to=origin/main main",
        'test "$(git rev-parse HEAD)" = "$(git rev-parse origin/main)"',
    )

    positions = [text.index(fragment) for fragment in required_in_order]
    assert positions == sorted(positions)
