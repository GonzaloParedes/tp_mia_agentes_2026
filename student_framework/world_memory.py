from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass, field
from typing import Any


_ID_PATTERN = re.compile(r"\[id:\s*([^\]]+)\]")
_ITEM_WITH_ID_PATTERN = re.compile(r"-\s*([^\[\n]+?)\s*\[id:\s*([^\]]+)\]")


def _without_accents(text: str) -> str:
    return "".join(
        char
        for char in unicodedata.normalize("NFKD", text)
        if not unicodedata.combining(char)
    )


def _lower_plain(text: str) -> str:
    return _without_accents(text).lower()


def _match_key(text: str) -> str:
    return re.sub(r"\s+", " ", _lower_plain(text).replace("_", " ")).strip()


def _tool_args(raw: str | None) -> dict[str, Any]:
    if not raw:
        return {}
    try:
        value = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return value if isinstance(value, dict) else {}


@dataclass
class RoomMemory:
    exits: set[str] = field(default_factory=set)
    blocked_exits: dict[str, str] = field(default_factory=dict)
    objects: set[str] = field(default_factory=set)


@dataclass
class FailedAction:
    tool: str
    args: dict[str, Any]
    reason: str


class WorldMemory:
    """Memoria estructurada liviana para mundos tipo sala de escape.

    No intenta modelar todo el mundo. Solo extrae hechos observables de los
    outputs de `look`, `examine`, `take`, `use` y `go` para recordarselos al
    LLM de forma compacta en la siguiente iteracion.
    """

    def __init__(self, *, max_failed_actions: int = 5, max_recent_calls: int = 8) -> None:
        self.current_room: str | None = None
        self.rooms: dict[str, RoomMemory] = {}
        self.inventory: set[str] = set()
        self.inventory_known = False
        self.object_locations: dict[str, set[str]] = {}
        self.item_labels: dict[str, str] = {}
        self.target_requirements: dict[str, set[str]] = {}
        self.revealed_not_taken: set[str] = set()
        self.opened: set[str] = set()
        self.failed_actions: list[FailedAction] = []
        self.recent_calls: list[tuple[str, str | None]] = []
        self._max_failed_actions = max_failed_actions
        self._max_recent_calls = max_recent_calls

    def validate_action(self, *, tool_name: str | None, tool_input: str | None) -> str | None:
        if tool_name is None:
            return None

        args = _tool_args(tool_input)
        if tool_name == "go":
            direction = args.get("direction")
            room = self._room()
            pending_items = self._revealed_not_taken_in_current_room()
            if pending_items:
                pending = ", ".join(sorted(pending_items))
                return (
                    "Error: memoria estructurada: antes de moverte, toma los "
                    f"objetos revelados en {self.current_room}: {pending}."
                )
            if (
                isinstance(direction, str)
                and self.current_room is not None
                and room is not None
                and room.exits
                and direction not in room.exits
            ):
                exits_list = sorted(room.exits)
                exits = ", ".join(exits_list)
                if len(exits_list) == 1:
                    return (
                        f"Error: memoria estructurada: desde {self.current_room} "
                        f"no existe salida {direction!r}. La unica salida conocida "
                        f"es {exits_list[0]!r}; usa `go` con "
                        f'{{"direction": "{exits_list[0]}"}}.'
                    )
                return (
                    f"Error: memoria estructurada: desde {self.current_room} "
                    f"no existe salida {direction!r}. Salidas conocidas: {exits}."
                )
            return None

        if tool_name == "use":
            item = args.get("item")
            target = args.get("target")
            if isinstance(item, str):
                if item in self.revealed_not_taken:
                    return (
                        f"Error: memoria estructurada: {item!r} fue revelado "
                        "pero no esta en el inventario. Primero usa `take`."
                    )
                if self.inventory_known and item not in self.inventory:
                    correction = self._inventory_id_correction(item)
                    if correction is not None:
                        item_id, label = correction
                        return (
                            f"Error: memoria estructurada: {item!r} no esta en el "
                            f"inventario observado. Quizas quisiste usar {item_id!r} "
                            f"({label}). Usa el id exacto devuelto por las herramientas."
                        )
                    return (
                        f"Error: memoria estructurada: {item!r} no esta en el "
                        "inventario observado. Primero busca y toma ese item."
                    )
            if isinstance(target, str):
                return self._validate_target_visible(target)
            return None

        if tool_name == "take":
            item = args.get("item")
            if isinstance(item, str):
                return self._validate_target_visible(item)
            return None

        if tool_name == "examine":
            target = args.get("target")
            if isinstance(target, str):
                return self._validate_target_visible(target)
            return None

        return None

    def update(
        self,
        *,
        tool_name: str | None,
        tool_input: str | None,
        tool_output: str | None,
        error: str | None,
    ) -> None:
        if tool_name is None:
            return

        args = _tool_args(tool_input)
        output = tool_output or ""
        output_plain = _lower_plain(output)
        call_key = (tool_name, tool_input)
        self.recent_calls.append(call_key)
        self.recent_calls = self.recent_calls[-self._max_recent_calls :]

        if error is not None or output.startswith("Error:"):
            self._remember_failed_action(tool_name, args, error or output)
            return

        if tool_name == "look":
            self._update_from_location_text(output)
            self._update_visible_objects(output)
            self._update_exits(output)
            self.inventory_known = True
            self._update_inventory(output)
            return

        if tool_name == "go":
            self._update_from_location_text(output)
            return

        if tool_name == "examine":
            self._update_revealed_items(output)
            return

        if tool_name == "take":
            item = args.get("item")
            if isinstance(item, str):
                self.inventory_known = True
                self.inventory.add(item)
                self.revealed_not_taken.discard(item)
            return

        if tool_name == "use":
            target = args.get("target")
            if isinstance(target, str):
                missing = self._parse_missing_requirements(output_plain)
                if missing:
                    self.target_requirements[target] = missing
            if isinstance(target, str) and (
                "se abre" in output_plain
                or "esta abierta" in output_plain
                or "ya esta abierta" in output_plain
                or "era la ultima pieza" in output_plain
            ):
                self.opened.add(target)
                self.target_requirements.pop(target, None)

    def to_prompt(self) -> str:
        lines = ["Memoria estructurada observada del entorno:"]
        if self.current_room:
            lines.append(f"- Sala actual: {self.current_room}")
        if self.inventory:
            lines.append(f"- Inventario observado: {', '.join(sorted(self.inventory))}")
        if self.revealed_not_taken:
            lines.append(
                "- Objetos revelados pero no tomados: "
                + ", ".join(sorted(self.revealed_not_taken))
            )
        if self.opened:
            lines.append(f"- Objetos abiertos: {', '.join(sorted(self.opened))}")

        if self.current_room and self.current_room in self.rooms:
            room = self.rooms[self.current_room]
            if room.objects:
                lines.append(
                    "- Objetos conocidos en sala actual: "
                    + ", ".join(sorted(room.objects))
                )
            if room.exits:
                lines.append(
                    "- Salidas conocidas de sala actual: "
                    + ", ".join(sorted(room.exits))
                )
            if room.blocked_exits:
                blocked = ", ".join(
                    f"{direction} bloqueada por {target}"
                    for direction, target in sorted(room.blocked_exits.items())
                )
                lines.append(f"- Salidas bloqueadas conocidas: {blocked}")

        if self.failed_actions:
            failed = []
            for action in self.failed_actions[-self._max_failed_actions :]:
                failed.append(
                    f"{action.tool}({json.dumps(action.args, ensure_ascii=False)}) -> {action.reason}"
                )
            lines.append("- Acciones fallidas recientes: " + " | ".join(failed))

        suggestion = self._next_step_suggestion()
        if suggestion:
            lines.append(f"- Siguiente objetivo sugerido: {suggestion}")

        repeated = self._last_repeated_call()
        if repeated is not None:
            tool_name, tool_input = repeated
            lines.append(f"- Ultima llamada repetida detectada: {tool_name} {tool_input}")

        if len(lines) == 1:
            lines.append("- Sin observaciones estructuradas todavia.")
        return "\n".join(lines)

    def _room(self) -> RoomMemory | None:
        if self.current_room is None:
            return None
        return self.rooms.setdefault(self.current_room, RoomMemory())

    def _remember_failed_action(self, tool_name: str, args: dict[str, Any], reason: str) -> None:
        self.failed_actions.append(FailedAction(tool=tool_name, args=args, reason=reason))
        self.failed_actions = self.failed_actions[-self._max_failed_actions :]

    def _update_from_location_text(self, output: str) -> None:
        for pattern in (r"Est[aá]s en ([^.]+)\.", r"Llegas a ([^.]+)\."):
            match = re.search(pattern, output)
            if match:
                self.current_room = match.group(1).strip()
                self.rooms.setdefault(self.current_room, RoomMemory())
                return
        normalized = _without_accents(output)
        for pattern in (r"Estas en ([^.]+)\.", r"Llegas a ([^.]+)\."):
            match = re.search(pattern, normalized)
            if match:
                self.current_room = match.group(1).strip()
                self.rooms.setdefault(self.current_room, RoomMemory())
                return

    def _update_visible_objects(self, output: str) -> None:
        room = self._room()
        if room is None:
            return
        self._remember_item_labels(output)
        for item_id in _ID_PATTERN.findall(output):
            item_id = item_id.strip()
            room.objects.add(item_id)
            self._remember_object_location(item_id)

    def _update_exits(self, output: str) -> None:
        room = self._room()
        if room is None:
            return
        match = re.search(r"Salidas:\s*(.+)\.", output)
        if not match:
            return
        for raw_part in match.group(1).split(","):
            part = raw_part.strip()
            blocked = re.match(r"([^\s]+)\s+\(bloqueada por ([^)]+)\)", part)
            if blocked:
                direction = blocked.group(1).strip()
                room.exits.add(direction)
                room.blocked_exits[direction] = blocked.group(2).strip()
            elif part:
                room.exits.add(part)

    def _update_inventory(self, output: str) -> None:
        match = re.search(r"Llevas:\s*(.+)\.", output)
        if not match:
            return
        self._remember_item_labels(match.group(1))
        for item_id in _ID_PATTERN.findall(match.group(1)):
            item_id = item_id.strip()
            self.inventory.add(item_id)
            self.revealed_not_taken.discard(item_id)

    def _update_revealed_items(self, output: str) -> None:
        ids = [item_id.strip() for item_id in _ID_PATTERN.findall(output)]
        if not ids:
            return
        self._remember_item_labels(output)
        room = self._room()
        for item_id in ids:
            if item_id not in self.inventory:
                self.revealed_not_taken.add(item_id)
            if room is not None:
                room.objects.add(item_id)
                self._remember_object_location(item_id)

    def _last_repeated_call(self) -> tuple[str, str | None] | None:
        if len(self.recent_calls) < 2:
            return None
        if self.recent_calls[-1] == self.recent_calls[-2]:
            return self.recent_calls[-1]
        return None

    def _remember_object_location(self, item_id: str) -> None:
        if self.current_room is None:
            return
        self.object_locations.setdefault(item_id, set()).add(self.current_room)

    def _remember_item_labels(self, output: str) -> None:
        for label, item_id in _ITEM_WITH_ID_PATTERN.findall(output):
            self.item_labels[item_id.strip()] = label.strip()

    def _parse_missing_requirements(self, output_plain: str) -> set[str]:
        match = re.search(
            r"todavia faltan (?:piezas|objetos|items|condiciones):\s*([^.]+)",
            output_plain,
        )
        if not match:
            return set()
        raw_items = re.split(r",|\sy\s", match.group(1))
        return {item.strip() for item in raw_items if item.strip()}

    def _revealed_not_taken_in_current_room(self) -> set[str]:
        if self.current_room is None:
            return set()
        return {
            item_id
            for item_id in self.revealed_not_taken
            if self.current_room in self.object_locations.get(item_id, set())
        }

    def _next_step_suggestion(self) -> str | None:
        for target, requirements in sorted(self.target_requirements.items()):
            if target in self.opened:
                continue
            requirement_ids = self._inventory_ids_for_requirements(requirements)
            if len(requirement_ids) != len(requirements):
                continue

            target_locations = self.object_locations.get(target)
            if not target_locations:
                continue

            target_room = sorted(target_locations)[0]
            pending_uses = ", ".join(
                f'use {{"item": "{item_id}", "target": "{target}"}}'
                for item_id in sorted(requirement_ids)
            )
            if self.current_room != target_room:
                return (
                    f"volver a {target_room}, donde esta {target}, y usar los "
                    f"items requeridos: {pending_uses}."
                )
            return f"usar los items requeridos sobre {target}: {pending_uses}."
        return None

    def _inventory_ids_for_requirements(self, requirements: set[str]) -> set[str]:
        found: set[str] = set()
        inventory_by_key: dict[str, str] = {}
        for item_id in self.inventory:
            inventory_by_key[_match_key(item_id)] = item_id
            label = self.item_labels.get(item_id)
            if label:
                inventory_by_key[_match_key(label)] = item_id

        for requirement in requirements:
            item_id = inventory_by_key.get(_match_key(requirement))
            if item_id is not None:
                found.add(item_id)
        return found

    def _inventory_id_correction(self, requested_item: str) -> tuple[str, str] | None:
        requested_key = _match_key(requested_item)
        for item_id in sorted(self.inventory):
            label = self.item_labels.get(item_id, item_id)
            if requested_key in {_match_key(item_id), _match_key(label)}:
                return item_id, label
        return None

    def _validate_target_visible(self, target: str) -> str | None:
        if target in self.inventory:
            return None
        if self.current_room is None:
            return None
        room = self._room()
        if room is not None and target in room.objects:
            return None

        locations = self.object_locations.get(target)
        if locations and self.current_room not in locations:
            known = ", ".join(sorted(locations))
            return (
                f"Error: memoria estructurada: {target!r} fue visto en {known}, "
                f"pero la sala actual es {self.current_room}. Navega primero a la sala correcta."
            )
        return None
