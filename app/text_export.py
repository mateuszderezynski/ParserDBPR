"""Summaries and text output for parsed DBPR data."""

from dataclasses import dataclass

from app.dbpr_parser import AmpDevice, DbprData


@dataclass(frozen=True)
class EquipmentRow:
    model: str
    quantity: int


@dataclass(frozen=True)
class EquipmentGroup:
    name: str
    quantity: int
    rows: tuple[EquipmentRow, ...]


@dataclass(frozen=True)
class AmpRow:
    model: str
    quantity: int
    ids: tuple[str, ...]


def build_gear_summary(data: DbprData) -> list[EquipmentRow]:
    rows: dict[str, int] = {}

    for item in data.gear:
        rows[item.speaker_model] = rows.get(item.speaker_model, 0) + item.quantity

    for frame in data.frames:
        model = f"Rama {frame.frame_type or '?'}"
        rows[model] = rows.get(model, 0) + 1

    return [
        EquipmentRow(model=model, quantity=quantity)
        for model, quantity in sorted(rows.items(), key=lambda item: _model_key(item[0]))
    ]


def build_gear_groups(data: DbprData) -> list[EquipmentGroup]:
    groups: dict[str, dict] = {}

    for item in data.gear:
        group = _ensure_group(groups, item.group_name, item.group_order)
        rows = group["rows"]
        rows[item.speaker_model] = rows.get(item.speaker_model, 0) + item.quantity

    for frame in data.frames:
        group = _ensure_group(groups, frame.group_name, frame.group_order)
        rows = group["rows"]
        model = f"Rama {frame.frame_type or '?'}"
        rows[model] = rows.get(model, 0) + 1

    grouped_rows: list[EquipmentGroup] = []
    for group in sorted(groups.values(), key=lambda item: (item["order"], item["name"])):
        rows = tuple(
            EquipmentRow(model=model, quantity=quantity)
            for model, quantity in sorted(
                group["rows"].items(),
                key=lambda item: _model_key(item[0]),
            )
        )
        grouped_rows.append(
            EquipmentGroup(
                name=group["name"],
                quantity=sum(row.quantity for row in rows),
                rows=rows,
            )
        )

    return grouped_rows


def build_amp_summary(data: DbprData) -> list[AmpRow]:
    rows: dict[str, list[str]] = {}

    for amp in data.amps:
        rows.setdefault(amp.model, []).append(format_amp_id(amp))

    return [
        AmpRow(model=model, quantity=len(ids), ids=tuple(sorted(ids, key=_id_key)))
        for model, ids in sorted(rows.items(), key=lambda item: _model_key(item[0]))
    ]


def render_equipment_text(data: DbprData, project_name: str | None = None) -> str:
    lines: list[str] = ["LISTA SPRZĘTU DBPR"]
    if project_name:
        lines.append(f"Projekt: {project_name}")

    lines.append("")
    lines.append("SPRZĘT WG GRUP")
    gear_groups = build_gear_groups(data)
    if gear_groups:
        for index, group in enumerate(gear_groups):
            if index:
                lines.append("")
            lines.append(f"{group.name} ({group.quantity} szt.)")
            lines.extend(f"- {row.model} x{row.quantity}" for row in group.rows)
    else:
        lines.append("- brak")

    lines.append("")
    lines.append("PODSUMOWANIE MODELI")
    gear_rows = build_gear_summary(data)
    if gear_rows:
        lines.extend(f"- {row.model} x{row.quantity}" for row in gear_rows)
    else:
        lines.append("- brak")

    lines.append("")
    lines.append("KOŃCÓWKI")
    amp_rows = build_amp_summary(data)
    if amp_rows:
        lines.extend(
            f"- {row.model} x{row.quantity} | ID: {', '.join(row.ids)}" for row in amp_rows
        )
    else:
        lines.append("- brak")

    return "\n".join(lines) + "\n"


def _ensure_group(groups: dict[str, dict], name: str, order: int) -> dict:
    key = name.strip().casefold()
    if key not in groups:
        groups[key] = {
            "name": name,
            "order": order,
            "rows": {},
        }
    return groups[key]


def format_amp_id(amp: AmpDevice) -> str:
    if amp.subnet is not None and amp.device_id is not None:
        return f"{amp.subnet}.{amp.device_id}"
    if amp.internal_id is not None:
        return f"wew.{amp.internal_id}"
    return "brak ID"


def _model_key(model: str) -> tuple[str, str]:
    return (model.casefold(), model)


def _id_key(value: str) -> tuple[int, int, str]:
    subnet, _, device = value.partition(".")
    if subnet.isdigit() and device.isdigit():
        return (int(subnet), int(device), value)
    return (9999, 9999, value)
