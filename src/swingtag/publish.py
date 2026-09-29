"""The publisher: compiles one item of the source zone into the public zone.

The only module, with handler.py, that talks to AWS. Clients are injected so the
algorithm runs against stubs in the unit tests.
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
import unicodedata
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from urllib.parse import quote_plus

from botocore.exceptions import ClientError

from . import convention, formats, theme as theme_module
from .catalog import MAX_COPY_BYTES, Item, SourceObject, build_item, published_keys, split_prefix
from .qr import qr_svg
from .render import render_not_found, render_page
from .settings import Settings

log = logging.getLogger(__name__)

INDEX_CACHE = "public, max-age=60"
RESOURCE_CACHE = "public, max-age=300"
_DELETE_BATCH = 1000
_REPUBLISH_MARKER = "_republish"  # placeholder file name in synthetic republish-all events
PRUNE_TOLERANCE = timedelta(seconds=1)  # S3 LastModified has whole seconds; small clock drift
SOURCE_ETAG = "source-etag"  # metadata key on public copies


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def ascii_filename(filename: str, extension: str) -> str:
    """ASCII form of a file name for Content-Disposition."""
    printable = "".join(ch for ch in filename if unicodedata.category(ch) != "Cc")
    translated = printable.translate(convention.TRANSLITERATION)
    ascii_only = unicodedata.normalize("NFKD", translated).encode("ascii", "ignore").decode("ascii")
    cleaned = ascii_only.replace('"', "").replace("\\", "").strip()
    stem = cleaned[: -len(extension)] if cleaned.lower().endswith(extension) else cleaned
    return cleaned if stem.strip(" .") else f"file{extension}"


class Publisher:
    def __init__(self, settings: Settings, s3, cloudfront=None, sqs=None,
                 clock: Callable[[], datetime] = _utcnow):
        self.settings = settings
        self.s3 = s3
        self.cloudfront = cloudfront
        self.sqs = sqs
        self.clock = clock
        self._theme: theme_module.Theme | None = None

    # ------------------------------------------------------------------ theme

    def theme(self) -> theme_module.Theme:
        """The deployment theme, read once per Publisher (one per invocation)."""
        if self._theme is None:
            try:
                body = self.s3.get_object(Bucket=self.settings.bucket, Key=self.settings.config_key)["Body"].read()
                self._theme = theme_module.from_json(body)
            except ClientError as exc:
                log.warning("theme: cannot read %s (%s), using the default theme",
                            self.settings.config_key, exc.response["Error"]["Code"])
                self._theme = theme_module.DEFAULT_THEME
        return self._theme

    # ------------------------------------------------------------------ listings

    def list_prefix(self, prefix: str) -> list[SourceObject]:
        objects = []
        paginator = self.s3.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=self.settings.bucket, Prefix=prefix):
            for entry in page.get("Contents", []):
                objects.append(SourceObject(key=entry["Key"], etag=entry["ETag"].strip('"'),
                                            size=entry["Size"], modified=entry["LastModified"]))
        return objects

    def common_prefixes(self, prefix: str) -> list[str]:
        found = []
        paginator = self.s3.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=self.settings.bucket, Prefix=prefix, Delimiter="/"):
            found.extend(p["Prefix"] for p in page.get("CommonPrefixes", []))
        return found

    def content(self, prefix: str, objects: list[SourceObject]) -> list[SourceObject]:
        """Objects that count as content: no folder placeholders, no ignored names (step 1)."""
        kept = []
        for obj in objects:
            relative = obj.key[len(prefix):]
            if not relative or relative.endswith("/"):
                continue
            if any(convention.is_ignored(part) for part in relative.split("/")):
                continue
            kept.append(obj)
        return kept

    def _ignored(self, prefix: str) -> bool:
        """True for items whose collection or folder name is ignored."""
        collection, folder = split_prefix(self.settings.source_prefix, prefix)
        return convention.is_ignored(collection) or convention.is_ignored(folder)

    def item_prefixes(self) -> list[str]:
        """Every item prefix under the source zone (collections, then items), ignored names skipped."""
        items = []
        for collection in self.common_prefixes(self.settings.source_prefix):
            items.extend(p for p in self.common_prefixes(collection) if not self._ignored(p))
        return items

    def token_owners(self, token: str, collection_prefix: str | None = None) -> list[str]:
        """Item prefixes carrying `token` that are not ignored and hold content (step 4),
        ordered by NFC form then raw bytes; the given collection is searched first."""
        collections = self.common_prefixes(self.settings.source_prefix)
        if collection_prefix in collections:
            collections.remove(collection_prefix)
            collections.insert(0, collection_prefix)
        owners = []
        for collection in collections:
            for prefix in self.common_prefixes(collection):
                _, folder = split_prefix(self.settings.source_prefix, prefix)
                if convention.split_item_name(folder)[1] != token or self._ignored(prefix):
                    continue
                if self.content(prefix, self.list_prefix(prefix)):
                    owners.append(prefix)
        # Raw prefixes (keys uploaded from macOS may be NFD), NFC form first, then bytes.
        return sorted(owners, key=lambda p: (convention.normalize(p), p))

    # ------------------------------------------------------------------ writes

    def _etag(self, key: str) -> str | None:
        try:
            return self.s3.head_object(Bucket=self.settings.bucket, Key=key)["ETag"].strip('"')
        except ClientError as exc:
            if exc.response["Error"]["Code"] in ("404", "NoSuchKey", "NotFound"):
                return None
            raise

    def _put_if_changed(self, key: str, body: bytes, content_type: str, cache: str) -> bool:
        if self._etag(key) == hashlib.md5(body).hexdigest():
            return False
        self.s3.put_object(Bucket=self.settings.bucket, Key=key, Body=body,
                           ContentType=content_type, CacheControl=cache)
        return True

    def _source_etag(self, key: str) -> str | None:
        try:
            head = self.s3.head_object(Bucket=self.settings.bucket, Key=key)
        except ClientError as exc:
            if exc.response["Error"]["Code"] in ("404", "NoSuchKey", "NotFound"):
                return None
            raise
        return head.get("Metadata", {}).get(SOURCE_ETAG)

    def _delete(self, keys: list[str]) -> None:
        for start in range(0, len(keys), _DELETE_BATCH):
            chunk = keys[start:start + _DELETE_BATCH]
            response = self.s3.delete_objects(Bucket=self.settings.bucket,
                                              Delete={"Objects": [{"Key": k} for k in chunk], "Quiet": True})
            errors = response.get("Errors", [])
            if errors:  # a 200 response can still list per-key failures
                raise RuntimeError("delete failed: " + ", ".join(f"{e['Key']} ({e.get('Code')})" for e in errors))

    def invalidate(self, paths: list[str]) -> None:
        """Best effort: a failed invalidation is logged, never raised."""
        if not self.settings.distribution_id or self.cloudfront is None:
            return
        try:
            self.cloudfront.create_invalidation(
                DistributionId=self.settings.distribution_id,
                InvalidationBatch={"Paths": {"Quantity": len(paths), "Items": paths},
                                   "CallerReference": f"publish-{time.time_ns()}"},
            )
        except Exception as exc:  # noqa: BLE001 - the publication itself succeeded
            log.warning("invalidation of %s failed: %s", paths, exc)

    # ------------------------------------------------------------------ steps

    def christen(self, prefix: str, objects: list[SourceObject], collection: str, label: str) -> str:
        """Move an untokenised item folder to `{label} · {token}`; returns the new prefix."""
        token = convention.token_for(collection, label, self.settings.token_secret)
        parent = prefix[: prefix.rstrip("/").rfind("/") + 1]
        new_prefix = f"{parent}{convention.with_token(label, token)}/"
        for obj in objects:
            destination = new_prefix + obj.key[len(prefix):]
            source = {"Bucket": self.settings.bucket, "Key": obj.key}
            try:
                if obj.size > MAX_COPY_BYTES:
                    self.s3.copy(source, self.settings.bucket, destination)  # managed multipart copy
                else:
                    self.s3.copy_object(Bucket=self.settings.bucket, Key=destination, CopySource=source)
            except ClientError as exc:
                if exc.response["Error"]["Code"] not in ("NoSuchKey", "404"):
                    raise
                # A concurrent run christened the same folder first and already moved
                # this object to the same derived destination.
                log.info("christening %s: %s already moved by a concurrent run", prefix, obj.key)
        self._delete([obj.key for obj in objects])
        log.info("christened %s as %s", prefix, new_prefix)
        return new_prefix

    def remove_publication(self, token: str) -> None:
        keys = [o.key for o in self.list_prefix(f"{self.settings.public_prefix}{token}/")]
        self._delete(keys)
        if keys:
            self.invalidate([f"/{token}*"])
        log.info("publication %s removed (%d objects)", token, len(keys))

    def _link_bodies(self, prefix: str, objects: list[SourceObject]) -> dict[str, bytes]:
        """Bodies of the link files that can become buttons (entry level, not ignored, small)."""
        bodies = {}
        for obj in self.content(prefix, objects):
            if len(obj.key[len(prefix):].split("/")) != 2:
                continue
            fmt = formats.lookup(obj.key.rsplit("/", 1)[-1])
            if fmt is not None and fmt.kind == "link" and obj.size <= formats.MAX_LINK_BYTES:
                bodies[obj.key] = self.s3.get_object(Bucket=self.settings.bucket, Key=obj.key)["Body"].read()
        return bodies

    def _copy_resources(self, item: Item) -> int:
        copied = 0
        for button in item.buttons:
            if button.public_key is None:
                continue  # links are not copied
            if self._source_etag(button.public_key) == button.etag:
                continue
            extension = button.public_key[button.public_key.rfind("."):]
            self.s3.copy_object(
                Bucket=self.settings.bucket, Key=button.public_key,
                CopySource={"Bucket": self.settings.bucket, "Key": button.source_key},
                MetadataDirective="REPLACE", TaggingDirective="REPLACE", ContentType=button.content_type,
                ContentDisposition=f'inline; filename="{ascii_filename(button.filename, extension)}"',
                CacheControl=RESOURCE_CACHE, Metadata={SOURCE_ETAG: button.etag},
            )
            copied += 1
        return copied

    def _prune(self, token: str, keep: set[str], since: datetime) -> int:
        # Spare writes from the run's own second onwards (S3 truncates LastModified), with
        # one extra second of tolerance for clock drift.
        limit = since.replace(microsecond=0) - PRUNE_TOLERANCE
        stale = [o.key for o in self.list_prefix(f"{self.settings.public_prefix}{token}/")
                 if o.key not in keep and (o.modified is None or o.modified < limit)]
        self._delete(stale)
        return len(stale)

    # ------------------------------------------------------------------ publish

    def publish(self, prefix: str, _visited: frozenset[str] = frozenset()) -> Item:
        """Publish one item prefix. Returns the model that was published.

        `_visited` holds the prefixes already tried in this call chain: steps 2 and 6 can
        hand over to another owner of the token, and two owners must never bounce."""
        started = self.clock()
        src = self.settings.source_prefix
        visited = _visited | {prefix}
        collection, folder = split_prefix(src, prefix)
        label, token = convention.split_item_name(folder)

        # Step 0: ignored names are never published.
        if self._ignored(prefix):
            log.info("%s is under an ignored name: nothing to do", prefix)
            return Item(collection=collection, label=label, token="")

        # Steps 1-2: without content, an untokenised folder waits; a tokenised one hands over
        # to another owner of its token or is unpublished.
        objects = self.list_prefix(prefix)
        collection_prefix = prefix[: prefix.rstrip("/").rfind("/") + 1]
        if not self.content(prefix, objects):
            if token is None:
                log.info("%s has no content and no token: nothing to do", prefix)
                return Item(collection=collection, label=label, token="")
            return self._hand_over_or_remove(prefix, token, collection_prefix, visited,
                                             Item(collection=collection, label=label, token=token))

        # Step 3: christening.
        if token is None:
            prefix = self.christen(prefix, objects, collection, label)
            visited = visited | {prefix}
            objects = self.list_prefix(prefix)
            collection, folder = split_prefix(src, prefix)
            label, token = convention.split_item_name(folder)

        # Step 4: another owner that sorts first keeps the token.
        owners = self.token_owners(token, collection_prefix)
        if owners and owners[0] != prefix:
            log.warning("anomaly on %s: duplicate token: %s is published from %s", prefix, token, owners[0])
            return Item(collection=collection, label=label, token=token)

        # Steps 5-6: model.
        item = build_item(src, self.settings.public_prefix, prefix, objects, self._link_bodies(prefix, objects))
        for anomaly in item.anomalies:
            log.warning("anomaly on %s: %s", prefix, anomaly)
        if item.empty:
            log.info("%s has no valid resource", prefix)
            return self._hand_over_or_remove(prefix, token, collection_prefix, visited, item)

        # Steps 7-11: copy, page, QR code, prune, invalidate when something changed.
        changed = self._copy_resources(item)
        theme = self.theme()
        base = f"{self.settings.public_prefix}{token}/"
        changed += self._put_if_changed(f"{base}index.html", render_page(item, theme).encode("utf-8"),
                                        "text/html; charset=utf-8", INDEX_CACHE)
        changed += self._put_if_changed(f"{base}qr.svg", qr_svg(f"{self.settings.public_base_url}/{token}"),
                                        "image/svg+xml", RESOURCE_CACHE)
        changed += self._prune(token, published_keys(self.settings.public_prefix, item), since=started)
        if changed:
            self.invalidate([f"/{token}*"])
        log.info("published %s as %s (%d buttons, %d writes)", prefix, token, len(item.buttons), changed)
        return item

    def _hand_over_or_remove(self, prefix: str, token: str, collection_prefix: str,
                             visited: frozenset[str], item: Item) -> Item:
        """Publish another owner of the token if one exists (rename, move), else unpublish."""
        others = [o for o in self.token_owners(token, collection_prefix) if o not in visited]
        if others:
            log.info("%s: token %s now lives in %s", prefix, token, others[0])
            return self.publish(others[0], visited)
        self.remove_publication(token)
        return item

    # ------------------------------------------------------------------ site-wide

    def publish_error_page(self) -> None:
        self._put_if_changed(f"{self.settings.public_prefix}404.html",
                             render_not_found(self.theme()).encode("utf-8"),
                             "text/html; charset=utf-8", INDEX_CACHE)

    def republish_all(self) -> int:
        """Enqueue one message per item; returns the number of items."""
        prefixes = self.item_prefixes()
        for start in range(0, len(prefixes), 10):
            entries = []
            for offset, prefix in enumerate(prefixes[start:start + 10]):
                key = quote_plus(prefix + _REPUBLISH_MARKER, safe="/")
                body = {"Records": [{"eventName": "Republish", "s3": {"object": {"key": key}}}]}
                entries.append({"Id": str(offset), "MessageBody": json.dumps(body)})
            response = self.sqs.send_message_batch(QueueUrl=self.settings.queue_url, Entries=entries)
            failed = response.get("Failed", [])
            if failed:  # a 200 response can still list failed entries
                ids = {e["Id"] for e in failed}
                rejected = [prefixes[start + int(e["Id"])] for e in entries if e["Id"] in ids]
                raise RuntimeError(f"republish-all: SQS rejected {len(failed)} messages: {rejected}")
        self.invalidate(["/404.html", "/_assets/*"])
        log.info("republish-all enqueued %d items", len(prefixes))
        return len(prefixes)
