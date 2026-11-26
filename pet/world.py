"""The world around the pet: things that are not the pet's own stats.

Actions and owner interactions receive it next to the pet's state and may read or change it.

    WIDTH x HEIGHT          the size of the world: x in 0..WIDTH-1, y in 0..HEIGHT-1
    world.x, world.y        where the pet is
    world.items             every item in the world, each at its own (x, y)
    world.items_here()      the items at the pet's position
    world.here("food")      the food at the pet's position, or None
    world.put("food", x, y, 30)   add an item (or add to the same kind already there)
    world.take(item, 6)     use up some of an item; it disappears at 0
    world.move_to(x, y)     move the pet (kept inside the world)
    world.nearest("food")   the closest food to the pet, or None
    world.step_toward(x, y) / world.random_step()   move the pet one cell (up, down, left or right)
"""
import random
from dataclasses import asdict, dataclass, field

DIRECTIONS = [(1, 0), (-1, 0), (0, 1), (0, -1)]

WIDTH, HEIGHT = 16, 16  # the world is a 16x16 grid


def inside(x: int, y: int) -> bool:
    """Whether (x, y) is a position in the world."""
    return 0 <= x < WIDTH and 0 <= y < HEIGHT


def clamp_position(x: int, y: int) -> tuple[int, int]:
    """The nearest position inside the world."""
    return min(max(x, 0), WIDTH - 1), min(max(y, 0), HEIGHT - 1)


@dataclass
class Item:
    kind: str            # what it is: "food", ...
    x: int
    y: int
    amount: float = 0.0  # how much of it there is (food: points of fullness it gives)

    def __post_init__(self):
        if not inside(self.x, self.y):
            raise ValueError(f"{self.kind} at ({self.x}, {self.y}) is outside the {WIDTH}x{HEIGHT} world")


@dataclass
class World:
    x: int = 0  # the pet's position
    y: int = 0
    items: list[Item] = field(default_factory=list)

    def __post_init__(self):
        if not inside(self.x, self.y):
            raise ValueError(f"the pet at ({self.x}, {self.y}) is outside the {WIDTH}x{HEIGHT} world")

    def move_to(self, x: int, y: int) -> None:
        """Move the pet to (x, y); a position outside the world stops at its edge."""
        self.x, self.y = clamp_position(x, y)

    def step_toward(self, x: int, y: int) -> None:
        """Move the pet one cell toward (x, y), along the axis with the longer way to go.
        Does nothing once it is there."""
        dx, dy = x - self.x, y - self.y
        if dx == 0 and dy == 0:
            return
        if abs(dx) >= abs(dy):
            self.move_to(self.x + (1 if dx > 0 else -1), self.y)
        else:
            self.move_to(self.x, self.y + (1 if dy > 0 else -1))

    def random_step(self, rng: random.Random = random) -> None:
        """Move the pet one cell in a random direction that stays inside the world."""
        options = [(dx, dy) for dx, dy in DIRECTIONS if inside(self.x + dx, self.y + dy)]
        dx, dy = rng.choice(options)
        self.move_to(self.x + dx, self.y + dy)

    def distance_to(self, item: "Item") -> int:
        """Steps from the pet to the item (moving up, down, left or right)."""
        return abs(item.x - self.x) + abs(item.y - self.y)

    def nearest(self, kind: str) -> "Item | None":
        """The item of this kind closest to the pet, or None if there is none."""
        return min((i for i in self.items if i.kind == kind), key=self.distance_to, default=None)

    def items_at(self, x: int, y: int) -> list[Item]:
        return [i for i in self.items if (i.x, i.y) == (x, y)]

    def items_here(self) -> list[Item]:
        """The items at the pet's position."""
        return self.items_at(self.x, self.y)

    def here(self, kind: str) -> Item | None:
        """The first item of this kind at the pet's position, or None."""
        return next((i for i in self.items_here() if i.kind == kind), None)

    def find(self, kind: str) -> Item | None:
        """The first item of this kind anywhere in the world, or None."""
        return next((i for i in self.items if i.kind == kind), None)

    def put(self, kind: str, x: int, y: int, amount: float) -> Item:
        """Add an item at (x, y). If one of the same kind is already there, add to it instead."""
        existing = next((i for i in self.items_at(x, y) if i.kind == kind), None)
        if existing is not None:
            existing.amount += amount
            return existing
        item = Item(kind, x, y, amount)
        self.items.append(item)
        return item

    def take(self, item: Item, amount: float) -> float:
        """Use up to `amount` of the item; it is removed once nothing is left. Returns what was taken."""
        taken = min(amount, item.amount)
        item.amount = round(item.amount - taken, 6)
        if item.amount <= 0 and item in self.items:
            self.items.remove(item)
        return taken

    def numbers(self) -> dict[str, float]:
        """Flat numbers for working out what changed: the position and each item's amount
        (keyed kind@x,y)."""
        out: dict[str, float] = {"x": self.x, "y": self.y}
        for i in self.items:
            key = f"{i.kind}@{i.x},{i.y}"
            out[key] = out.get(key, 0) + i.amount
        return out

    def to_dict(self) -> dict:
        return {
            "width": WIDTH,
            "height": HEIGHT,
            "x": self.x,
            "y": self.y,
            "items": [asdict(i) for i in self.items],
            "here": [asdict(i) for i in self.items_here()],
        }


def diff(before: dict[str, float], after: dict[str, float]) -> dict[str, float]:
    """What changed between two flat dicts (keys that appeared or disappeared count from 0)."""
    out = {}
    for k in before.keys() | after.keys():
        d = after.get(k, 0) - before.get(k, 0)
        if d:
            out[k] = d
    return out
