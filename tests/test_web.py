"""Web plumbing tests via FastAPI TestClient — no model server required."""

import os
import subprocess
import sys
import textwrap

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from eyebrain.web.app import app  # noqa: E402

client = TestClient(app)


def test_cameras_endpoint():
    r = client.get("/api/cameras")
    assert r.status_code == 200
    body = r.json()
    assert "cameras" in body and "indexed_moments" in body


def test_ask_rejects_empty_question():
    r = client.post("/api/ask", json={"question": "   "})
    assert r.status_code == 400


def test_frame_unknown_camera_404():
    r = client.get("/api/frame", params={"camera": "nope", "t": 1.0})
    assert r.status_code == 404


def test_web_app_imports_without_vision_or_semantic_extras():
    env = os.environ.copy()
    env.pop("EYEBRAIN_EMBEDDER", None)
    env["EYEBRAIN_RETRIEVER"] = "local"
    code = textwrap.dedent(
        """
        import importlib
        import sys

        class BlockOptionalDeps:
            def find_spec(self, fullname, path=None, target=None):
                if fullname.split(".", 1)[0] in {"cv2", "fastembed"}:
                    raise ImportError(fullname)
                return None

        sys.meta_path.insert(0, BlockOptionalDeps())
        web_app = importlib.import_module("eyebrain.web.app")
        assert web_app.app.title == "eyebrain"
        """
    )
    subprocess.run([sys.executable, "-c", code], check=True, env=env, capture_output=True, text=True)
