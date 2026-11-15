"""Actions: the functions here change the stats (and the world around the pet).

The LLM picks one of these actions each tick, based on the pet's current thought and memory.

To add an action, write a function and decorate it with @action(...).
The LLM's list of choices picks it up automatically.

    def can_walk(state: PetState, world: World) -> bool:
        return state.energy >= 20          # too tired to go out

    @action("walk", "Walk", pose="walk", condition=can_walk)
    def walk(state: PetState, world: World) -> None:
        state.apply({"health": +5, "energy": -10})

The action function receives the pet's state and the world and can contain any logic
(conditions, randomness, ...). Use state.apply({...}) to change stats;
values are clamped to 0-100 automatically.

condition (optional) is called first, with the state before the action.
If it returns False the action has no effect this tick (the pet still spends
the tick on it, and the per-tick rules still run). Leave it out to always apply.

pose and prop say how the action looks. Actions share a small set of them so the
graphical display only needs a few drawings:
    pose: stand / walk / sit / lie
    prop: bowl / heart / question / zzz, or None
The pet's expression is not set here; it follows the current thought.
"""
from dataclasses import dataclass
from typing import Callable

from .state import PetState
from .world import World

ActionFn = Callable[[PetState, World], None]
ConditionFn = Callable[[PetState, World], bool]


def always(state: PetState, world: World) -> bool:
    """Default condition: the action always takes effect."""
    return True


@dataclass(frozen=True)
class Action:
    name: str
    label: str              # display name
    pose: str               # stand / walk / sit / lie
    prop: str | None        # bowl / heart / question / zzz, or None
    fn: ActionFn            # function that changes the stats
    condition: ConditionFn  # whether the action can change the stats right now


@dataclass(frozen=True)
class ActionResult:
    delta: dict[str, int]   # actual change this tick (action + per-tick rules), stats and world
    applied: bool           # False if the condition blocked the action's effect


ACTIONS: dict[str, Action] = {}


def action(name: str, label: str, *, pose: str, prop: str | None = None,
           condition: ConditionFn = always) -> Callable[[ActionFn], ActionFn]:
    """Register an action function."""
    def register(fn: ActionFn) -> ActionFn:
        if name in ACTIONS:
            raise ValueError(f"action {name} is registered twice")
        ACTIONS[name] = Action(name, label, pose, prop, fn, condition)
        return fn
    return register


# ---------------------------------------------------------------- action functions
# Each action has a can_<name> condition. Most return True for now;
# fill them in to decide when the action is able to change anything.

# ---- when hungry

def can_eat_from_bowl(state: PetState, world: World) -> bool:
    return world.bowl > 0  # an empty bowl: nothing to eat


@action("eat_from_bowl", "Eat from bowl", pose="sit", prop="bowl", condition=can_eat_from_bowl)
def eat_from_bowl(state: PetState, world: World) -> None:
    world.bowl -= 1
    state.apply({"fullness": +30})


def can_beg(state: PetState, world: World) -> bool:
    return True


@action("beg", "Beg", pose="sit", prop="question", condition=can_beg)
def beg(state: PetState, world: World) -> None:
    pass  # changes nothing by itself; it shows the owner the pet wants food


def can_scavenge(state: PetState, world: World) -> bool:
    return True


@action("scavenge", "Scavenge", pose="walk", prop="question", condition=can_scavenge)
def scavenge(state: PetState, world: World) -> None:
    state.apply({"fullness": +15, "health": -10})  # always finds something, but it isn't good for the pet


# ---- when tired

def can_sleep(state: PetState, world: World) -> bool:
    return True


@action("sleep", "Sleep", pose="lie", prop="zzz", condition=can_sleep)
def sleep(state: PetState, world: World) -> None:
    state.apply({"energy": +45, "fullness": -10})


def can_rest(state: PetState, world: World) -> bool:
    return True


@action("rest", "Rest", pose="lie", condition=can_rest)
def rest(state: PetState, world: World) -> None:
    state.apply({"energy": +15, "health": +15})


# ---- when lonely

def can_seek_attention(state: PetState, world: World) -> bool:
    return True


@action("seek_attention", "Seek attention", pose="sit", prop="heart", condition=can_seek_attention)
def seek_attention(state: PetState, world: World) -> None:
    pass  # changes nothing by itself; the owner's Cuddle is what helps


def can_play_alone(state: PetState, world: World) -> bool:
    return True


@action("play_alone", "Play alone", pose="walk", prop="heart", condition=can_play_alone)
def play_alone(state: PetState, world: World) -> None:
    state.apply({"social": +10, "energy": -10})


# ---- when content

def can_explore(state: PetState, world: World) -> bool:
    return True


@action("explore", "Explore", pose="walk", condition=can_explore)
def explore(state: PetState, world: World) -> None:
    state.apply({"energy": -5})


@action("idle", "Idle", pose="stand")
def idle(state: PetState, world: World) -> None:
    pass


# ---------------------------------------------------------------- apply

def apply_action(state: PetState, world: World, action_name: str | None) -> ActionResult:
    """Check the condition, run the action function if allowed, then every per-tick rule in order.
    action_name=None means no action this tick (e.g. the LLM gave no usable reply): only the rules run."""
    from .rules import RULES  # avoid a circular import

    before = {**state.to_dict(), **world.to_dict()}
    applied = False
    if action_name is not None:
        act = ACTIONS[action_name]
        applied = act.condition(state, world)
        if applied:
            act.fn(state, world)
    for rule in RULES:  # time passes either way
        rule(state)
    after = {**state.to_dict(), **world.to_dict()}
    delta = {k: after[k] - before[k] for k in after if after[k] != before[k]}
    return ActionResult(delta, applied)
