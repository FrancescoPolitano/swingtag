"""Configuration of the publisher from the Lambda environment."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass


def _prefix(value: str) -> str:
    return value.strip().strip("/") + "/"


@dataclass(frozen=True)
class Settings:
    bucket: str
    source_prefix: str
    public_prefix: str
    config_key: str
    public_base_url: str
    distribution_id: str
    queue_url: str
    token_secret: str

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> "Settings":
        env = os.environ if env is None else env

        def required(name: str) -> str:
            value = env.get(name, "").strip()
            if not value:
                raise RuntimeError(f"missing environment variable: {name}")
            return value

        return cls(
            bucket=required("BUCKET"),
            source_prefix=_prefix(env.get("SOURCE_PREFIX", "source")),
            public_prefix=_prefix(env.get("PUBLIC_PREFIX", "public")),
            config_key=env.get("CONFIG_KEY", "config/theme.json").strip().lstrip("/"),
            public_base_url=required("PUBLIC_BASE_URL").rstrip("/"),
            distribution_id=env.get("DISTRIBUTION_ID", "").strip(),
            queue_url=env.get("QUEUE_URL", "").strip(),
            token_secret=required("TOKEN_SECRET"),
        )
