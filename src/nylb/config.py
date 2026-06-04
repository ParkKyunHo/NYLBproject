from __future__ import annotations

import os
from pathlib import Path

import yaml
from dotenv import load_dotenv


def load_settings() -> dict:
    """Read API credentials from .env / environment."""
    load_dotenv()
    return {
        "youtube_api_key": os.getenv("YOUTUBE_API_KEY"),
        "naver_client_id": os.getenv("NAVER_CLIENT_ID"),
        "naver_client_secret": os.getenv("NAVER_CLIENT_SECRET"),
        "instagram_graph_token": os.getenv("INSTAGRAM_GRAPH_TOKEN"),
        "instagram_user_id": os.getenv("INSTAGRAM_USER_ID"),
        "supabase_url": os.getenv("SUPABASE_URL"),
        "supabase_service_key": os.getenv("SUPABASE_SERVICE_ROLE_KEY"),
    }


def load_lenses(path: Path | str = "config/lenses.yaml") -> dict:
    return yaml.safe_load(Path(path).read_text(encoding="utf-8"))


def get_lens_config(lenses: dict, store_id: str, lens: str) -> dict:
    return lenses[store_id]["lenses"][lens]
