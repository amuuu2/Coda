from __future__ import annotations

import pytest

from yuxi_cli.discovery import ServerCompatibilityError, ensure_server_compatible, is_server_version_supported


@pytest.mark.parametrize(
    ("version", "expected"),
    [
        ("0.1.1", True),
        ("0.1.1.post1", True),
        ("0.1.1.dev0", True),
        ("0.1.0", False),
        ("0.1.0.dev99", False),
        ("0.1.1rc1", False),
        ("0.7.1", True),
        ("0.7.2", True),
        ("unknown", False),
    ],
)
def test_is_server_version_supported_handles_dev_releases(version, expected):
    assert is_server_version_supported(version) is expected


def test_ensure_server_compatible_requires_capability():
    discovery = {
        "version": "0.1.1",
        "capabilities": {
            "cli": {
                "browser_login": False,
                "api_key_auth": True,
            }
        },
    }

    with pytest.raises(ServerCompatibilityError, match="cli.browser_login"):
        ensure_server_compatible(discovery, "cli.browser_login")
