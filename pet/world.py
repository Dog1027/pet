"""The world around the pet: things that are not the pet's own stats.

Actions and owner interactions receive it next to the pet's state and may read or change it.
"""
from dataclasses import asdict, dataclass

BOWL_MAX = 2  # portions the bowl can hold


@dataclass
class World:
    bowl: int = 0  # portions of food in the bowl, 0..BOWL_MAX

    def to_dict(self) -> dict[str, int]:
        return asdict(self)
