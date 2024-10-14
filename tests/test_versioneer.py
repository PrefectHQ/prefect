"""Tests custom changes to versioneer.py"""

from versioneer import render_pep440


def test_render_pep440_ignores_dirty():
    """
    Tests that versioneer.py's render_pep440 ignores dirty.
    """
    assert (
        render_pep440(
            {
                "long": "3452196e283815332768b084467cba17d6d40ffa",
                "short": "3452196e28",
                "error": None,
                "branch": "test",
                "dirty": True,
                "closest-tag": "0.0.1",
                "distance": 0,
                "date": "2024-10-12T23:30:05-0500",
            }
        )
        == "0.0.1"
    )


def test_render_pep440_ignores_respects_distance():
    """
    Tests that versioneer.py's render_pep440 still respects distance.
    """
    assert (
        render_pep440(
            {
                "long": "3452196e283815332768b084467cba17d6d40ffa",
                "short": "3452196e28",
                "error": None,
                "branch": "test",
                "dirty": False,
                "closest-tag": "0.0.1",
                "distance": 1,
                "date": "2024-10-12T23:30:05-0500",
            }
        )
        == "0.0.1+1.g3452196e28"
    )
