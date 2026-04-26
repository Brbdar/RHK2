from __future__ import annotations

import rhk_regression_tests as regression_suite


def test_regression_suite_smoke() -> None:
    """Run legacy regression suite inside pytest/CI."""
    regression_suite.main()
