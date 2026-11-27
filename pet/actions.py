"""Actions: the only thing that changes the pet. The pet does one action at a time.

The loop (engine.py):
    pick an action -> it runs for its duration, changing the stats and the world -> pick the next

Picking the next action:
    1. the action that just finished picks it, through its `then` function
    2. if `then` is missing or returns None, the LLM picks it from the pet's thought and memory

To add an action, decorate a function with @action(...).
The LLM's list of choices picks it up automatically.

    def after_walk(state: PetState, world: World) -> str | None:
        return "rest" if state.energy < 20 else None     # too tired: rest; otherwise ask the LLM

    @action("walk", "Walk", pose="walk", duration=10, then=after_walk)
    def walk(state: PetState, world: World, step: Step) -> Effect:
        for _ in range(step.count(10)):                  # 10 cells over the action
            world.move_to(world.x + 1, world.y)
        return plus(living(state, step), per_second({"health": +0.5, "energy": -1}, step))

The function runs every step while the action lasts (about once a second). `step` says how much
time that step covers (step.seconds) and how far along the action is; step.count(n) spreads n
events (moves, bites, ...) evenly over the whole action. The function makes the world changes for
this step (eat some of the food, move the pet, ...) and returns the stat changes for this step;
values are clamped to 0-100.
It can contain any logic: look at the world and the stats and do something different.
Nothing else changes the stats as time passes, so include the cost of living
(living(), below): an action that does nothing still makes the pet a little hungrier, and a
need left at 0 hurts its health.

duration: the most seconds the action lasts.

stop_when (optional): checked every step, right after the function, with the stats and world at
that moment. Return True to end the action there, before its duration is up; it then counts as
finished (`then` runs). Leave it out and the action always runs its full duration.

then (optional): runs once when the action has finished (its duration is up, or stop_when said
so), with the stats and world at that moment. Return the name of the next action, or None to let the LLM decide.

llm (optional, default True): whether the LLM may pick it. llm=False actions only happen
when another action's `then` picks them.

pose and prop say how the action looks. Actions share a small set of them so the
graphical display only needs a few drawings:
    pose: stand / walk / sit / lie
    prop: bowl / heart / question / zzz, or None
The pet's expression is not set here; it follows the current thought.
"""
import math
from dataclasses import dataclass
from typing import Callable

from .state import PetState
from .world import World

Effect = dict[str, float]  # stat -> change


@dataclass(frozen=True)
class Step:
    """The part of the action one call of its function covers."""
    start: float     # seconds into the action when this step starts
    end: float       # ... and ends
    duration: float  # the whole action

    @property
    def seconds(self) -> float:
        return self.end - self.start

    def count(self, n: int) -> int:
        """How many of n events, spread evenly over the action, fall in this step.
        Over the whole action the counts add up to exactly n."""
        return math.floor(n * self.end / self.duration) - math.floor(n * self.start / self.duration)


ActionFn = Callable[[PetState, World, Step], Effect]  # runs every step
ThenFn = Callable[[PetState, World], str | None]      # runs at the end: next action, or None
StopFn = Callable[[PetState, World], bool]            # runs every step: True = end it now


@dataclass(frozen=True)
class Action:
    name: str
    label: str                      # display name
    pose: str                       # stand / walk / sit / lie
    prop: str | None                # bowl / heart / question / zzz, or None
    duration: float                 # the most seconds it lasts
    fn: ActionFn                    # runs every step: changes the world, returns the stat changes
    then: ThenFn | None = None      # picks the next action, or None = the LLM picks
    stop_when: StopFn | None = None  # ends it early
    llm: bool = True                # whether the LLM may pick it

    def should_stop(self, state: PetState, world: World) -> bool:
        """Whether stop_when ends the action now."""
        return self.stop_when is not None and bool(self.stop_when(state, world))

    def next_action(self, state: PetState, world: World) -> "Action | None":
        """The action `then` picks, or None for the LLM to pick."""
        if self.then is None:
            return None
        name = self.then(state, world)
        if name is None:
            return None
        if name not in ACTIONS:
            raise ValueError(f"{self.name}: then returned {name!r}, which is not an action")
        return ACTIONS[name]


ACTIONS: dict[str, Action] = {}


def action(name: str, label: str, *, pose: str, duration: float, prop: str | None = None,
           then: ThenFn | None = None, stop_when: StopFn | None = None,
           llm: bool = True) -> Callable[[ActionFn], ActionFn]:
    """Register an action."""
    if duration <= 0:
        raise ValueError(f"action {name}: duration must be greater than 0")

    def register(fn: ActionFn) -> ActionFn:
        if name in ACTIONS:
            raise ValueError(f"action {name} is registered twice")
        ACTIONS[name] = Action(name, label, pose, prop, duration, fn, then, stop_when, llm)
        return fn
    return register


def llm_choices() -> list[str]:
    """The actions the LLM may pick."""
    return [a.name for a in ACTIONS.values() if a.llm]


def per_second(rates: dict[str, float], step: Step) -> Effect:
    """Changes per second -> changes for this step."""
    return {k: v * step.seconds for k, v in rates.items()}


def plus(*effects: Effect) -> Effect:
    """Add effects together."""
    out: Effect = {}
    for e in effects:
        for k, v in e.items():
            out[k] = out.get(k, 0) + v
    return out


# ---------------------------------------------------------------- actions

LIVING = {"fullness": -1.2, "energy": -0.8, "social": -0.8}  # per second, whatever the pet does
NEEDS = ("fullness", "energy", "social")
NEGLECT = 1.0    # health lost per second for each need at 0
REST_HEAL = 3.0  # health rest gives back per second, only while no need is at 0
EAT_SPEED = 6.0  # food eaten per second; each unit of food is one point of fullness


MOVES = 8         # cells idle (at random) and scavenge (toward food) move over the action


def neglected(state: PetState) -> list[str]:
    """The needs that are at 0."""
    return [n for n in NEEDS if getattr(state, n) <= 0]


def living(state: PetState, step: Step) -> Effect:
    """The cost of living for this step; part of every action.
    Each need at 0 also costs NEGLECT health a second: left alone long enough, the pet falls ill."""
    return per_second({**LIVING, "health": -NEGLECT * len(neglected(state))}, step)


# ---- when hungry

def after_eating(state: PetState, world: World) -> str | None:
    if state.fullness < 60 and world.here("food") is not None:
        return "eat"  # still hungry and there's food left: keep eating
    return None


def done_eating(state: PetState, world: World) -> bool:
    return world.here("food") is None or state.fullness >= 100  # nothing left, or full


@action("eat", "Eat", pose="sit", prop="bowl", duration=5, then=after_eating, stop_when=done_eating,
        llm=False)
def eat(state: PetState, world: World, step: Step) -> Effect:
    """Eats the food at the pet's position, EAT_SPEED a second, until it's gone.
    The LLM can't pick it: the pet eats after scavenge has brought it to food."""
    food = world.here("food")
    eaten = 0.0
    if food is not None:
        eaten = world.take(food, EAT_SPEED * step.seconds)
    return plus(living(state, step), {"fullness": eaten})


@action("beg", "Beg", pose="sit", prop="question", duration=5)
def beg(state: PetState, world: World, step: Step) -> Effect:
    return living(state, step)  # nothing by itself; shows the owner it wants food


def after_scavenging(state: PetState, world: World) -> str | None:
    return "eat" if world.here("food") is not None else None  # reached the food: eat it


def reached_food(state: PetState, world: World) -> bool:
    return world.here("food") is not None


@action("scavenge", "Scavenge", pose="walk", prop="question", duration=5, then=after_scavenging,
        stop_when=reached_food)
def scavenge(state: PetState, world: World, step: Step) -> Effect:
    """Heads for the nearest food, up to MOVES cells over the action; ends on reaching it.
    Stays put if there is no food: only the owner's food fills the pet (through eat)."""
    for _ in range(step.count(MOVES)):
        food = world.nearest("food")
        if food is None:
            break
        world.step_toward(food.x, food.y)
    return living(state, step)


# ---- when tired

def after_sleeping(state: PetState, world: World) -> str | None:
    return "sleep" if state.energy < 40 else None  # still exhausted: keep sleeping


@action("sleep", "Sleep", pose="lie", prop="zzz", duration=10, then=after_sleeping)
def sleep(state: PetState, world: World, step: Step) -> Effect:
    return plus(living(state, step), per_second({"energy": +9, "fullness": -2}, step))


@action("rest", "Rest", pose="lie", duration=10)
def rest(state: PetState, world: World, step: Step) -> Effect:
    """Recovers some energy, and health too, but only while no need is at 0: resting can't make
    up for starving or being left alone."""
    heal = 0.0 if neglected(state) else REST_HEAL
    return plus(living(state, step), per_second({"energy": +3, "health": heal}, step))


# ---- when lonely

@action("cuddled", "Being cuddled", pose="sit", prop="heart", duration=5, llm=False)
def cuddled(state: PetState, world: World, step: Step) -> Effect:
    """The owner's Cuddle (interactions.py) starts this, whatever the pet was doing.
    It helps loneliness but tires the pet out."""
    return plus(living(state, step), per_second({"social": +6, "energy": -1}, step))


@action("seek_attention", "Seek attention", pose="sit", prop="heart", duration=5)
def seek_attention(state: PetState, world: World, step: Step) -> Effect:
    return living(state, step)  # nothing by itself; the owner's Cuddle is what helps


@action("play_alone", "Play alone", pose="walk", prop="heart", duration=10)
def play_alone(state: PetState, world: World, step: Step) -> Effect:
    return plus(living(state, step), per_second({"social": +2, "energy": -2}, step))


# ---- when content

@action("idle", "Idle", pose="walk", duration=5)
def idle(state: PetState, world: World, step: Step) -> Effect:
    """Wanders: MOVES random cells over the action."""
    for _ in range(step.count(MOVES)):
        world.random_step()
    return living(state, step)
