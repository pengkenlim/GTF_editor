"""PyScript GTF (Gene Transfer Format) editor.

Loads a GTF/GFF file in the browser, shows it as an editable table backed by
a pandas DataFrame, and lets the user download the edited result. Everything
runs client-side in the browser via Pyodide - no server round trip.
"""

import io

import js
import pandas as pd
from pyodide.ffi import create_proxy
from pyscript import document, when

GTF_COLUMNS = [
    "seqname", "source", "feature", "start", "end",
    "score", "strand", "frame", "attribute",
]

# In-memory app state.
df = pd.DataFrame(columns=GTF_COLUMNS)
header_lines: list[str] = []
current_filename = "edited.gtf"

status_el = document.getElementById("status")
table_container = document.getElementById("table-container")
add_row_btn = document.getElementById("add-row-btn")
download_btn = document.getElementById("download-btn")


def set_status(message: str) -> None:
    status_el.innerHTML = f"<span>{message}</span>"


def parse_gtf(text: str) -> tuple[list[str], pd.DataFrame]:
    """Split a GTF/GFF file into its comment header lines and a data frame."""
    comments = []
    rows = []
    for line in text.splitlines():
        if not line.strip():
            continue
        if line.startswith("#"):
            comments.append(line)
            continue
        fields = line.split("\t")
        # Pad/truncate to the expected 9 GTF columns so malformed lines don't crash the table.
        fields = (fields + [""] * len(GTF_COLUMNS))[: len(GTF_COLUMNS)]
        rows.append(fields)
    frame = pd.DataFrame(rows, columns=GTF_COLUMNS)
    return comments, frame


def render_table() -> None:
    if df.empty:
        table_container.innerHTML = "<p>No rows loaded yet.</p>"
        return

    head = "".join(f"<th>{col}</th>" for col in GTF_COLUMNS) + "<th></th>"
    body_rows = []
    for row_idx, row in enumerate(df.itertuples(index=False)):
        cells = "".join(
            f'<td><input class="cell-input" data-row="{row_idx}" data-col="{col_idx}" value="{_escape(value)}"></td>'
            for col_idx, value in enumerate(row)
        )
        delete_cell = (
            f'<td class="row-actions">'
            f'<button class="delete-btn" data-row="{row_idx}" title="Delete row">&times;</button>'
            f"</td>"
        )
        body_rows.append(f"<tr>{cells}{delete_cell}</tr>")

    table_container.innerHTML = (
        f"<table><thead><tr>{head}</tr></thead><tbody>{''.join(body_rows)}</tbody></table>"
    )


def _escape(value) -> str:
    return (
        str(value)
        .replace("&", "&amp;")
        .replace('"', "&quot;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def _table_input_handler(event) -> None:
    target = event.target
    class_list = target.classList
    if not class_list.contains("cell-input"):
        return
    row_idx = int(target.dataset.row)
    col_idx = int(target.dataset.col)
    df.iat[row_idx, col_idx] = target.value


def _table_click_handler(event) -> None:
    target = event.target
    if not target.classList.contains("delete-btn"):
        return
    row_idx = int(target.dataset.row)
    delete_row(row_idx)


def delete_row(row_idx: int) -> None:
    global df
    df = df.drop(df.index[row_idx]).reset_index(drop=True)
    render_table()
    set_status(f"Deleted row {row_idx}. {len(df)} rows remaining.")


@when("click", "#add-row-btn")
def add_row(event=None) -> None:
    global df
    blank = {
        "seqname": "chr1", "source": "pyscript", "feature": "exon",
        "start": "1", "end": "1", "score": ".", "strand": "+",
        "frame": ".", "attribute": "",
    }
    df.loc[len(df)] = blank
    render_table()
    set_status(f"Added row. {len(df)} rows total.")


@when("change", "#file-input")
async def on_file_selected(event) -> None:
    global df, header_lines, current_filename
    files = event.target.files
    if not files or files.length == 0:
        return
    file = files.item(0)
    current_filename = file.name
    set_status(f"Reading {file.name}...")
    text = await file.text()
    header_lines, df = parse_gtf(text)
    render_table()
    add_row_btn.disabled = False
    download_btn.disabled = False
    set_status(f"Loaded {file.name}: {len(df)} feature rows, {len(header_lines)} header lines.")


@when("click", "#download-btn")
def download_gtf(event=None) -> None:
    lines = list(header_lines)
    for row in df.itertuples(index=False):
        lines.append("\t".join(str(value) for value in row))
    text = "\n".join(lines) + "\n"

    blob = js.Blob.new([text], {"type": "text/plain"})
    url = js.URL.createObjectURL(blob)
    anchor = js.document.createElement("a")
    anchor.href = url
    anchor.download = current_filename or "edited.gtf"
    anchor.click()
    js.URL.revokeObjectURL(url)
    set_status(f"Downloaded {anchor.download}.")


table_container.addEventListener("input", create_proxy(_table_input_handler))
table_container.addEventListener("click", create_proxy(_table_click_handler))

set_status("Ready. Choose a .gtf file to begin.")
