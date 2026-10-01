from __future__ import annotations  # Enable forward references in type annotations

import re  # Parse B/S/C outer-totalistic notation
from dataclasses import dataclass  # Store normalized rules

RULE_NOTATION = re.compile(r"^B([^/]*)/S([^/]*)(?:/[CG](\d+))?$", re.IGNORECASE)


# Describes a normalized outer-totalistic rule
@dataclass(frozen=True)
class OuterTotalisticRule:
    birth: tuple[int, ...]
    survival: tuple[int, ...]
    states: int
    neighborhood: str

    # PROPERTY :: VOID -> STRING
    # Returns normalized B/S/C notation
    @property
    def notation(self) -> str:
        birth = _formatCounts(self.birth)
        survival = _formatCounts(self.survival)
        states = "" if self.states == 2 else f"/C{self.states}"
        return f"B{birth}/S{survival}{states}"


# :: STRING, STRING, INT -> outerTotalisticRule
# Parses and validates a two- or three-dimensional B/S/C rule
def parseRule(notation: str, neighborhood: str = "moore", dimension: int = 2) -> OuterTotalisticRule:
    if neighborhood not in {"moore", "von_neumann"}:
        raise ValueError("neighborhood must be moore or von_neumann")
    if not isinstance(notation, str):
        raise ValueError("rule notation must be a string")
    match = RULE_NOTATION.fullmatch(notation.strip())
    if not match:
        raise ValueError("rule must use B…/S… with optional /C… states")
    if dimension not in {2, 3}:
        raise ValueError("rule dimension must be 2 or 3")
    maximum = (26 if neighborhood == "moore" else 6) if dimension == 3 else (8 if neighborhood == "moore" else 4)
    birth = _parseCounts(match.group(1), maximum, "birth")
    survival = _parseCounts(match.group(2), maximum, "survival")
    states = int(match.group(3) or 2)
    if not 2 <= states <= 256:
        raise ValueError("rule states must be between 2 and 256")
    return OuterTotalisticRule(birth, survival, states, neighborhood)


# :: (INT) -> STRING
# Formats multi-digit neighbor counts without ambiguity
def _formatCounts(counts: tuple[int, ...]) -> str:
    separator = "," if any(count >= 10 for count in counts) else ""
    return separator.join(str(count) for count in counts)


# :: STRING, INT, STRING -> (INT)
# Parses compact single-digit counts, comma lists, and inclusive ranges
def _parseCounts(value: str, maximum: int, label: str) -> tuple[int, ...]:
    if not value:
        return ()
    counts: set[int] = set()
    if "," not in value and "-" not in value:
        if not value.isdigit():
            raise ValueError(f"{label} counts must be integers")
        counts.update(int(character) for character in value)
    else:
        for part in value.split(","):
            if not part:
                raise ValueError(f"{label} counts contain an empty item")
            if "-" in part:
                bounds = part.split("-")
                if len(bounds) != 2 or not all(bound.isdigit() for bound in bounds):
                    raise ValueError(f"{label} range {part!r} is invalid")
                start, end = (int(bound) for bound in bounds)
                if start > end:
                    raise ValueError(f"{label} range {part!r} is reversed")
                counts.update(range(start, end + 1))
            elif part.isdigit():
                counts.add(int(part))
            else:
                raise ValueError(f"{label} count {part!r} is invalid")
    invalid = sorted(count for count in counts if count < 0 or count > maximum)
    if invalid:
        raise ValueError(f"{label} count {invalid[0]} exceeds the neighborhood maximum of {maximum}")
    return tuple(sorted(counts))
