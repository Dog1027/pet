"""Find the pet's PNG sprites in webui/static/sprites/ and describe them for the page.

Files follow the naming in the design requirements ("Moffy 寵物動畫設計需求"):

    sprites/<pose>/body.png                        the pose's still body (used by every action of
                                                   that pose that has no frames of its own)
    sprites/<pose>/<action>-01.png, -02.png ...   body frames of an action, played in order
    sprites/<pose>/eyes-<eye>.png                  the eyes for that pose, laid over the body
    sprites/faces.json                             where the eyes go on each pose's body (the page
                                                   draws them; written by slice_poses.py)
    sprites/settings.json                          optional: playback speed, eye positions

    pose:   stand / walk / sit / loaf / lie
    action: the action's name (actions.py), plus "thinking" (waiting for the LLM)
            and "ill" (fallen ill)
    eye:    open / half / closed / happy / x

Every PNG has the same canvas size, with the pet standing on the same point (bottom centre).
An eyes file covers the whole canvas, drawn where the eyes sit in that pose at rest.

settings.json (every key optional):
    {
      "fps": 8,                                  default frames per second
      "actions": {"idle": {"fps": 10}},          per action
      "eyes": {                                  where the eyes' centre is, in canvas px
        "walk": {"base": [610, 520],             in the eyes file
                 "idle": [[610, 540], [610, 500], ...]}   in each frame of an action
      }
    }
When an action's face moves (squashing as it bounces), its frames list the eyes' centre per
frame and the page shifts the eyes layer by (frame - base).
"""
import json
import re
from pathlib import Path

SPRITES_DIR = Path(__file__).resolve().parent / "static" / "sprites"
URL_PREFIX = "sprites"
POSES = ("stand", "walk", "sit", "loaf", "lie")
EYES = ("open", "half", "closed", "happy", "x")
DEFAULT_FPS = 8

_FRAME = re.compile(r"^(?P<action>[a-z_]+)-(?P<n>\d+)\.png$")
_EYES = re.compile(r"^eyes-(?P<eye>[a-z]+)\.png$")


def describe(directory: Path = SPRITES_DIR) -> dict:
    """What sprites there are, as the page reads them:
        {"actions": {name: {"pose", "frames": [url, ...], "fps", "eyeOffsets"?: [[dx, dy], ...]}},
         "bodies": {pose: url},
         "faces": {"canvas": [w, h], "poses": {pose: {"eyes": [[x, y], [x, y]], "r"}}},
         "eyes": {pose: {eye: url}},
         "problems": [text, ...]}
    Missing directory or no files -> empty "actions": the page keeps drawing the pet itself."""
    out: dict = {"actions": {}, "bodies": {}, "faces": {}, "eyes": {}, "problems": []}
    if not directory.is_dir():
        return out
    settings = _settings(directory, out["problems"])
    faces = directory / "faces.json"
    if faces.exists():
        try:
            out["faces"] = json.loads(faces.read_text(encoding="utf-8"))
        except ValueError as e:
            out["problems"].append(f"faces.json: not valid JSON ({e})")
    default_fps = settings.get("fps", DEFAULT_FPS)

    for pose in POSES:
        pose_dir = directory / pose
        if not pose_dir.is_dir():
            continue
        frames: dict[str, list[tuple[int, str]]] = {}
        for f in sorted(pose_dir.iterdir()):
            if not f.is_file() or f.suffix.lower() != ".png":
                continue
            url = f"{URL_PREFIX}/{pose}/{f.name}"
            if f.name == "body.png":
                out["bodies"][pose] = url
            elif m := _EYES.match(f.name):
                if m["eye"] in EYES:
                    out["eyes"].setdefault(pose, {})[m["eye"]] = url
                else:
                    out["problems"].append(f"{pose}/{f.name}: unknown eyes {m['eye']!r}, expected one of {EYES}")
            elif m := _FRAME.match(f.name):
                frames.setdefault(m["action"], []).append((int(m["n"]), url))
            else:
                out["problems"].append(f"{pose}/{f.name}: name doesn't match body.png, <action>-NN.png or eyes-<eye>.png")

        for action, numbered in frames.items():
            if action in out["actions"]:
                out["problems"].append(f"{action}: frames in both {out['actions'][action]['pose']}/ and {pose}/; "
                                       f"using {out['actions'][action]['pose']}/")
                continue
            numbered.sort()
            entry = {
                "pose": pose,
                "frames": [url for _, url in numbered],
                "fps": settings.get("actions", {}).get(action, {}).get("fps", default_fps),
            }
            offsets = _eye_offsets(settings, pose, action, len(numbered), out["problems"])
            if offsets:
                entry["eyeOffsets"] = offsets
            out["actions"][action] = entry
    return out


def _settings(directory: Path, problems: list[str]) -> dict:
    path = directory / "settings.json"
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except ValueError as e:
        problems.append(f"settings.json: not valid JSON ({e})")
        return {}
    if not isinstance(data, dict):
        problems.append("settings.json: expected an object")
        return {}
    return data


def _eye_offsets(settings: dict, pose: str, action: str, frames: int, problems: list[str]) -> list | None:
    """Per-frame shift of the eyes layer, from settings["eyes"][pose]: frame centre - base."""
    spec = settings.get("eyes", {}).get(pose, {})
    centres = spec.get(action)
    if centres is None:
        return None
    base = spec.get("base")
    if not base:
        problems.append(f"settings.json: eyes.{pose}.{action} needs eyes.{pose}.base")
        return None
    if len(centres) != frames:
        problems.append(f"settings.json: eyes.{pose}.{action} has {len(centres)} points for {frames} frames")
        return None
    return [[c[0] - base[0], c[1] - base[1]] for c in centres]
