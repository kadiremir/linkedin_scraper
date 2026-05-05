from pathlib import Path
from types import SimpleNamespace

import pytest

from linkedin_jobs.profiles import default_chrome_user_data_dir, resolve_browser_profile


def test_resolve_browser_profile_uses_dedicated_profile_by_default():
    args = SimpleNamespace(
        profile_dir=Path(".browser-profile"),
        use_default_chrome_profile=False,
        chrome_user_data_dir=None,
        chrome_profile_directory="Default",
    )

    profile = resolve_browser_profile(args)

    assert profile.user_data_dir == Path(".browser-profile")
    assert profile.profile_directory is None


def test_default_chrome_user_data_dir_uses_local_app_data(monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", r"C:\Users\me\AppData\Local")

    assert default_chrome_user_data_dir() == Path(
        r"C:\Users\me\AppData\Local\Google\Chrome\User Data"
    )


def test_profile_directory_requires_chrome_user_data_dir():
    args = SimpleNamespace(
        profile_dir=Path(".browser-profile"),
        use_default_chrome_profile=False,
        chrome_user_data_dir=None,
        chrome_profile_directory="Profile 1",
    )

    with pytest.raises(RuntimeError, match="--chrome-profile-directory requires"):
        resolve_browser_profile(args)


def test_resolve_browser_profile_accepts_existing_chrome_user_data_dir():
    args = SimpleNamespace(
        profile_dir=Path(".browser-profile"),
        use_default_chrome_profile=False,
        chrome_user_data_dir=Path("."),
        chrome_profile_directory="Profile 1",
    )

    profile = resolve_browser_profile(args)

    assert profile.user_data_dir == Path(".")
    assert profile.profile_directory == "Profile 1"
