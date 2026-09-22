"""PyScript GTF (Gene Transfer Format) editor.

Loads a GTF/GFF file in the browser, shows it as an editable table, and lets
users download the edited result. Everything runs client-side in the browser,
without pandas or any server-side code.
"""

import js
from pyodide.ffi import create_proxy
from pyscript import document, when

GTF_COLUMNS = [
    "seqname", "source", "feature", "start", "end",
    "score", "strand", "frame", "attribute",
]

# In-memory app state stored as a list of dictionaries for browser use.
rows: list[dict[str, str]] = []
header_lines: list[str] = []
current_filename = "edited.gtf"

status_el = document.getElementById("status")
table_container = document.getElementById("table-container")
add_row_btn = document.getElementById("add-row-btn")
download_btn = document.getElementById("download-btn")


def set_status(message: str) -> None:
    status_el.innerHTML = f"<span>{message}</span>"


def parse_gtf(text: str) -> tuple[list[str], list[dict[str, str]]]:
    """Split a GTF/GFF file into header lines and a list of row dictionaries."""
    comments = []
    parsed_rows = []
    for line in text.splitlines():
        if not line.strip():
            continue
        if line.startswith("#"):
            comments.append(line)
            continue
        fields = line.split("\t")
        fields = (fields + [""] * len(GTF_COLUMNS))[: len(GTF_COLUMNS)]
        parsed_rows.append({col: value for col, value in zip(GTF_COLUMNS, fields)})
    return comments, parsed_rows


def render_table() -> None:
    if not rows:
        table_container.innerHTML = "<p>No rows loaded yet.</p>"
        return

    head = "".join(f"<th>{col}</th>" for col in GTF_COLUMNS) + "<th></th>"
    body_rows = []
    for row_idx, row in enumerate(rows):
        cells = "".join(
            f'<td><input class="cell-input" data-row="{row_idx}" data-col="{col_idx}" value="{_escape(row.get(col, ""))}"></td>'
            for col_idx, col in enumerate(GTF_COLUMNS)
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
    if not target.classList.contains("cell-input"):
        return
    row_idx = int(target.dataset.row)
    col_idx = int(target.dataset.col)
    col_name = GTF_COLUMNS[col_idx]
    rows[row_idx][col_name] = target.value


def _table_click_handler(event) -> None:
    target = event.target
    if not target.classList.contains("delete-btn"):
        return
    row_idx = int(target.dataset.row)
    delete_row(row_idx)


def delete_row(row_idx: int) -> None:
    global rows
    if 0 <= row_idx < len(rows):
        del rows[row_idx]
    render_table()
    set_status(f"Deleted row {row_idx}. {len(rows)} rows remaining.")


@when("click", "#add-row-btn")
def add_row(event=None) -> None:
    global rows
    blank = {
        "seqname": "chr1", "source": "pyscript", "feature": "exon",
        "start": "1", "end": "1", "score": ".", "strand": "+",
        "frame": ".", "attribute": "",
    }
    rows.append(blank)
    render_table()
    set_status(f"Added row. {len(rows)} rows total.")


@when("change", "#file-input")
async def on_file_selected(event) -> None:
    global rows, header_lines, current_filename
    files = event.target.files
    if not files or files.length == 0:
        return
    file = files.item(0)
    current_filename = file.name
    set_status(f"Reading {file.name}...")
    text = await file.text()
    header_lines, rows = parse_gtf(text)
    render_table()
    add_row_btn.disabled = False
    download_btn.disabled = False
    set_status(f"Loaded {file.name}: {len(rows)} feature rows, {len(header_lines)} header lines.")


@when("click", "#download-btn")
def download_gtf(event=None) -> None:
    lines = list(header_lines)
    for row in rows:
        lines.append("\t".join(str(row.get(col, "")) for col in GTF_COLUMNS))
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
