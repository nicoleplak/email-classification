"""LOCAL_BLOB_DIR: the blob container as a local folder, and the offline demo that fills it."""

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from data import blob_output

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def local_blob(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCAL_BLOB_DIR", str(tmp_path / "blob"))
    return tmp_path / "blob"


def test_upload_list_download_round_trip(local_blob, tmp_path):
    blob_output.upload_bytes("bronze/run1/emails.json", b"[]")
    blob_output.upload_bytes("silver/run1/case/text/a.txt", "κείμενο".encode())
    assert (local_blob / "bronze" / "run1" / "emails.json").read_bytes() == b"[]"
    assert blob_output.list_names("bronze/") == ["bronze/run1/emails.json"]
    assert blob_output.list_names("") == ["bronze/run1/emails.json", "silver/run1/case/text/a.txt"]
    assert blob_output.download("silver/run1/case/text/a.txt").decode() == "κείμενο"

    blob_output.upload_bytes("bronze/run1/emails.json", b"{}")  # silver/bronze writes overwrite
    target = tmp_path / "copy.json"
    blob_output.download_to("bronze/run1/emails.json", target)
    assert target.read_bytes() == b"{}"


def test_missing_blob_and_empty_folder(local_blob):
    assert blob_output.list_names("bronze/") == []  # folder not created yet
    with pytest.raises(FileNotFoundError):
        blob_output.download("bronze/nope.json")


def test_result_files_are_never_overwritten(local_blob, tmp_path):
    source = tmp_path / "result.json"
    source.write_text("1")
    blob_output.upload_result_file(str(source), "gold/result.json")
    with pytest.raises(FileExistsError):
        blob_output.upload_result_file(str(source), "gold/result.json")


@pytest.mark.parametrize("name", ["../outside.txt", "bronze/../../outside.txt", "/etc/passwd", ""])
def test_names_cannot_leave_the_folder(local_blob, name):
    with pytest.raises(ValueError):
        blob_output.upload_bytes(name, b"x")
    with pytest.raises(ValueError):
        blob_output.download(name)


def test_unset_means_azure(monkeypatch):
    monkeypatch.delenv("LOCAL_BLOB_DIR", raising=False)
    assert blob_output.local_root() is None


def _graph_blob_store():
    path = ROOT / "graphapi" / "src" / "helpers" / "blob_store.py"
    spec = importlib.util.spec_from_file_location("graph_blob_store", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_graph_ingest_writes_to_the_same_folder(local_blob):
    store = _graph_blob_store()
    assert store.download("state/graph_delta_state.json") is None  # first run: no checkpoint yet
    assert store.upload(b"a", "attachments/x/file.pdf") is True
    assert store.upload(b"b", "attachments/x/file.pdf") is False  # kept, as with Azure's overwrite=False
    assert store.upload(b"c", "state/graph_delta_state.json", overwrite=True) is True
    assert store.download("attachments/x/file.pdf") == b"a"
    assert blob_output.list_names("state/") == ["state/graph_delta_state.json"]  # classifier sees it too


def test_local_demo_fills_every_queue(tmp_path):
    """tools/local_demo.py end to end: invented emails, registry, cases, classifications, text views."""
    folder = tmp_path / "demo"
    env = {k: v for k, v in os.environ.items() if k not in ("LOCAL_BLOB_DIR", "LOCAL_STORE_DIR", "CASE_STORE")}
    env["PYTHONIOENCODING"] = "utf-8"
    done = subprocess.run([sys.executable, str(ROOT / "tools" / "local_demo.py"), "--folder", str(folder),
                           "--emails", "12"], capture_output=True, text=True, env=env, timeout=120)
    assert done.returncode == 0, done.stderr[-2000:]

    cases = [json.loads(p.read_text(encoding="utf-8")) for p in (folder / "case_store" / "cases").glob("*.json")]
    assert len(cases) == 14
    routes = {c["route"] for c in cases}
    assert {"AUTO", "REVIEW", "EXCEPTION", None} <= routes  # None: the two left waiting
    assert sum(c["status"] == "RECEIVED" for c in cases) == 2
    understood = [c for c in cases if (c.get("understanding") or {}).get("customers")]
    assert understood and all(c["understanding"]["evidence"] for c in understood)

    blob = folder / "blob"
    assert list((blob / "in").glob("qualco_output_*.csv"))
    assert list(blob.glob("silver/*/*/text/*.txt"))  # attachment text the review app shows
    with_files = [c for c in cases if c["sourceRefs"]["attachments"]]
    assert all((blob / name).is_file() for c in with_files for name in c["sourceRefs"]["attachments"])


def _fetch_sample():
    spec = importlib.util.spec_from_file_location("fetch_sample", ROOT / "tools" / "fetch_sample.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FakeContainer:
    """Stands in for the Azure container: list and download only (the script must never write)."""

    def __init__(self, files):
        self.files = files

    def list_blobs(self, name_starts_with=""):
        from types import SimpleNamespace

        return [SimpleNamespace(name=n) for n in sorted(self.files) if n.startswith(name_starts_with)]

    def download_blob(self, name):
        from types import SimpleNamespace

        if name not in self.files:
            raise KeyError(name)
        return SimpleNamespace(readall=lambda: self.files[name])


def test_fetch_sample_copies_runs_and_what_their_emails_point_to(tmp_path):
    message = lambda n, att: {"id": f"m{n}", "eml_blob_path": f"messages/aa/m{n}/message.eml",  # noqa: E731
                              "attachments": [{"blob_name": att}] if att else []}
    files = {
        "bronze/20261101T000000Z/emails.json": json.dumps([message(0, None)]).encode(),
        "bronze/20261120T000000Z/emails.json": json.dumps(
            {"messages": [message(1, "attachments/x/1.pdf"), message(2, "attachments/x/gone.pdf"), message(3, None)],
             "removed": []}).encode(),
        "messages/aa/m0/message.eml": b"0", "messages/aa/m1/message.eml": b"1", "messages/aa/m2/message.eml": b"2",
        "messages/aa/m3/message.eml": b"3", "attachments/x/1.pdf": b"%PDF",
        "in/qualco_output_20261101.csv": b"old", "in/qualco_output_20261120.csv": b"new",
    }
    dest = tmp_path / "blob"
    totals = _fetch_sample().fetch(FakeContainer(files), dest, limit=2, registry=True, log=lambda *_: None)
    assert totals == {"runs": 1, "emails": 2, "files": 4, "missing": 1}  # newest run only, 2 emails, 1 attachment gone
    kept = json.loads((dest / "bronze/20261120T000000Z/emails.json").read_text())
    assert [m["id"] for m in kept["messages"]] == ["m1", "m2"]
    assert (dest / "attachments/x/1.pdf").read_bytes() == b"%PDF"
    assert (dest / "in/qualco_output_20261120.csv").read_bytes() == b"new"
    assert not (dest / "messages/aa/m3/message.eml").exists() and not (dest / "bronze/20261101T000000Z").exists()
    # The copy is a container the classifier reads as is.

