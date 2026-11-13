"""The pet's six stats. Every value ranges from 0 to 100; higher is better."""
from dataclasses import dataclass, asdict, fields

STAT_MIN, STAT_MAX = 0, 100

# Stat name -> description (also included in the LLM prompt)
STAT_DESCRIPTIONS = {
    "fullness": "how full the pet is (low = very hungry)",
    "energy": "energy level (low = very tired)",
    "mood": "mood (low = unhappy)",
    "cleanliness": "cleanliness (low = very dirty)",
    "health": "health (low = sick)",
    "social": "social needs met (low = very lonely)",
}


def clamp(v: float) -> int:
    return int(max(STAT_MIN, min(STAT_MAX, round(v))))


@dataclass
class PetState:
    fullness: int = 70
    energy: int = 70
    mood: int = 70
    cleanliness: int = 70
    health: int = 90
    social: int = 60

    def apply(self, delta: dict[str, int]) -> None:
        """Add the given deltas, clamping each stat to 0-100."""
        for k, v in delta.items():
            setattr(self, k, clamp(getattr(self, k) + v))

    def to_dict(self) -> dict[str, int]:
        return asdict(self)

    @staticmethod
    def names() -> list[str]:
        return [f.name for f in fields(PetState)]

    def lowest(self) -> tuple[str, int]:
        d = self.to_dict()
        k = min(d, key=d.get)
        return k, d[k]
