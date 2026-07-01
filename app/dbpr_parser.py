"""Standalone parser for d&b `.dbpr` project files.

The `.dbpr` file is a SQLite database. This module reads it in read-only mode
and extracts only the data needed by the small gear-list tool:

- loudspeaker models and quantities,
- amplifier models with project IDs,
- rigging frames.
"""

import sqlite3
from dataclasses import dataclass, field
from pathlib import Path

_UNUSED_GROUP = "Unused channels"

_QUERY_PROJECT_INFO = """
SELECT ProjectName, AuthorName, AppVersionR1, AppVersionArrayCalc
FROM ProjectInformation
LIMIT 1;
"""

_QUERY_GEAR = """
SELECT sg.Name        AS group_name,
       cad.Name       AS speaker_model,
       COUNT(*)       AS qty
FROM SourceGroups sg
JOIN Cabinets cab               ON sg.SourceGroupId = cab.SourceGroupId
JOIN CabinetsAdditionalData cad ON cab.CabinetId = cad.CabinetId
WHERE sg.Name != ?
GROUP BY sg.Name, cad.Name
ORDER BY sg.OrderIndex, cad.Name;
"""

_QUERY_FRAMES = """
SELECT ff.Type                 AS frame_type,
       sg.Name                 AS group_name,
       ff.TotalWeight          AS total_weight,
       ff.FrontPickPointWeight AS front_pick_weight,
       ff.RearPickPointWeight  AS rear_pick_weight
FROM FlyingFrames ff
JOIN SourceGroups sg ON ff.SourceGroupId = sg.SourceGroupId
ORDER BY sg.Name;
"""

_QUERY_AMPS = """
SELECT DeviceId, Model, Name, RemoteIdSubnet, RemoteIdDevice
FROM Devices
WHERE Model IS NOT NULL AND Model != ''
ORDER BY Model, RemoteIdSubnet, RemoteIdDevice, Name;
"""


@dataclass(frozen=True)
class ProjectInfo:
    project_name: str | None
    author_name: str | None
    app_version_r1: str | None
    app_version_arraycalc: str | None


@dataclass(frozen=True)
class GearItem:
    group_name: str
    speaker_model: str
    quantity: int


@dataclass(frozen=True)
class FrameItem:
    frame_type: str | None
    group_name: str
    total_weight: float | None
    front_pick_weight: float | None
    rear_pick_weight: float | None


@dataclass(frozen=True)
class AmpDevice:
    model: str
    name: str | None
    subnet: int | None
    device_id: int | None
    internal_id: int | None


@dataclass
class DbprData:
    project_info: ProjectInfo
    gear: list[GearItem] = field(default_factory=list)
    frames: list[FrameItem] = field(default_factory=list)
    amps: list[AmpDevice] = field(default_factory=list)


class DbprParseError(Exception):
    """Raised when a file is not a readable `.dbpr` SQLite database."""


def parse_dbpr(file_path: str | Path) -> DbprData:
    """Parse a `.dbpr` file without modifying it."""
    path = Path(file_path)
    uri = f"file:{path}?mode=ro"

    try:
        conn = sqlite3.connect(uri, uri=True)
    except sqlite3.OperationalError as exc:
        raise DbprParseError(f"Nie można otworzyć pliku: {exc}") from exc

    conn.row_factory = sqlite3.Row
    try:
        return _extract(conn)
    except sqlite3.DatabaseError as exc:
        raise DbprParseError(f"Plik nie jest poprawną bazą .dbpr: {exc}") from exc
    finally:
        conn.close()


def _extract(conn: sqlite3.Connection) -> DbprData:
    info_row = conn.execute(_QUERY_PROJECT_INFO).fetchone()
    project_info = ProjectInfo(
        project_name=info_row["ProjectName"] if info_row else None,
        author_name=info_row["AuthorName"] if info_row else None,
        app_version_r1=info_row["AppVersionR1"] if info_row else None,
        app_version_arraycalc=info_row["AppVersionArrayCalc"] if info_row else None,
    )

    gear = [
        GearItem(
            group_name=row["group_name"],
            speaker_model=row["speaker_model"],
            quantity=row["qty"],
        )
        for row in conn.execute(_QUERY_GEAR, (_UNUSED_GROUP,))
    ]

    frames = [
        FrameItem(
            frame_type=str(row["frame_type"]) if row["frame_type"] is not None else None,
            group_name=row["group_name"],
            total_weight=row["total_weight"],
            front_pick_weight=row["front_pick_weight"],
            rear_pick_weight=row["rear_pick_weight"],
        )
        for row in conn.execute(_QUERY_FRAMES)
    ]

    amps = [
        AmpDevice(
            model=row["Model"],
            name=row["Name"],
            subnet=row["RemoteIdSubnet"],
            device_id=row["RemoteIdDevice"],
            internal_id=row["DeviceId"],
        )
        for row in conn.execute(_QUERY_AMPS)
    ]

    return DbprData(project_info=project_info, gear=gear, frames=frames, amps=amps)
