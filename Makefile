.PHONY: setup ollama web ask test record-cam1 record-cam2 demo-placeholder clean-index

VENV=.venv/bin/activate

setup:  ## install all extras for the demo
	uv venv --python 3.11 || true
	. $(VENV) && uv pip install -e '.[dev,semantic,vision,web]'

ollama:  ## start the on-device model server (official app binary)
	/Applications/Ollama.app/Contents/Resources/ollama serve

web:  ## launch the demo web UI at http://127.0.0.1:8000
	. $(VENV) && EYEBRAIN_EMBEDDER=fastembed python -m eyebrain.web.app

ask:  ## one-off CLI query: make ask Q="When did the display get knocked over?"
	. $(VENV) && eyebrain ask "$(Q)" --embedder fastembed --top-k 5

test:
	. $(VENV) && python -m pytest -q

# --- demo footage ---
record-cam1:  ## record + on-device index camera 1 (resets the index)
	. $(VENV) && python scripts/record_camera.py --camera-id cam1 --name "Front Display" --seconds 30 --reset

record-cam2:  ## record + on-device index camera 2
	. $(VENV) && python scripts/record_camera.py --camera-id cam2 --name "Back Hallway" --seconds 30

demo-placeholder:  ## generate synthetic videos + index from caption sidecars (no webcam)
	. $(VENV) && python scripts/make_placeholder_videos.py

clean-index:  ## wipe the local index + registry
	rm -f data/index/moments.jsonl data/index/embeddings.npy data/index/cameras.json
