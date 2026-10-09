"""Settings, read from environment variables or a .env file. All settings are optional."""

from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv


@dataclass
class Settings:
    api_key: str | None = None      # enables written answers from Claude
    model: str = "claude-sonnet-5-5"

    @classmethod
    def from_env(cls) -> "Settings":
        load_dotenv()
        return cls(
            api_key=os.getenv("ANTHROPIC_API_KEY") or None,
            model=os.getenv("ONBOARD_MODEL", cls.model),
        )
