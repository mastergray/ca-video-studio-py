from __future__ import annotations  # Enable forward references in type annotations

import json  # Parse the versioned 3D catalog
from dataclasses import dataclass  # Store immutable catalog records
from importlib.resources import files  # Locate packaged catalog data

from ca_video_studio_py.simulation.rules import OuterTotalisticRule, parseRule  # Normalize catalog rules


# Describes one built-in three-dimensional automaton rule
@dataclass(frozen=True)
class Rule3DEntry:
    key: str
    name: str
    category: str
    notation: str
    neighborhood: str
    recommendedInitial: str
    density: float
    description: str

    # PROPERTY :: VOID -> outerTotalisticRule
    # Returns the parsed rule with 3D neighbor limits
    @property
    def rule(self) -> OuterTotalisticRule:
        return parseRule(self.notation, self.neighborhood, 3)


# Describes the four visible colors of an isometric voxel
@dataclass(frozen=True)
class Palette3D:
    key: str
    top: tuple[int, int, int]
    left: tuple[int, int, int]
    right: tuple[int, int, int]
    outline: tuple[int, int, int]


# :: STRING -> (INT, INT, INT)
# Converts a catalog hex color to RGB channels
def _color(value: str) -> tuple[int, int, int]:
    return tuple(int(value[index : index + 2], 16) for index in (1, 3, 5))


# :: VOID -> ARRAY<STRING, ANY>
# Loads the packaged catalog mapping
def _catalogData() -> dict[str, object]:
    resource = files("ca_video_studio_py.catalogs").joinpath("rules_3d.json")
    return json.loads(resource.read_text(encoding="utf-8"))


# :: VOID -> (rule3DEntry)
# Loads three-dimensional rules in display order
def rule3DCatalog() -> tuple[Rule3DEntry, ...]:
    return tuple(
        Rule3DEntry(
            item["key"],
            item["name"],
            item["category"],
            item["notation"],
            item["neighborhood"],
            item["initial"],
            item["density"],
            item["description"],
        )
        for item in _catalogData()["rules"]
    )


# :: STRING -> rule3DEntry
# Resolves a stable three-dimensional rule key
def getRule3D(key: str) -> Rule3DEntry:
    for entry in rule3DCatalog():
        if entry.key == key:
            return entry
    choices = ", ".join(entry.key for entry in rule3DCatalog())
    raise KeyError(f"unknown 3D rule preset {key!r}; expected one of {choices}")


# :: VOID -> (palette3D)
# Loads all isometric voxel palettes
def palette3DCatalog() -> tuple[Palette3D, ...]:
    palettes = _catalogData()["palettes"]
    return tuple(
        Palette3D(
            key,
            _color(value["top"]),
            _color(value["left"]),
            _color(value["right"]),
            _color(value["outline"]),
        )
        for key, value in palettes.items()
    )


# :: STRING -> palette3D
# Resolves a stable palette key
def getPalette3D(key: str) -> Palette3D:
    for palette in palette3DCatalog():
        if palette.key == key:
            return palette
    choices = ", ".join(palette.key for palette in palette3DCatalog())
    raise KeyError(f"unknown 3D palette {key!r}; expected one of {choices}")
