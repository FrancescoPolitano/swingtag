"""Hand-written stand-ins for the S3, CloudFront and SQS clients.

They keep objects in memory and record calls. Behaviour copied from the real
services where the publisher depends on it: ETag is the MD5 of the body and is
preserved by copy_object for single-part sources but not for multipart
ones, custom metadata survives a REPLACE copy, CopyObject refuses sources
over 5 GiB, LastModified is truncated to the second, listings are paginated and
support Delimiter, missing keys raise botocore's ClientError with code NoSuchKey
or 404, and batch APIs report per-entry failures inside a successful response.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone

from botocore.exceptions import ClientError

FIVE_GIB = 5 * 1024**3


def _missing(operation, code="NoSuchKey"):
    return ClientError({"Error": {"Code": code, "Message": "Not Found"}}, operation)


class Clock:
    """A settable clock; every call advances by one second so writes are ordered."""

    def __init__(self, start=datetime(2026, 9, 25, 10, 0, tzinfo=timezone.utc)):
        self.now = start

    def __call__(self):
        self.now += timedelta(seconds=1)
        return self.now


class StubS3:
    def __init__(self, clock=None, page_size=1000):
        self.fail_delete: set[str] = set()  # keys DeleteObjects reports as errors
        self.objects: dict[str, dict] = {}
        self.calls: list[tuple[str, dict]] = []
        self.clock = clock or Clock()
        self.page_size = page_size
        self.on_copy = None  # hook(source_key, dest_key) for concurrency tests

    # ---------------------------------------------------------------- helpers
    def _stamp(self, modified=None):
        return (modified or self.clock()).replace(microsecond=0)  # S3 keeps whole seconds

    def add(self, key, body=b"x", modified=None, size=None, etag=None, **meta):
        body = body if isinstance(body, bytes) else body.encode()
        self.objects[key] = {
            "Body": body,
            "Size": len(body) if size is None else size,
            "ETag": f'"{etag or hashlib.md5(body).hexdigest()}"',
            "LastModified": self._stamp(modified),
            "ContentType": meta.get("ContentType", "application/octet-stream"),
            "ContentDisposition": meta.get("ContentDisposition"),
            "CacheControl": meta.get("CacheControl"),
            "Metadata": meta.get("Metadata", {}),
        }

    def keys(self, prefix=""):
        return sorted(k for k in self.objects if k.startswith(prefix))

    def count(self, operation):
        return sum(1 for name, _ in self.calls if name == operation)

    # ---------------------------------------------------------------- client API
    def list_objects_v2(self, Bucket, Prefix="", Delimiter=None, ContinuationToken=None, **_):
        self.calls.append(("list_objects_v2", {"Prefix": Prefix, "Delimiter": Delimiter}))
        keys = self.keys(Prefix)
        entries: list[tuple[str, str]] = []  # (sort key, kind)
        seen_prefixes = set()
        for key in keys:
            rest = key[len(Prefix):]
            if Delimiter and Delimiter in rest:
                common = Prefix + rest.split(Delimiter, 1)[0] + Delimiter
                if common not in seen_prefixes:
                    seen_prefixes.add(common)
                    entries.append((common, "prefix"))
            else:
                entries.append((key, "key"))
        start = int(ContinuationToken or 0)
        page = entries[start:start + self.page_size]
        response = {
            "Contents": [{"Key": k, "ETag": self.objects[k]["ETag"], "Size": self.objects[k]["Size"],
                          "LastModified": self.objects[k]["LastModified"]} for k, kind in page if kind == "key"],
            "CommonPrefixes": [{"Prefix": k} for k, kind in page if kind == "prefix"],
            "IsTruncated": start + self.page_size < len(entries),
        }
        if response["IsTruncated"]:
            response["NextContinuationToken"] = str(start + self.page_size)
        return response

    def get_paginator(self, name):
        assert name == "list_objects_v2"
        client = self

        class Paginator:
            def paginate(self, **kwargs):
                token = None
                while True:
                    page = client.list_objects_v2(**kwargs, ContinuationToken=token)
                    yield page
                    if not page["IsTruncated"]:
                        break
                    token = page["NextContinuationToken"]

        return Paginator()

    def get_object(self, Bucket, Key, **_):
        self.calls.append(("get_object", {"Key": Key}))
        if Key not in self.objects:
            raise _missing("GetObject")
        obj = self.objects[Key]

        class Body:
            def read(self):
                return obj["Body"]

        return {"Body": Body(), "ETag": obj["ETag"], "ContentType": obj["ContentType"]}

    def head_object(self, Bucket, Key, **_):
        self.calls.append(("head_object", {"Key": Key}))
        if Key not in self.objects:
            raise _missing("HeadObject", code="404")
        obj = self.objects[Key]
        return {"ETag": obj["ETag"], "ContentType": obj["ContentType"],
                "ContentDisposition": obj["ContentDisposition"], "CacheControl": obj["CacheControl"],
                "LastModified": obj["LastModified"], "ContentLength": obj["Size"],
                "Metadata": dict(obj["Metadata"])}

    def put_object(self, Bucket, Key, Body, ContentType=None, CacheControl=None, **_):
        self.calls.append(("put_object", {"Key": Key}))
        self.add(Key, Body, ContentType=ContentType, CacheControl=CacheControl)
        return {"ETag": self.objects[Key]["ETag"]}

    def copy_object(self, Bucket, Key, CopySource, MetadataDirective="COPY", ContentType=None,
                    ContentDisposition=None, CacheControl=None, Metadata=None, **_):
        self.calls.append(("copy_object", {"Key": Key, "Source": CopySource["Key"],
                                           "TaggingDirective": _.get("TaggingDirective", "COPY")}))
        if self.on_copy:
            self.on_copy(CopySource["Key"], Key)
        if CopySource["Key"] not in self.objects:
            raise _missing("CopyObject")
        source = self.objects[CopySource["Key"]]
        if source["Size"] > FIVE_GIB:
            raise ClientError({"Error": {"Code": "InvalidRequest", "Message": "too large"}}, "CopyObject")
        replace = MetadataDirective == "REPLACE"
        multipart = "-" in source["ETag"]
        self.objects[Key] = {
            "Body": source["Body"],
            "Size": source["Size"],
            # a single-part copy keeps the ETag; a multipart source does not
            "ETag": f'"{hashlib.md5(source["Body"]).hexdigest()}"' if multipart else source["ETag"],
            "LastModified": self._stamp(),
            "ContentType": ContentType if replace else source["ContentType"],
            "ContentDisposition": ContentDisposition if replace else source["ContentDisposition"],
            "CacheControl": CacheControl if replace else source["CacheControl"],
            "Metadata": dict(Metadata or {}) if replace else dict(source["Metadata"]),
        }
        return {}

    def copy(self, CopySource, Bucket, Key, **_):
        """The managed (multipart) copy of boto3: any size, keeps the multipart ETag."""
        self.calls.append(("copy", {"Key": Key, "Source": CopySource["Key"]}))
        if CopySource["Key"] not in self.objects:
            raise _missing("CopyObject")
        source = self.objects[CopySource["Key"]]
        self.objects[Key] = {**source, "LastModified": self._stamp(), "Metadata": dict(source["Metadata"])}

    def delete_objects(self, Bucket, Delete):
        keys = [o["Key"] for o in Delete["Objects"]]
        self.calls.append(("delete_objects", {"Keys": keys}))
        errors = [{"Key": k, "Code": "AccessDenied", "Message": "denied"} for k in keys if k in self.fail_delete]
        for key in keys:
            if key not in self.fail_delete:
                self.objects.pop(key, None)  # deleting a missing key is not an error on S3
        response = {"Deleted": [{"Key": k} for k in keys if k not in self.fail_delete]}
        if errors:
            response["Errors"] = errors  # a 200 response that lists per-key failures
        return response


class StubCloudFront:
    def __init__(self, fail=False):
        self.invalidations: list[list[str]] = []
        self.fail = fail

    def create_invalidation(self, DistributionId, InvalidationBatch):
        if self.fail:
            raise ClientError({"Error": {"Code": "ServiceUnavailable", "Message": "down"}}, "CreateInvalidation")
        self.invalidations.append(InvalidationBatch["Paths"]["Items"])
        return {"Invalidation": {"Id": str(len(self.invalidations))}}


class StubSQS:
    def __init__(self, fail_ids=()):
        self.batches: list[list[dict]] = []
        self.fail_ids = set(fail_ids)

    def send_message_batch(self, QueueUrl, Entries):
        assert len(Entries) <= 10
        self.batches.append(Entries)
        return {"Successful": [{"Id": e["Id"]} for e in Entries if e["Id"] not in self.fail_ids],
                "Failed": [{"Id": e["Id"], "Code": "InternalError", "SenderFault": False}
                           for e in Entries if e["Id"] in self.fail_ids]}
