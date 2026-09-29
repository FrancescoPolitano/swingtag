"""Lambda entry point.

Two event shapes: an SQS batch of S3 notifications (or republish-all messages),
and a direct invocation {"action": "republish_all"}. A batch is reduced to its
distinct item prefixes and each is published once; only the messages of a failed
item are returned for retry.
"""

from __future__ import annotations

import json
import logging
import os
from urllib.parse import unquote_plus

from .catalog import item_prefix
from .publish import Publisher
from .settings import Settings

log = logging.getLogger(__name__)


def configure_logging(level: str | None = None) -> None:
    """The Lambda runtime installs a root handler, so basicConfig would do nothing:
    set the level on the root logger directly."""
    level = (level or os.environ.get("LOG_LEVEL", "INFO")).upper()
    root = logging.getLogger()
    if root.handlers:
        root.setLevel(level)
    else:
        logging.basicConfig(level=level)


configure_logging()

_clients: dict = {}


def _client(name: str):
    if name not in _clients:
        import boto3

        _clients[name] = boto3.client(name)
    return _clients[name]


def make_publisher(settings: Settings | None = None) -> Publisher:
    """A fresh publisher per invocation (so the theme is re-read), reusing the clients."""
    return Publisher(settings or Settings.from_env(), s3=_client("s3"),
                     cloudfront=_client("cloudfront"), sqs=_client("sqs"))


def keys_from_body(body: str) -> list[str]:
    """Object keys in one queue message; test events and garbage give no keys."""
    try:
        payload = json.loads(body)
    except (TypeError, ValueError):
        log.warning("message body is not JSON, skipped")
        return []
    if not isinstance(payload, dict) or payload.get("Event") == "s3:TestEvent":
        return []
    keys = []
    for record in payload.get("Records", []):
        raw = record.get("s3", {}).get("object", {}).get("key")
        if raw:
            keys.append(unquote_plus(raw))  # S3 keys arrive URL-encoded
    return keys


def handle(event: dict, publisher: Publisher) -> dict:
    if event.get("action") == "republish_all":
        publisher.publish_error_page()
        return {"items": publisher.republish_all()}

    source_prefix = publisher.settings.source_prefix
    targets: dict[str, list[str]] = {}
    for record in event.get("Records", []):
        message_id = record.get("messageId", "")
        for key in keys_from_body(record.get("body", "")):
            prefix = item_prefix(source_prefix, key)
            if prefix is None:
                log.warning("anomaly on %s: key outside convention: %s", source_prefix, key)
                continue
            targets.setdefault(prefix, []).append(message_id)

    failures: list[str] = []
    for prefix, message_ids in targets.items():
        try:
            publisher.publish(prefix)
        except Exception:  # noqa: BLE001 - the messages go back to the queue
            log.exception("publication failed for %s", prefix)
            failures.extend(message_ids)
    return {"batchItemFailures": [{"itemIdentifier": m} for m in dict.fromkeys(failures) if m]}


def lambda_handler(event: dict, context=None) -> dict:
    return handle(event, make_publisher())
