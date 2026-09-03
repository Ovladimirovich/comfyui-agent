"""M2 tests — Asset Layer (media-agnostic, локальный, без ComfyUI/Provider/LLM).

Тесты используют реальную файловую систему (tmp_path), не mock.
"""
import os

import pytest

from app.assets import Asset, AssetStore, PathSecurityError, SizeLimitError, AssetNotFoundError


def _mk(tmp_path, name, content=b"x" * 5):
    p = tmp_path / name
    p.write_bytes(content)
    return p


def test_asset_creation(tmp_path):
    store = AssetStore(root=tmp_path / "data" / "assets")
    f = _mk(tmp_path, "photo.png", b"hello")
    a = store.ingest(f, type="image")
    assert a.id != "photo.png"            # identity != filename
    assert a.type == "image"
    assert a.mime in ("image/png", None)
    assert a.path.endswith("photo.png")
    assert store.exists(a.id)
    assert isinstance(a, Asset)


def test_persistence_and_restart(tmp_path):
    root = tmp_path / "data" / "assets"
    s1 = AssetStore(root=root)
    f = _mk(tmp_path, "a.png", b"data")
    a = s1.ingest(f, type="image")
    # новый экземпляр того же root — registry восстанавливается из JSONL
    s2 = AssetStore(root=root)
    b = s2.get(a.id)
    assert b is not None and b.id == a.id and b.type == "image"
    assert (tmp_path / "data" / "assets.jsonl").exists()


def test_multiple_media_types(tmp_path):
    store = AssetStore(root=tmp_path / "data" / "assets")
    img = _mk(tmp_path, "i.png", b"1")
    vid = _mk(tmp_path, "v.mp4", b"2")
    aud = _mk(tmp_path, "a.wav", b"3")
    ai = store.ingest(img, type="image")
    av = store.ingest(vid, type="video")
    aa = store.ingest(aud, type="audio")
    assert {ai.type, av.type, aa.type} == {"image", "video", "audio"}
    # один и тот же API, без подклассов
    assert all(type(x) is Asset for x in (ai, av, aa))


def test_architecture_media_agnostic(tmp_path):
    store = AssetStore(root=tmp_path / "data" / "assets")
    for t in ("image", "video", "audio", "mask", "sequence", "document", "other", "custom_x"):
        f = _mk(tmp_path, t + ".bin", b"0")
        a = store.ingest(f, type=t)
        assert isinstance(a, Asset)   # без ветвления и подклассов
        assert a.type == t


def test_lineage(tmp_path):
    store = AssetStore(root=tmp_path / "data" / "assets")
    f = _mk(tmp_path, "x.png", b"data")
    A = store.ingest(f, type="image", role="input")
    B = store.link(A.id, type="image", role="output", created_from="job1")
    C = store.link(B.id, type="image", role="output", created_from="job2")
    assert C.source_asset == B.id and B.source_asset == A.id
    chain = store.lineage(C.id)
    assert [x.id for x in chain] == [C.id, B.id, A.id]


def test_security_traversal(tmp_path):
    store = AssetStore(root=tmp_path / "data" / "assets")
    f = _mk(tmp_path, "ok.png", b"data")
    with pytest.raises(PathSecurityError):
        store.ingest(f, type="image", stored_name="../../evil.png")


def test_security_absolute(tmp_path):
    store = AssetStore(root=tmp_path / "data" / "assets")
    f = _mk(tmp_path, "ok.png", b"data")
    with pytest.raises(PathSecurityError):
        store.ingest(f, type="image", stored_name="/etc/passwd")


def test_security_symlink(tmp_path):
    store = AssetStore(root=tmp_path / "data" / "assets")
    f = _mk(tmp_path, "ok.png", b"data")
    outside = tmp_path / "outside_dir"
    outside.mkdir()
    link_dir = tmp_path / "data" / "assets" / "evil_link"
    try:
        os.symlink(outside, link_dir)
    except (OSError, NotImplementedError, PermissionError):
        pytest.skip("symlinks не поддерживаются на этой платформе")
    with pytest.raises(PathSecurityError):
        store.ingest(f, type="image", stored_name="evil_link/../../escape.png")


def test_size_limit(tmp_path):
    store = AssetStore(root=tmp_path / "data" / "assets", max_upload_bytes=10)
    big = _mk(tmp_path, "big.png", b"x" * 100)
    with pytest.raises(SizeLimitError):
        store.ingest(big, type="image")
    small = _mk(tmp_path, "small.png", b"x" * 5)
    a = store.ingest(small, type="image")
    assert a is not None


def test_delete(tmp_path):
    store = AssetStore(root=tmp_path / "data" / "assets")
    f = _mk(tmp_path, "d.png", b"data")
    a = store.ingest(f, type="image")
    p = a.path
    store.delete(a.id)
    assert not store.exists(a.id)
    assert not os.path.exists(p)


def test_not_found(tmp_path):
    store = AssetStore(root=tmp_path / "data" / "assets")
    with pytest.raises(AssetNotFoundError):
        store.delete("nope")
    assert store.get("nope") is None
