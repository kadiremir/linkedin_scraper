import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class BrowserProfileConfig:
    user_data_dir: Path
    profile_directory: str | None


def resolve_browser_profile(args) -> BrowserProfileConfig:
    if args.chrome_profile_directory != "Default" and not (
        args.use_default_chrome_profile or args.chrome_user_data_dir
    ):
        raise RuntimeError(
            "--chrome-profile-directory requires --use-default-chrome-profile "
            "or --chrome-user-data-dir."
        )

    if args.use_default_chrome_profile or args.chrome_user_data_dir:
        user_data_dir = args.chrome_user_data_dir or default_chrome_user_data_dir()
        if not user_data_dir.exists():
            raise RuntimeError(f"Chrome user data directory does not exist: {user_data_dir}")

        return BrowserProfileConfig(
            user_data_dir=user_data_dir,
            profile_directory=args.chrome_profile_directory,
        )

    return BrowserProfileConfig(
        user_data_dir=args.profile_dir,
        profile_directory=None,
    )


def default_chrome_user_data_dir() -> Path:
    local_app_data = os.environ.get("LOCALAPPDATA")
    if not local_app_data:
        raise RuntimeError(
            "LOCALAPPDATA is not set. Pass --chrome-user-data-dir explicitly."
        )
    return Path(local_app_data) / "Google" / "Chrome" / "User Data"
