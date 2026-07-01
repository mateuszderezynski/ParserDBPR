"""Standalone DBPR gear-list web app."""

import tempfile
from dataclasses import asdict
from pathlib import Path
from urllib.parse import quote

from fastapi import FastAPI, HTTPException, UploadFile
from fastapi.responses import FileResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles

from app.dbpr_parser import DbprData, DbprParseError, parse_dbpr
from app.text_export import build_amp_summary, build_gear_summary, render_equipment_text

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"

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


async def _parse_upload(file: UploadFile) -> tuple[DbprData, str]:
    if not file.filename or not file.filename.lower().endswith(".dbpr"):
        raise HTTPException(status_code=400, detail="Oczekiwano pliku .dbpr")

    suffix = Path(file.filename).suffix
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=True) as tmp:
        tmp.write(await file.read())
        tmp.flush()
        try:
            data = parse_dbpr(tmp.name)
        except DbprParseError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    return data, Path(file.filename).stem


def _txt_filename(project_name: str) -> str:
    safe = "".join(ch if ch.isalnum() or ch in ("-", "_") else "-" for ch in project_name)
    safe = "-".join(part for part in safe.split("-") if part)
    return f"{safe or 'dbpr'}-lista-sprzetu.txt"
