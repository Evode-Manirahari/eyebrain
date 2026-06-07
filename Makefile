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

# --- Moss sidecar (runs Moss in Linux x86_64; the Mac talks to it over HTTP) ---
moss-build:  ## build the Moss sidecar image
	docker build --platform linux/amd64 -t eyebrain-moss ./moss_sidecar

moss-up:  ## run the Moss sidecar (reads Moss creds from .env)
	docker run -d --rm --name eyebrain-moss -p 8077:8077 --env-file .env eyebrain-moss
	@echo "waiting for sidecar..."; until curl -sf http://127.0.0.1:8077/health >/dev/null; do sleep 1; done; echo "moss sidecar up"

moss-down:  ## stop the Moss sidecar
	-docker stop eyebrain-moss

moss-sync:  ## push the local index into Moss (run after ingesting cameras)
	. $(VENV) && python scripts/sync_to_moss.py --reset

web-moss:  ## launch the web UI backed by Moss retrieval
	. $(VENV) && EYEBRAIN_RETRIEVER=moss EYEBRAIN_EMBEDDER=fastembed python -m eyebrain.web.app
