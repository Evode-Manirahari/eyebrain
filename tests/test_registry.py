from eyebrain.web.registry import CameraRegistry


def test_register_and_roundtrip(tmp_path):
    reg = CameraRegistry()
    reg.register("cam1", "/tmp/cam1.mp4", "Front Display")
    reg.register("cam2", "/tmp/cam2.mp4")
    reg.save(index_dir=tmp_path)

    loaded = CameraRegistry.load(index_dir=tmp_path)
    assert set(loaded.cameras) == {"cam1", "cam2"}
    assert loaded.get("cam1").camera_name == "Front Display"
    assert loaded.get("cam1").video_path == "/tmp/cam1.mp4"
    assert loaded.get("cam2").camera_name is None
    assert loaded.get("missing") is None


def test_load_missing_returns_empty(tmp_path):
    reg = CameraRegistry.load(index_dir=tmp_path)
    assert reg.cameras == {}
