"""The pet's stats. Every value is a float from 0 to 100; higher is better.

fullness, energy and social are needs (each has a thought in thoughts.py).
health is not a need: it shows the consequence of neglect. The pet feels sick when it is low
and falls ill at 0.
"""
from dataclasses import dataclass, asdict, fields

STAT_MIN, STAT_MAX = 0, 100


def clamp(v: float) -> float:
    return round(max(STAT_MIN, min(STAT_MAX, v)), 6)  # rounding keeps float noise out of the values


@dataclass
class PetState:
    fullness: float = 70
    energy: float = 70
    health: float = 90
    social: float = 60

    def apply(self, delta: dict[str, float]) -> None:
        """Add the given deltas, clamping each stat to 0-100."""
        for k, v in delta.items():
            setattr(self, k, clamp(getattr(self, k) + v))

    def to_dict(self) -> dict[str, float]:
        return asdict(self)

    @staticmethod
    def names() -> list[str]:
        return [f.name for f in fields(PetState)]

    def lowest(self) -> tuple[str, float]:
        d = self.to_dict()
        k = min(d, key=d.get)
        return k, d[k]
