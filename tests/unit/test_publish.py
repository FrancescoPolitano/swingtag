"""Unit tests for publish.py against stub clients."""
import json
import logging
from datetime import datetime, timezone
from urllib.parse import unquote_plus

import pytest

from stubs import Clock, StubCloudFront, StubS3, StubSQS
from swingtag import convention
from swingtag.catalog import item_prefix
from swingtag.publish import Publisher, ascii_filename
from swingtag.settings import Settings

SECRET = "test-secret"


def settings():
    return Settings(bucket="b", source_prefix="source/", public_prefix="public/",
                    config_key="config/theme.json", public_base_url="https://d1.cloudfront.net",
                    distribution_id="E123", queue_url="https://sqs.example/q", token_secret=SECRET)


class World:
    def __init__(self, cloudfront_fails=False, page_size=1000):
        self.clock = Clock()
        self.s3 = StubS3(clock=self.clock, page_size=page_size)
        self.cf = StubCloudFront(fail=cloudfront_fails)
        self.sqs = StubSQS()

    def publisher(self):
        return Publisher(settings(), self.s3, self.cf, self.sqs, clock=self.clock)

    def publish(self, prefix):
        return self.publisher().publish(prefix)


@pytest.fixture
def world():
    return World()


def tok(collection, label):
    return convention.token_for(collection, label, SECRET)


def PDF(n=1):
    return b"%PDF-1.4 " + str(n).encode() * 40


def test_listing_paginated():
    w = World(page_size=1000)
    for i in range(2500):
        w.s3.add(f"source/C/A · abcdefghijkm/10 E/f{i:04d}.pdf")
    assert len(w.publisher().list_prefix("source/C/A · abcdefghijkm/")) == 2500


def test_ascii_filename():
    assert ascii_filename("Menù d'estate.pdf", ".pdf") == "Menu d'estate.pdf"
    assert ascii_filename('Straße "neu".pdf', ".pdf") == "Strasse neu.pdf"
    assert ascii_filename("★★★.pdf", ".pdf") == "file.pdf"


def test_put_if_changed_skips_same_body(world):
    publisher = world.publisher()
    assert publisher._put_if_changed("public/x.txt", b"same", "text/plain", "no-store") is True
    assert publisher._put_if_changed("public/x.txt", b"same", "text/plain", "no-store") is False
    assert world.s3.count("put_object") == 1


def test_token_owners_sorted_nfc(world):
    world.s3.add("source/C2/B · abcdefghijkm/10 E/x.pdf")
    world.s3.add("source/C1/A · abcdefghijkm/10 E/x.pdf")
    world.s3.add("source/C1/Other · bcdefghijkmn/10 E/x.pdf")
    assert world.publisher().token_owners("abcdefghijkm", "source/C2/") == [
        "source/C1/A · abcdefghijkm/", "source/C2/B · abcdefghijkm/"]


def test_first_publication(world):
    world.s3.add("source/Vivaio/Olivo/10 Scheda/scheda.pdf", PDF())
    item = world.publish("source/Vivaio/Olivo/")
    t = tok("Vivaio", "Olivo")
    assert item.token == t
    assert world.s3.keys("source/") == [f"source/Vivaio/Olivo · {t}/10 Scheda/scheda.pdf"]
    assert world.s3.keys("public/") == [f"public/{t}/index.html", f"public/{t}/qr.svg",
                                         f"public/{t}/scheda/scheda.pdf"]


def test_empty_untokenised_not_christened(world):
    world.publish("source/Vivaio/Ghost/")
    assert world.s3.count("put_object") == world.s3.count("copy_object") == world.s3.count("delete_objects") == 0


def test_concurrent_christening_converges(world):
    world.s3.add("source/C/A/10 E/x.pdf", PDF(1))
    world.s3.add("source/C/A/20 F/y.pdf", PDF(2))
    ran = []

    def interleave(source, dest):
        if not ran:  # the second run starts while the first is copying
            ran.append(True)
            world.publish("source/C/A/")

    world.s3.on_copy = interleave
    world.publish("source/C/A/")
    world.s3.on_copy = None
    t = tok("C", "A")
    assert {k.split("/")[2] for k in world.s3.keys("source/")} == {f"A · {t}"}
    assert {k.split("/")[1] for k in world.s3.keys("public/")} == {t}


def test_copy_metadata(world):
    world.s3.add("source/C/A · abcdefghijkm/10 Doc/doc.pdf", PDF())
    world.s3.add("source/C/A · abcdefghijkm/20 Clip/clip.MP4", b"\x00\x00\x00\x18ftypmp42")
    world.publish("source/C/A · abcdefghijkm/")
    pdf = world.s3.objects["public/abcdefghijkm/doc/doc.pdf"]
    mp4 = world.s3.objects["public/abcdefghijkm/clip/clip.mp4"]
    assert (pdf["ContentType"], mp4["ContentType"]) == ("application/pdf", "video/mp4")
    assert pdf["ContentDisposition"] == 'inline; filename="doc.pdf"'
    assert mp4["ContentDisposition"] == 'inline; filename="clip.MP4"'
    assert pdf["CacheControl"] == mp4["CacheControl"] == "public, max-age=300"


def test_copy_skipped_same_etag(world):
    world.s3.add("source/C/A · abcdefghijkm/10 Doc/doc.pdf", PDF())
    world.publish("source/C/A · abcdefghijkm/")
    world.s3.calls.clear()
    world.publish("source/C/A · abcdefghijkm/")
    assert world.s3.count("copy_object") == 0


def test_replacement(world):
    key = "source/C/A · abcdefghijkm/10 Doc/doc.pdf"
    world.s3.add(key, PDF(1), modified=datetime(2026, 9, 1, tzinfo=timezone.utc))
    world.publish("source/C/A · abcdefghijkm/")
    world.s3.calls.clear()
    before = len(world.cf.invalidations)
    world.s3.add(key, PDF(2), modified=datetime(2026, 9, 2, tzinfo=timezone.utc))
    world.publish("source/C/A · abcdefghijkm/")
    puts = [c[1]["Key"] for c in world.s3.calls if c[0] == "put_object"]
    assert world.s3.count("copy_object") == 1
    assert puts == ["public/abcdefghijkm/index.html"]
    assert world.s3.objects["public/abcdefghijkm/doc/doc.pdf"]["Body"] == PDF(2)
    assert len(world.cf.invalidations) == before + 1


def test_removal(world):
    world.s3.add("source/C/A · abcdefghijkm/10 Doc/doc.pdf", PDF(1))
    world.s3.add("source/C/A · abcdefghijkm/20 Menu/menu.pdf", PDF(2))
    world.publish("source/C/A · abcdefghijkm/")
    del world.s3.objects["source/C/A · abcdefghijkm/10 Doc/doc.pdf"]
    world.publish("source/C/A · abcdefghijkm/")
    assert "public/abcdefghijkm/doc/doc.pdf" not in world.s3.objects
    assert world.s3.objects["public/abcdefghijkm/index.html"]["Body"].count(b"class=b ") == 1


def test_idempotent_page(world):
    world.s3.add("source/C/A · abcdefghijkm/10 Doc/doc.pdf", PDF())
    world.publish("source/C/A · abcdefghijkm/")
    page = world.s3.objects["public/abcdefghijkm/index.html"]["Body"]
    world.s3.calls.clear()
    world.publish("source/C/A · abcdefghijkm/")
    assert world.s3.count("put_object") == world.s3.count("copy_object") == 0
    assert world.s3.objects["public/abcdefghijkm/index.html"]["Body"] == page


def test_page_date_from_source():
    w = World()
    w.clock.now = datetime(2030, 1, 1, tzinfo=timezone.utc)
    w.s3.add("source/C/A · abcdefghijkm/10 Doc/doc.pdf", PDF(), modified=datetime(2026, 9, 1, 8, 0, tzinfo=timezone.utc))
    w.publish("source/C/A · abcdefghijkm/")
    assert b"1 Sep 2026, 08:00" in w.s3.objects["public/abcdefghijkm/index.html"]["Body"]


def move(world, old, new):
    for key in world.s3.keys(old):
        world.s3.objects[new + key[len(old):]] = world.s3.objects.pop(key)


def test_rename_keeps_publication(world):
    world.s3.add("source/C1/A · abcdefghijkm/10 Doc/doc.pdf", PDF())
    world.publish("source/C1/A · abcdefghijkm/")
    move(world, "source/C1/A · abcdefghijkm/", "source/C1/B · abcdefghijkm/")
    world.publish("source/C1/A · abcdefghijkm/")  # the removal event of the old prefix
    assert "public/abcdefghijkm/doc/doc.pdf" in world.s3.objects
    assert b"<h1>B</h1>" in world.s3.objects["public/abcdefghijkm/index.html"]["Body"]


def test_move_collection_keeps_publication(world):
    world.s3.add("source/C1/A · abcdefghijkm/10 Doc/doc.pdf", PDF())
    world.publish("source/C1/A · abcdefghijkm/")
    move(world, "source/C1/A · abcdefghijkm/", "source/C2/A · abcdefghijkm/")
    world.publish("source/C1/A · abcdefghijkm/")
    assert "public/abcdefghijkm/doc/doc.pdf" in world.s3.objects
    assert b"C2" in world.s3.objects["public/abcdefghijkm/index.html"]["Body"]


def test_empty_removes_publication(world):
    world.s3.add("source/C/A · abcdefghijkm/10 Doc/doc.pdf", PDF())
    world.publish("source/C/A · abcdefghijkm/")
    world.s3.objects.clear()
    world.publish("source/C/A · abcdefghijkm/")
    assert world.s3.keys("public/abcdefghijkm/") == []
    assert world.cf.invalidations[-1] == ["/abcdefghijkm*"]


def test_restore_same_token(world):
    world.s3.add("source/C/A/10 Doc/doc.pdf", PDF())
    t = world.publish("source/C/A/").token
    for key in world.s3.keys("source/"):
        del world.s3.objects[key]
    world.publish(f"source/C/A · {t}/")
    assert world.s3.keys("public/") == []
    world.s3.add("source/C/A/10 Doc/doc.pdf", PDF())
    assert world.publish("source/C/A/").token == t


def test_token_edited_new_address(world):
    world.s3.add("source/C/A · abcdefghijkm/10 Doc/doc.pdf", PDF())
    world.publish("source/C/A · abcdefghijkm/")
    move(world, "source/C/A · abcdefghijkm/", "source/C/A · abcdefghijk0/")
    new = world.publish("source/C/A · abcdefghijk0/")
    assert new.token == tok("C", "A · abcdefghijk0")
    world.publish("source/C/A · abcdefghijkm/")  # removal event of the old prefix
    assert world.s3.keys("public/abcdefghijkm/") == []
    assert world.s3.keys(f"public/{new.token}/")


def test_duplicate_token(world, caplog):
    world.s3.add("source/C/A · abcdefghijkm/10 Doc/doc.pdf", PDF(1))
    world.s3.add("source/C/B · abcdefghijkm/10 Doc/doc.pdf", PDF(2))
    with caplog.at_level(logging.WARNING):
        world.publish("source/C/B · abcdefghijkm/")
    assert world.s3.keys("public/") == []
    assert any("duplicate token" in r.getMessage() for r in caplog.records)
    world.publish("source/C/A · abcdefghijkm/")
    assert world.s3.objects["public/abcdefghijkm/doc/doc.pdf"]["Body"] == PDF(1)


def test_prune_spares_recent(world):
    world.s3.add("source/C/A · abcdefghijkm/10 Doc/doc.pdf", PDF())
    world.s3.add("public/abcdefghijkm/stale.txt", b"old", modified=datetime(2000, 1, 1, tzinfo=timezone.utc))
    world.s3.add("public/abcdefghijkm/fresh.txt", b"new", modified=datetime(2099, 1, 1, tzinfo=timezone.utc))
    world.publish("source/C/A · abcdefghijkm/")
    assert "public/abcdefghijkm/stale.txt" not in world.s3.objects
    assert "public/abcdefghijkm/fresh.txt" in world.s3.objects


def test_invalidation_failure_not_raised(caplog):
    w = World(cloudfront_fails=True)
    w.s3.add("source/C/A · abcdefghijkm/10 Doc/doc.pdf", PDF())
    with caplog.at_level(logging.WARNING):
        item = w.publish("source/C/A · abcdefghijkm/")
    assert len(item.buttons) == 1
    assert any("invalidation" in r.getMessage() for r in caplog.records)


def test_theme_loaded_once(world):
    world.s3.add("config/theme.json", json.dumps({"locale": "it", "colors": {
        "primary": "#8a2d1c", "background": "#fbf7f2", "text": "#1f1b16"}}).encode())
    world.s3.add("source/C/A · abcdefghijkm/10 Doc/doc.pdf", PDF())
    world.s3.add("source/C/B · bcdefghijkmn/10 Doc/doc.pdf", PDF())
    publisher = world.publisher()
    publisher.publish("source/C/A · abcdefghijkm/")
    publisher.publish("source/C/B · bcdefghijkmn/")
    theme_reads = [c for c in world.s3.calls if c[0] == "get_object" and c[1]["Key"] == "config/theme.json"]
    assert len(theme_reads) == 1
    assert b'<html lang="it">' in world.s3.objects["public/bcdefghijkmn/index.html"]["Body"]


def test_theme_missing(world):
    world.s3.add("source/C/A · abcdefghijkm/10 Doc/doc.pdf", PDF())
    world.publish("source/C/A · abcdefghijkm/")
    assert b'<html lang="en">' in world.s3.objects["public/abcdefghijkm/index.html"]["Body"]


def test_only_publisher_writes_public(world):
    world.s3.add("source/C/A/10 Doc/doc.pdf", PDF())
    world.publish("source/C/A/")
    writes = [c[1]["Key"] for c in world.s3.calls if c[0] in ("put_object", "copy_object")]
    assert writes and all(k.startswith(("public/", "source/C/A · ")) for k in writes)


def test_existing_token_kept(world):
    world.s3.add("source/C/A · k7m2p9x4qzbv/10 Doc/doc.pdf", PDF())
    item = world.publish("source/C/A · k7m2p9x4qzbv/")
    assert item.token == "k7m2p9x4qzbv" != tok("C", "A")
    assert world.s3.keys("source/") == ["source/C/A · k7m2p9x4qzbv/10 Doc/doc.pdf"]


def test_republish_interleaved_with_event():
    def scenario(interleave):
        w = World()
        w.s3.add("source/C/A · abcdefghijkm/10 Doc/doc.pdf", PDF(1))
        w.s3.add("source/C/A · abcdefghijkm/20 Menu/menu.pdf", PDF(2))
        if interleave:
            ran = []

            def hook(source, dest):
                if not ran:
                    ran.append(True)
                    w.publish("source/C/A · abcdefghijkm/")
            w.s3.on_copy = hook
        w.publish("source/C/A · abcdefghijkm/")
        return {k: w.s3.objects[k]["Body"] for k in w.s3.keys("public/")}

    assert scenario(interleave=True) == scenario(interleave=False)


def test_nfd_prefix_not_duplicate_of_itself(world):
    """a folder uploaded from macOS (NFD) is not its own duplicate."""
    import unicodedata
    prefix = unicodedata.normalize("NFD", "source/Città/Menù · abcdefghijkm/")
    world.s3.add(prefix + "10 Doc/doc.pdf", PDF())
    item = world.publish(prefix)
    assert len(item.buttons) == 1 and "public/abcdefghijkm/doc/doc.pdf" in world.s3.objects


def test_large_link_not_downloaded(world):
    """a link file over 64 KiB is never read and becomes an anomaly."""
    world.s3.add("source/C/A · abcdefghijkm/10 Doc/doc.pdf", PDF())
    world.s3.add("source/C/A · abcdefghijkm/50 Book/book.url", b"[InternetShortcut]\nURL=https://example.com\n" + b" " * 70000)
    item = world.publish("source/C/A · abcdefghijkm/")
    reads = [c[1]["Key"] for c in world.s3.calls if c[0] == "get_object"]
    assert not any(k.endswith("book.url") for k in reads)
    assert any(a.startswith("invalid link") for a in item.anomalies)


def test_ignored_collection_not_published(world):
    """names starting with _ or . are ignored at every level."""
    world.s3.add("source/_drafts/A · abcdefghijkm/10 Doc/doc.pdf", PDF())
    world.s3.add("source/C/.hidden · bcdefghijkmn/10 Doc/doc.pdf", PDF())
    world.publish("source/_drafts/A · abcdefghijkm/")
    world.publish("source/C/.hidden · bcdefghijkmn/")
    assert world.s3.keys("public/") == []
    assert world.publisher().item_prefixes() == []


def test_error_page(world):
    world.publisher().publish_error_page()
    page = world.s3.objects["public/404.html"]
    assert page["ContentType"] == "text/html; charset=utf-8"
    assert b"Page not available" in page["Body"]


def test_republish_all_enqueues(world):
    prefixes = []
    for c in range(3):
        for i in range(8 if c < 2 else 7):
            prefix = f"source/Coll {c}/Item {i} · abcdefghij{c}{i if i > 1 else i + 2}/"
            prefixes.append(prefix)
            world.s3.add(prefix + "10 Doc/doc.pdf")
    count = world.publisher().republish_all()
    assert count == 23
    assert [len(b) for b in world.sqs.batches] == [10, 10, 3]
    decoded = []
    for batch in world.sqs.batches:
        for entry in batch:
            key = json.loads(entry["MessageBody"])["Records"][0]["s3"]["object"]["key"]
            decoded.append(item_prefix("source/", unquote_plus(key)))
    assert sorted(decoded) == sorted(prefixes)


def test_republish_all_invalidates(world):
    world.s3.add("source/C/A · abcdefghijkm/10 Doc/doc.pdf")
    world.publisher().republish_all()
    assert world.cf.invalidations[-1] == ["/404.html", "/_assets/*"]


def test_republish_all_empty(world):
    """no items means no queue call, but the site-wide paths are invalidated."""
    assert world.publisher().republish_all() == 0
    assert world.sqs.batches == [] and world.cf.invalidations == [["/404.html", "/_assets/*"]]


# ---------------------------------------------------------------- edge cases

def test_console_rename_with_placeholder_keeps_url(world):
    """Critical: a console move leaves the folder placeholder behind; the URL must survive."""
    world.s3.add("source/C/A · abcdefghijkm/", b"")  # "Create folder" placeholder
    world.s3.add("source/C/A · abcdefghijkm/10 Doc/doc.pdf", PDF())
    world.publish("source/C/A · abcdefghijkm/")
    world.s3.objects["source/C/B · abcdefghijkm/10 Doc/doc.pdf"] = world.s3.objects.pop(
        "source/C/A · abcdefghijkm/10 Doc/doc.pdf")
    world.publish("source/C/A · abcdefghijkm/")  # removal event of the old folder
    world.publish("source/C/B · abcdefghijkm/")  # creation event of the new one
    assert "public/abcdefghijkm/doc/doc.pdf" in world.s3.objects
    assert b"<h1>B</h1>" in world.s3.objects["public/abcdefghijkm/index.html"]["Body"]


def test_old_folder_with_only_ds_store_does_not_win(world):
    world.s3.add("source/C/A · abcdefghijkm/.DS_Store", b"x")
    world.s3.add("source/C/B · abcdefghijkm/10 Doc/doc.pdf", PDF())
    world.publish("source/C/B · abcdefghijkm/")
    assert "public/abcdefghijkm/doc/doc.pdf" in world.s3.objects


def test_placeholder_only_folder_not_christened(world):
    world.s3.add("source/C/New/", b"")
    world.publish("source/C/New/")
    assert world.s3.keys("source/") == ["source/C/New/"]


def test_ignored_backup_does_not_own_token(world):
    world.s3.add("source/_archive/Olivo · abcdefghijkm/10 Doc/doc.pdf", PDF(1))
    world.s3.add("source/menu/Olivo · abcdefghijkm/10 Doc/doc.pdf", PDF(2))
    world.publish("source/menu/Olivo · abcdefghijkm/")
    assert world.s3.objects["public/abcdefghijkm/doc/doc.pdf"]["Body"] == PDF(2)


def test_move_to_drafts_unpublishes(world):
    world.s3.add("source/menu/Olivo · abcdefghijkm/10 Doc/doc.pdf", PDF())
    world.publish("source/menu/Olivo · abcdefghijkm/")
    world.s3.objects["source/_drafts/Olivo · abcdefghijkm/10 Doc/doc.pdf"] = world.s3.objects.pop(
        "source/menu/Olivo · abcdefghijkm/10 Doc/doc.pdf")
    world.publish("source/menu/Olivo · abcdefghijkm/")
    assert world.s3.keys("public/abcdefghijkm/") == []


def test_nfc_nfd_twins_single_owner(world):
    import unicodedata
    nfc = "source/C/Menù · abcdefghijkm/"
    nfd = unicodedata.normalize("NFD", nfc)
    world.s3.add(nfc + "10 Doc/doc.pdf", PDF(1))
    world.s3.add(nfd + "20 Menu/menu.pdf", PDF(2))
    world.publish(nfd)
    world.publish(nfc)  # the last run must not take over from the deterministic owner
    owner = min([nfc, nfd], key=lambda p: (convention.normalize(p), p))
    kept = "doc" if owner == nfc else "menu"
    assert f"public/abcdefghijkm/{kept}/{kept}.pdf" in world.s3.objects
    assert len([k for k in world.s3.keys("public/abcdefghijkm/") if k.endswith(".pdf")]) == 1


def test_christen_large_object_uses_managed_copy(world):
    world.s3.add("source/C/A/10 Clip/big.mp4", b"big", size=6 * 1024**3)
    world.s3.add("source/C/A/20 Doc/doc.pdf", PDF())
    item = world.publish("source/C/A/")
    t = tok("C", "A")
    assert world.s3.keys("source/") == [f"source/C/A · {t}/10 Clip/big.mp4", f"source/C/A · {t}/20 Doc/doc.pdf"]
    assert [b.filename for b in item.buttons] == ["doc.pdf"]  # the big file stays an anomaly
    assert any(a.startswith("too large for single copy") for a in item.anomalies)


def test_multipart_source_not_recopied(world):
    world.s3.add("source/C/A · abcdefghijkm/10 Clip/clip.mp4", b"video", etag="44c3dcef15943cd677dba34b783254a5-3")
    world.publish("source/C/A · abcdefghijkm/")
    world.s3.calls.clear()
    world.publish("source/C/A · abcdefghijkm/")
    assert world.s3.count("copy_object") == 0
    assert world.s3.objects["public/abcdefghijkm/clip/clip.mp4"]["Metadata"]["source-etag"] == \
        "44c3dcef15943cd677dba34b783254a5-3"


def test_delete_errors_raise(world):
    world.s3.add("source/C/A · abcdefghijkm/10 Doc/doc.pdf", PDF())
    world.s3.add("public/abcdefghijkm/stale.txt", b"x", modified=datetime(2000, 1, 1, tzinfo=timezone.utc))
    world.s3.fail_delete = {"public/abcdefghijkm/stale.txt"}
    with pytest.raises(RuntimeError, match="stale.txt"):
        world.publish("source/C/A · abcdefghijkm/")


def test_send_batch_failure_raises():
    w = World()
    w.sqs = StubSQS(fail_ids={"1"})
    w.s3.add("source/C/A · abcdefghijkm/10 Doc/doc.pdf")
    w.s3.add("source/C/B · bcdefghijkmn/10 Doc/doc.pdf")
    with pytest.raises(RuntimeError, match="republish"):
        w.publisher().republish_all()


def test_prune_spares_same_second_writes(world):
    """S3 truncates LastModified to the second: a write in the run's own second is fresh."""
    world.s3.add("source/C/A · abcdefghijkm/10 Doc/doc.pdf", PDF())
    started = world.clock.now.replace(microsecond=0)
    world.s3.add("public/abcdefghijkm/concurrent.pdf", b"x", modified=started)
    world.publish("source/C/A · abcdefghijkm/")
    assert "public/abcdefghijkm/concurrent.pdf" in world.s3.objects


def test_no_invalidation_when_unchanged(world):
    world.s3.add("source/C/A · abcdefghijkm/10 Doc/doc.pdf", PDF())
    world.publish("source/C/A · abcdefghijkm/")
    before = len(world.cf.invalidations)
    world.publish("source/C/A · abcdefghijkm/")
    assert len(world.cf.invalidations) == before


def test_ascii_filename_strips_controls():
    assert ascii_filename("a\r\nX-Evil: 1.pdf", ".pdf") == "aX-Evil: 1.pdf"


def test_link_bodies_skip_ignored_and_misplaced(world):
    world.s3.add("source/C/A · abcdefghijkm/10 Doc/doc.pdf", PDF())
    world.s3.add("source/C/A · abcdefghijkm/_old/book.url", b"[InternetShortcut]\nURL=https://example.com\n")
    world.s3.add("source/C/A · abcdefghijkm/book.url", b"[InternetShortcut]\nURL=https://example.com\n")
    world.publish("source/C/A · abcdefghijkm/")
    reads = [c[1]["Key"] for c in world.s3.calls if c[0] == "get_object"]
    assert not any(k.endswith("book.url") for k in reads)


def test_two_owners_without_valid_resources_do_not_recurse(world):
    """Step 6 hands over to another owner; two owners with nothing valid must not loop."""
    world.s3.add("source/C/A · abcdefghijkm/10 Doc/notes.docx", b"x")
    world.s3.add("source/C/B · abcdefghijkm/10 Doc/notes.docx", b"x")
    world.publish("source/C/A · abcdefghijkm/")
    world.publish("source/C/B · abcdefghijkm/")
    assert world.s3.keys("public/") == []


def test_public_copies_do_not_copy_tags(world):
    """copying the owner's tags needs tagging permissions; public copies drop them."""
    world.s3.add("source/C/A · abcdefghijkm/10 Doc/doc.pdf", PDF())
    world.publish("source/C/A · abcdefghijkm/")
    copies = [c[1] for c in world.s3.calls if c[0] == "copy_object" and c[1]["Key"].startswith("public/")]
    assert copies and all(c["TaggingDirective"] == "REPLACE" for c in copies)
