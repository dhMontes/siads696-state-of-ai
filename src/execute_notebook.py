"""Execute a saved notebook with progress, saving partial output if a cell fails."""
import argparse
import sys
from pathlib import Path
import nbformat
from nbclient import NotebookClient
from nbconvert import HTMLExporter


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("notebook", type=Path)
    parser.add_argument("--html", type=Path)
    args = parser.parse_args()
    path = args.notebook.resolve()
    nb = nbformat.read(path, as_version=4)
    def progress(cell, cell_index, **kwargs):
        if cell.cell_type == "code":
            print(f"Executing cell {cell_index}: {cell.source.splitlines()[0][:100]}", flush=True)
    client = NotebookClient(nb, timeout=1800, resources={"metadata": {"path": str(path.parent)}},
                            on_cell_start=progress)
    try:
        client.execute()
    finally:
        nbformat.write(nb, path)
    if args.html:
        args.html.parent.mkdir(parents=True, exist_ok=True)
        # A venv may use system-site packages whose templates live under base_prefix.
        templates = Path(sys.base_prefix) / "share/jupyter/nbconvert/templates"
        exporter = HTMLExporter(extra_template_basedirs=[str(templates)],
                                extra_template_paths=[str(templates)])
        body, _ = exporter.from_notebook_node(nb)
        args.html.write_text(body, encoding="utf-8")
    print("Completed notebook execution and export.", flush=True)


if __name__ == "__main__":
    main()
