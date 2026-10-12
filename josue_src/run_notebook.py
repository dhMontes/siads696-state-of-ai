"""Execute preprocessing.ipynb with this Python environment and save its outputs."""

import argparse
import json
import os
from pathlib import Path
import sys
import tempfile

import nbformat
from nbclient import NotebookClient
from jupyter_client import KernelManager
from jupyter_client.kernelspec import KernelSpecManager

HERE = Path(__file__).resolve().parent


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, help="Optional source CSV path")
    parser.add_argument("--output", type=Path, help="Optional prepared-data folder")
    args = parser.parse_args()
    for name, value in (("SOURCE", args.source), ("OUTPUT", args.output)):
        if value is not None:
            os.environ["COMMON_INTAKE_" + name] = str(value.resolve())

    path = HERE / "preprocessing.ipynb"
    notebook = nbformat.read(path, as_version=4)

    # A temporary kernel uses this interpreter without changing installed kernels.
    with tempfile.TemporaryDirectory(prefix="common-notebook-") as temporary:
        kernels = Path(temporary)
        spec = kernels / "common-preparation"
        spec.mkdir()
        kernel = {
            "argv": [sys.executable, "-m", "ipykernel_launcher", "-f", "{connection_file}"],
            "display_name": "Python (common preparation)",
            "language": "python",
        }
        (spec / "kernel.json").write_text(json.dumps(kernel), encoding="utf-8")
        manager = KernelManager(
            kernel_name="common-preparation",
            kernel_spec_manager=KernelSpecManager(kernel_dirs=[str(kernels)]),
        )
        client = NotebookClient(
            notebook, timeout=300, km=manager,
            resources={"metadata": {"path": str(HERE)}},
        )
        try:
            client.execute()
        finally:
            if manager.has_kernel:
                manager.shutdown_kernel(now=True)

    # Save only after every cell succeeds; direct notebook edits are preserved.
    nbformat.validate(notebook)
    nbformat.write(notebook, path)
    cells = sum(cell.cell_type == "code" for cell in notebook.cells)
    print(f"Executed {cells} code cells and saved {path.name}.")


if __name__ == "__main__":
    main()
