"""Tests for documentation consistency with actual code.

Validates that CLAUDE.md, AGENTS.md, development-plan.md, and PRD.md
accurately reflect the current route and database module counts, and
that the manual review (人工抽检) feature status is correct.
"""

from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent


class TestDocRouteConsistency:
    """Verify documentation lists all route modules accurately."""

    def _get_actual_route_files(self) -> list[str]:
        """Return sorted list of actual route .py files (excluding __init__)."""
        routes_dir = PROJECT_ROOT / "dashboard" / "backend" / "routes"
        return sorted(
            f.name for f in routes_dir.glob("*.py") if f.name != "__init__.py"
        )

    def _get_actual_db_files(self) -> list[str]:
        """Return sorted list of actual database .py files (excluding __init__)."""
        db_dir = PROJECT_ROOT / "dashboard" / "backend" / "database"
        return sorted(
            f.name for f in db_dir.glob("*.py") if f.name != "__init__.py"
        )

    def test_actual_route_count(self) -> None:
        """Verify there are 12 route modules."""
        routes = self._get_actual_route_files()
        assert len(routes) == 12, f"Expected 12 route files, got {len(routes)}: {routes}"

    def test_actual_db_module_count(self) -> None:
        """Verify there are 8 database modules."""
        modules = self._get_actual_db_files()
        assert len(modules) == 8, f"Expected 8 db files, got {len(modules)}: {modules}"

    def test_reviews_py_exists_in_routes(self) -> None:
        """Verify reviews.py (manual review) exists in routes."""
        routes = self._get_actual_route_files()
        assert "reviews.py" in routes

    def test_manual_reviews_py_exists_in_database(self) -> None:
        """Verify manual_reviews.py exists in database."""
        modules = self._get_actual_db_files()
        assert "manual_reviews.py" in modules


class TestClaudeMdConsistency:
    """Verify CLAUDE.md reflects actual code structure."""

    @pytest.fixture(autouse=True)
    def _load_claude_md(self) -> None:
        path = PROJECT_ROOT / "CLAUDE.md"
        self.content = path.read_text(encoding="utf-8")

    def test_routes_mention_reviews_py(self) -> None:
        """CLAUDE.md should list reviews.py in routes section."""
        assert "reviews.py" in self.content, (
            "CLAUDE.md is missing reviews.py in route modules list"
        )

    def test_database_mention_manual_reviews_py(self) -> None:
        """CLAUDE.md should list manual_reviews.py in database section."""
        assert "manual_reviews.py" in self.content, (
            "CLAUDE.md is missing manual_reviews.py in database modules list"
        )

    def test_route_count_is_12(self) -> None:
        """CLAUDE.md should reference 12 route modules, not 11."""
        # Check that there's no outdated "11" count for routes
        lines = self.content.split("\n")
        for line in lines:
            if "routes/" in line and "11" in line:
                pytest.fail(f"CLAUDE.md still references 11 routes: {line.strip()}")

    def test_db_module_count_is_8(self) -> None:
        """CLAUDE.md should reference 8 database modules, not 7."""
        lines = self.content.split("\n")
        for line in lines:
            if "database/" in line and "7" in line and "module" in line.lower():
                pytest.fail(f"CLAUDE.md still references 7 database modules: {line.strip()}")


class TestAgentsMdConsistency:
    """Verify AGENTS.md reflects actual code structure."""

    @pytest.fixture(autouse=True)
    def _load_agents_md(self) -> None:
        path = PROJECT_ROOT / "AGENTS.md"
        self.content = path.read_text(encoding="utf-8")

    def test_routes_mention_reviews_py(self) -> None:
        """AGENTS.md should list reviews.py in routes section."""
        assert "reviews.py" in self.content, (
            "AGENTS.md is missing reviews.py in route modules list"
        )

    def test_database_mention_manual_reviews_py(self) -> None:
        """AGENTS.md should list manual_reviews.py in database section."""
        assert "manual_reviews.py" in self.content, (
            "AGENTS.md is missing manual_reviews.py in database modules list"
        )

    def test_route_count_is_12(self) -> None:
        """AGENTS.md should reference 12 route modules, not 11."""
        lines = self.content.split("\n")
        for line in lines:
            if "路由模块" in line and "11" in line:
                pytest.fail(f"AGENTS.md still references 11 routes: {line.strip()}")

    def test_db_module_count_is_8(self) -> None:
        """AGENTS.md should reference 8 database modules, not 7."""
        lines = self.content.split("\n")
        for line in lines:
            if "database" in line.lower() and "7" in line and "模块" in line:
                pytest.fail(f"AGENTS.md still references 7 database modules: {line.strip()}")


class TestDevelopmentPlanConsistency:
    """Verify development-plan.md has correct status for manual review."""

    @pytest.fixture(autouse=True)
    def _load_dev_plan(self) -> None:
        path = PROJECT_ROOT / "docs" / "product" / "development-plan.md"
        self.content = path.read_text(encoding="utf-8")

    def test_manual_review_not_marked_pending(self) -> None:
        """人工抽检 should not be marked as 待实现."""
        lines = self.content.split("\n")
        for line in lines:
            if "人工抽检" in line and "待实现" in line:
                pytest.fail(
                    f"development-plan.md still marks 人工抽检 as 待实现: {line.strip()}"
                )

    def test_manual_review_marked_completed(self) -> None:
        """人工抽检 should be marked as ✅ 已完成."""
        assert "✅ 已完成" in self.content, (
            "development-plan.md should contain at least one ✅ 已完成 entry"
        )
        # Find the line with 人工抽检 and check it says 已完成
        found = False
        for line in self.content.split("\n"):
            if "人工抽检" in line:
                assert "已完成" in line, (
                    f"人工抽检 line should say 已完成: {line.strip()}"
                )
                found = True
                break
        assert found, "development-plan.md should contain 人工抽检 entry"


class TestPrdConsistency:
    """Verify PRD.md mentions manual review is implemented."""

    @pytest.fixture(autouse=True)
    def _load_prd(self) -> None:
        path = PROJECT_ROOT / "docs" / "product" / "PRD.md"
        self.content = path.read_text(encoding="utf-8")

    def test_manual_review_section_exists(self) -> None:
        """PRD.md should have a manual review (人工抽检) section."""
        assert "人工抽检" in self.content, (
            "PRD.md should mention 人工抽检"
        )

    def test_no_pending_status_for_manual_review(self) -> None:
        """PRD.md should not have 人工抽检 marked as 待实现."""
        lines = self.content.split("\n")
        for line in lines:
            if "人工抽检" in line and "待实现" in line:
                pytest.fail(
                    f"PRD.md still marks 人工抽检 as 待实现: {line.strip()}"
                )
