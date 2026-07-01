import base64
import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.cli import main as cli_main
from app.dbpr_parser import DbprParseError, parse_dbpr
from app.main import app
from app.text_export import build_amp_summary, build_gear_summary, render_equipment_text


def test_parse_and_summarize_dbpr(tmp_path):
    dbpr = make_sample_dbpr(tmp_path)

    data = parse_dbpr(dbpr)
    gear = {row.model: row.quantity for row in build_gear_summary(data)}
    amps = {row.model: row for row in build_amp_summary(data)}

    assert gear == {"Rama 2": 1, "V12": 2, "V8": 4}
    assert amps["D80"].quantity == 2
    assert amps["D80"].ids == ("0.21", "0.22")


def test_render_text(tmp_path):
    data = parse_dbpr(make_sample_dbpr(tmp_path))

    text = render_equipment_text(data, "sample")

    assert text == (
        "LISTA SPRZĘTU DBPR\n"
        "Projekt: sample\n"
        "\n"
        "SPRZĘT\n"
        "- Rama 2 x1\n"
        "- V12 x2\n"
        "- V8 x4\n"
        "\n"
        "KOŃCÓWKI\n"
        "- D80 x2 | ID: 0.21, 0.22\n"
    )


def test_api_parse_and_text_export(tmp_path):
    dbpr = make_sample_dbpr(tmp_path)
    client = TestClient(app)

    with dbpr.open("rb") as file:
        response = client.post(
            "/api/parse",
            files={"file": ("sample.dbpr", file, "application/octet-stream")},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["project_name"] == "sample"
    assert body["gear"] == [
        {"model": "Rama 2", "quantity": 1},
        {"model": "V12", "quantity": 2},
        {"model": "V8", "quantity": 4},
    ]
    assert body["amps"] == [{"model": "D80", "quantity": 2, "ids": ["0.21", "0.22"]}]

    with dbpr.open("rb") as file:
        response = client.post(
            "/api/equipment.txt",
            files={"file": ("sample.dbpr", file, "application/octet-stream")},
        )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain")
    assert "sample-lista-sprzetu.txt" in response.headers["content-disposition"]
    assert "- D80 x2 | ID: 0.21, 0.22\n" in response.text


def test_gpt_action_export_returns_openai_file_response(tmp_path, monkeypatch):
    dbpr = make_sample_dbpr(tmp_path)
    client = TestClient(app)

    def fake_download(download_link: str) -> bytes:
        assert download_link == "https://files.oaiusercontent.com/sample"
        return dbpr.read_bytes()

    monkeypatch.setattr("app.main._download_action_file", fake_download)

    response = client.post(
        "/api/actions/equipment",
        json={
            "openaiFileIdRefs": [
                {
                    "name": "sample.dbpr",
                    "id": "file-test",
                    "mime_type": "application/octet-stream",
                    "download_link": "https://files.oaiusercontent.com/sample",
                }
            ]
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["project_name"] == "sample"
    assert body["gear"] == [
        {"model": "Rama 2", "quantity": 1},
        {"model": "V12", "quantity": 2},
        {"model": "V8", "quantity": 4},
    ]

    file_response = body["openaiFileResponse"][0]
    assert file_response["name"] == "sample-lista-sprzetu.txt"
    assert file_response["mime_type"] == "text/plain"
    assert base64.b64decode(file_response["content"]).decode("utf-8") == body["text"]
    assert "- D80 x2 | ID: 0.21, 0.22\n" in body["text"]


def test_cli_writes_text_file(tmp_path):
    dbpr = make_sample_dbpr(tmp_path)
    output = tmp_path / "exports" / "lista.txt"

    exit_code = cli_main([str(dbpr), "-o", str(output)])

    assert exit_code == 0
    assert output.read_text(encoding="utf-8") == (
        "LISTA SPRZĘTU DBPR\n"
        "Projekt: sample\n"
        "\n"
        "SPRZĘT\n"
        "- Rama 2 x1\n"
        "- V12 x2\n"
        "- V8 x4\n"
        "\n"
        "KOŃCÓWKI\n"
        "- D80 x2 | ID: 0.21, 0.22\n"
    )


def test_rejects_non_dbpr(tmp_path):
    bad = tmp_path / "bad.dbpr"
    bad.write_text("not sqlite", encoding="utf-8")

    with pytest.raises(DbprParseError):
        parse_dbpr(bad)


def make_sample_dbpr(tmp_path: Path) -> Path:
    path = tmp_path / "sample.dbpr"
    conn = sqlite3.connect(path)
    try:
        conn.executescript(
            """
            CREATE TABLE ProjectInformation (
                ProjectName TEXT,
                AuthorName TEXT,
                AppVersionR1 TEXT,
                AppVersionArrayCalc TEXT
            );

            CREATE TABLE SourceGroups (
                SourceGroupId INTEGER PRIMARY KEY,
                Name TEXT,
                OrderIndex INTEGER
            );

            CREATE TABLE Cabinets (
                CabinetId INTEGER PRIMARY KEY,
                SourceGroupId INTEGER,
                DeviceId INTEGER,
                AmplifierChannel INTEGER
            );

            CREATE TABLE CabinetsAdditionalData (
                CabinetId INTEGER PRIMARY KEY,
                Name TEXT
            );

            CREATE TABLE FlyingFrames (
                Type INTEGER,
                SourceGroupId INTEGER,
                TotalWeight REAL,
                FrontPickPointWeight REAL,
                RearPickPointWeight REAL
            );

            CREATE TABLE Devices (
                DeviceId INTEGER PRIMARY KEY,
                Model TEXT,
                RemoteIdSubnet INTEGER,
                RemoteIdDevice INTEGER,
                Name TEXT
            );

            INSERT INTO ProjectInformation VALUES ('Untitled', 'tester', '3.12.0', '12.6.6');
            INSERT INTO SourceGroups VALUES (1, 'Main', 1);
            INSERT INTO SourceGroups VALUES (2, 'Unused channels', 99);

            INSERT INTO Cabinets VALUES (1, 1, 10, 1);
            INSERT INTO Cabinets VALUES (2, 1, 10, 2);
            INSERT INTO Cabinets VALUES (3, 1, 11, 1);
            INSERT INTO Cabinets VALUES (4, 1, 11, 2);
            INSERT INTO Cabinets VALUES (5, 1, 10, 3);
            INSERT INTO Cabinets VALUES (6, 1, 11, 3);
            INSERT INTO Cabinets VALUES (7, 2, 11, 4);

            INSERT INTO CabinetsAdditionalData VALUES (1, 'V8');
            INSERT INTO CabinetsAdditionalData VALUES (2, 'V8');
            INSERT INTO CabinetsAdditionalData VALUES (3, 'V8');
            INSERT INTO CabinetsAdditionalData VALUES (4, 'V8');
            INSERT INTO CabinetsAdditionalData VALUES (5, 'V12');
            INSERT INTO CabinetsAdditionalData VALUES (6, 'V12');
            INSERT INTO CabinetsAdditionalData VALUES (7, 'IGNORED');

            INSERT INTO FlyingFrames VALUES (2, 1, 120.0, 60.0, 60.0);

            INSERT INTO Devices VALUES (10, 'D80', 0, 21, 'Main 0.21');
            INSERT INTO Devices VALUES (11, 'D80', 0, 22, 'Main 0.22');
            """
        )
        conn.commit()
    finally:
        conn.close()
    return path
