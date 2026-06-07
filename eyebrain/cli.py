from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from eyebrain.embeddings import make_embedder
from eyebrain.index import MomentIndex
from eyebrain.ingest import ingest_video
from eyebrain.rag import build_cited_answer

app = typer.Typer(no_args_is_help=True)
console = Console()


@app.command()
def ingest(
    video: Annotated[Path, typer.Argument(help="Local video path on the camera node.")],
    camera_id: Annotated[str, typer.Option(help="Stable camera identifier.")],
    camera_name: Annotated[str | None, typer.Option(help="Human-friendly camera name.")] = None,
    captions: Annotated[Path | None, typer.Option(help="JSONL caption sidecar from a local vision model.")] = None,
    index_dir: Annotated[Path, typer.Option(help="Central compact index directory.")] = Path("data/index"),
    sample_every_sec: Annotated[float, typer.Option(min=0.25, help="Sampling interval for raw video.")] = 2.0,
    vision_model: Annotated[str | None, typer.Option(help="Optional local Ollama vision model.")] = None,
    embedder: Annotated[str, typer.Option(help="Embedding backend: hash or fastembed.")] = "hash",
    reset: Annotated[bool, typer.Option(help="Clear the current index before ingesting.")] = False,
) -> None:
    index = MomentIndex(index_dir=index_dir, embedder=make_embedder(embedder))
    if reset:
        index.clear()
    moments = ingest_video(
        video_path=video,
        camera_id=camera_id,
        camera_name=camera_name,
        sample_every_sec=sample_every_sec,
        captions_path=captions,
        vision_model=vision_model,
    )
    indexed = index.add_moments(moments)
    console.print(f"Indexed {len(indexed)} compact moments into {index.path}")


@app.command()
def ask(
    question: Annotated[str, typer.Argument(help="Natural-language security footage question.")],
    index_dir: Annotated[Path, typer.Option(help="Central compact index directory.")] = Path("data/index"),
    top_k: Annotated[int, typer.Option(min=1, max=20, help="Number of cited moments to retrieve.")] = 3,
    embedder: Annotated[str, typer.Option(help="Embedding backend: hash or fastembed.")] = "hash",
    json_output: Annotated[bool, typer.Option("--json", help="Print machine-readable JSON.")] = False,
) -> None:
    index = MomentIndex(index_dir=index_dir, embedder=make_embedder(embedder))
    answer = build_cited_answer(question, index.search(question, top_k=top_k))
    if json_output:
        console.print(answer.model_dump_json(indent=2))
        return

    console.print(Panel(answer.answer, title="eyebrain"))
    if answer.citations:
        table = Table(title="Citations")
        table.add_column("Score", justify="right")
        table.add_column("Camera")
        table.add_column("Time")
        table.add_column("Summary")
        for citation in answer.citations:
            table.add_row(
                f"{citation.score:.3f}",
                citation.camera_name or citation.camera_id,
                citation.time_range,
                citation.summary,
            )
        console.print(table)


@app.command("list")
def list_moments(
    index_dir: Annotated[Path, typer.Option(help="Central compact index directory.")] = Path("data/index"),
) -> None:
    index = MomentIndex(index_dir=index_dir)
    moments = index.load()
    table = Table(title=f"{len(moments)} indexed moments")
    table.add_column("Camera")
    table.add_column("Time")
    table.add_column("Summary")
    for moment in moments:
        table.add_row(moment.camera_name or moment.camera_id, moment.time_range, moment.summary)
    console.print(table)


if __name__ == "__main__":
    app()
