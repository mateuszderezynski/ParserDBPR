"""Standalone DBPR gear-list web app."""

import base64
import tempfile
from dataclasses import asdict
from typing import Any
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlparse
from urllib.request import Request, urlopen

from fastapi import FastAPI, HTTPException, UploadFile
from fastapi.responses import FileResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from app.dbpr_parser import DbprData, DbprParseError, parse_dbpr
from app.text_export import build_amp_summary, build_gear_summary, render_equipment_text

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
MAX_ACTION_FILE_BYTES = 25 * 1024 * 1024
DOWNLOAD_TIMEOUT_SECONDS = 20


class ActionEquipmentRequest(BaseModel):
    openaiFileIdRefs: list[dict[str, Any]] = Field(
        default_factory=list,
        description=(
            "GPT Actions file references. Runtime values are objects with name, id, "
            "mime_type, and download_link."
        ),
    )

app = FastAPI(
    title="DBPR Gear Tool",
    description="Samodzielny parser `.dbpr` -> lista sprzętu i końcówek.",
    version="1.0.0",
)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/parse")
async def parse_upload(file: UploadFile) -> dict:
    data, project_name = await _parse_upload(file)
    return {
        "project_name": project_name,
        "project_info": asdict(data.project_info),
        "gear": [asdict(row) for row in build_gear_summary(data)],
        "amps": [asdict(row) for row in build_amp_summary(data)],
        "text": render_equipment_text(data, project_name),
    }


@app.post("/api/equipment.txt")
async def export_txt(file: UploadFile) -> PlainTextResponse:
    data, project_name = await _parse_upload(file)
    filename = _txt_filename(project_name)
    return PlainTextResponse(
        render_equipment_text(data, project_name),
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}",
        },
    )


@app.post("/api/actions/equipment")
def action_export_equipment(request: ActionEquipmentRequest) -> dict:
    filename, download_link = _select_action_dbpr_file(request.openaiFileIdRefs)
    data = _parse_dbpr_bytes(_download_action_file(download_link), Path(filename).suffix)
    project_name = Path(filename).stem
    text = render_equipment_text(data, project_name)
    output_name = _txt_filename(project_name)

    return {
        "project_name": project_name,
        "project_info": asdict(data.project_info),
        "gear": [asdict(row) for row in build_gear_summary(data)],
        "amps": [asdict(row) for row in build_amp_summary(data)],
        "text": text,
        "openaiFileResponse": [
            {
                "name": output_name,
                "mime_type": "text/plain",
                "content": base64.b64encode(text.encode("utf-8")).decode("ascii"),
            }
        ],
    }


async def _parse_upload(file: UploadFile) -> tuple[DbprData, str]:
    if not file.filename or not file.filename.lower().endswith(".dbpr"):
        raise HTTPException(status_code=400, detail="Oczekiwano pliku .dbpr")

    data = _parse_dbpr_bytes(await file.read(), Path(file.filename).suffix)

    return data, Path(file.filename).stem


def _parse_dbpr_bytes(content: bytes, suffix: str = ".dbpr") -> DbprData:
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=True) as tmp:
        tmp.write(content)
        tmp.flush()
        try:
            return parse_dbpr(tmp.name)
        except DbprParseError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc


def _select_action_dbpr_file(file_refs: list[dict[str, Any]]) -> tuple[str, str]:
    if not file_refs:
        raise HTTPException(status_code=400, detail="Brakuje openaiFileIdRefs z plikiem .dbpr")

    dbpr_refs = [
        file_ref
        for file_ref in file_refs
        if str(file_ref.get("name") or "").lower().endswith(".dbpr")
    ]
    file_ref = dbpr_refs[0] if dbpr_refs else file_refs[0]

    filename = str(file_ref.get("name") or "")
    download_link = str(file_ref.get("download_link") or "")
    if not filename.lower().endswith(".dbpr"):
        raise HTTPException(status_code=400, detail="Oczekiwano pliku .dbpr")
    if not download_link:
        raise HTTPException(status_code=400, detail="Brakuje download_link dla pliku .dbpr")

    return filename, download_link


def _download_action_file(download_link: str) -> bytes:
    parsed = urlparse(download_link)
    if parsed.scheme != "https":
        raise HTTPException(status_code=400, detail="download_link musi używać HTTPS")

    request = Request(download_link, headers={"User-Agent": "dbpr-gear-tool/1.0"})
    chunks: list[bytes] = []
    total = 0

    try:
        with urlopen(request, timeout=DOWNLOAD_TIMEOUT_SECONDS) as response:
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break

                total += len(chunk)
                if total > MAX_ACTION_FILE_BYTES:
                    raise HTTPException(status_code=413, detail="Plik .dbpr jest za duży")

                chunks.append(chunk)
    except HTTPException:
        raise
    except (HTTPError, URLError, TimeoutError, OSError) as exc:
        raise HTTPException(status_code=502, detail=f"Nie można pobrać pliku: {exc}") from exc

    return b"".join(chunks)


def _txt_filename(project_name: str) -> str:
    safe = "".join(ch if ch.isalnum() or ch in ("-", "_") else "-" for ch in project_name)
    safe = "-".join(part for part in safe.split("-") if part)
    return f"{safe or 'dbpr'}-lista-sprzetu.txt"
