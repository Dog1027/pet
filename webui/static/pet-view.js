// How the pet and the items are drawn. Change this file to change the pet's look.
//
// drawPet(el, look) is called on every refresh with the pet's element (#pet). The page
// positions the element on the pet's cell (and moves it); this function only draws what is
// inside it. The floor is seen at a slant, so things stand on their cell: each child is
// anchored at the cell's centre and rises above it (see style.css). Clicking the drawing
// (.pet-svg / .pet-sprite) cuddles the pet.
//   look  {
//     pose:       "stand" | "walk" | "sit" | "lie"         (from the running action; stand when none)
//     prop:       "bowl" | "heart" | "question" | "zzz" | null
//     expression: the current thought: "content" | "hungry" | "tired" | "lonely" | "sick"
//     action:     name of the running action, or null (thinking)
//     alive:      false once the pet has fallen ill
//     facing:     "left" | "right"   (set by app.js from the way the pet last moved)
//   }
//
// drawItem(el, item) draws one item in its element (also one cell).
//   item  { kind: "food", x, y, amount }
//
// Two ways to draw the pet, chosen per action:
//   PNG sprites  when webui/static/sprites/ has the action's frames, or a still body for the
//                action's pose (names: webui/sprites.py, served as /api/sprites; made from
//                design.png by `just sprites`): the body (or its frames, in a loop) with the
//                pose's eyes for the current state on top, mirrored as a whole to face left
//   SVG          otherwise: the drawing below, a placeholder until all the PNGs are there
// Floating symbols are drawn by this file either way.
//
// The SVG pet is Moffy (design.jpg): a round, fluffy cream rabbit monster with big soft ears,
// a pink nose, buck teeth, blush and a cotton tail, and no arms or legs: it moves by
// bouncing like a ball (squashing as it lands, stretching as it rises). It is drawn turned a
// little to the right and mirrored to face left. Only the eyes change; what it thinks or does
// shows as symbols floating up from its head. A placeholder until the designer's layered PNGs
// arrive. Inline SVG, viewBox 120 x 100, standing on y = 96:
//   POSES    body and ears per pose                 (stand / walk / sit / loaf / lie)
//   ACTIONS  per action: pose, eyes, symbols, extras (the ball), animation
//   THOUGHTS the symbol and eyes for each thought, when the action doesn't set them
// Colours come from CSS variables (--pet, --pet-inner, --pet-line, --pet-blush in style.css);
// animations are CSS classes (a-*) in style.css.

// ---------------------------------------------------------------- eyes and icons
// Drawn here in the style of design.jpg: dark brown, soft rounded strokes, the palette's
// pink / orange / mint, a brown outline on coloured icons.

const INK = "#111";      // eyes: plain black
const LINE = "#6e4c3d";  // icon outlines

// One eye of radius r centred on (x, y); the same drawings serve the PNG pet (faces.json gives
// where and how big) and the SVG pet.
function eyeSvg(kind, x, y, r) {
  const w = r * 0.3;  // stroke width of the line-drawn eyes
  const line = (d) => `<path d="${d}" fill="none" stroke="${INK}" stroke-width="${w}" stroke-linecap="round" stroke-linejoin="round"/>`;
  switch (kind) {
    case "half":   // sleepy: the lid comes down over the top half
      return `<path d="M${x - r * 0.92} ${y - r * 0.05} A${r * 0.92} ${r * 0.85} 0 0 0 ${x + r * 0.92} ${y - r * 0.05} Z" fill="${INK}"/>`
        + line(`M${x - r * 1.1} ${y - r * 0.15} Q${x} ${y - r * 0.4} ${x + r * 1.1} ${y - r * 0.15}`);
    case "relaxed": // resting: a shallow, contented curve with a little lash at the outer end
      return line(`M${x - r * 0.85} ${y + r * 0.1} Q${x} ${y + r * 0.5} ${x + r * 0.85} ${y + r * 0.1}`)
        + line(`M${x + r * 0.85} ${y + r * 0.1} L${x + r * 1.15} ${y - r * 0.15}`);
    case "closed": // asleep: a soft downward curve with a little lash at the outer end
      return line(`M${x - r} ${y - r * 0.1} Q${x} ${y + r * 0.75} ${x + r} ${y - r * 0.1}`);
    case "happy":  // ^ ^
      return line(`M${x - r * 0.95} ${y + r * 0.35} Q${x} ${y - r * 0.95} ${x + r * 0.95} ${y + r * 0.35}`);
    case "x":
      return line(`M${x - r * 0.62} ${y - r * 0.62} L${x + r * 0.62} ${y + r * 0.62} M${x + r * 0.62} ${y - r * 0.62} L${x - r * 0.62} ${y + r * 0.62}`);
    case "sparkle": { // begging: bigger, shining eyes
      const R = r * 1.35;
      return `<ellipse cx="${x}" cy="${y}" rx="${R * 0.92}" ry="${R}" fill="${INK}"/>`
        + `<circle cx="${x + R * 0.3}" cy="${y - R * 0.36}" r="${R * 0.36}" fill="#fff"/>`
        + `<circle cx="${x - R * 0.34}" cy="${y + R * 0.36}" r="${R * 0.17}" fill="#fff"/>`
        + `<circle cx="${x + R * 0.38}" cy="${y + R * 0.42}" r="${R * 0.09}" fill="#fff"/>`;
    }
    default:       // open: a plain black round eye
      return `<ellipse cx="${x}" cy="${y}" rx="${r * 0.9}" ry="${r}" fill="${INK}"/>`;
  }
}

// The mouth: a small "ω", centred on (x, y), w wide
function mouthSvg(x, y, w) {
  const d = w * 0.32;  // how far the two curves dip
  return `<path d="M${x - w / 2} ${y} Q${x - w / 4} ${y + d * 1.6} ${x} ${y} Q${x + w / 4} ${y + d * 1.6} ${x + w / 2} ${y}"
      fill="none" stroke="${INK}" stroke-width="${w * 0.11}" stroke-linecap="round" stroke-linejoin="round"/>`;
}

// A cheek's blush: a soft pink oval (w x h) with three little strokes across it
function blushSvg(x, y, w, h) {
  const s = Math.min(w, h * 1.6) * 0.16;  // stroke length
  const lines = [-1, 0, 1].map((i) => {
    const cx = x + i * w * 0.22;
    return `M${cx - s * 0.35} ${y + s * 0.5} L${cx + s * 0.35} ${y - s * 0.5}`;
  }).join(" ");
  return `<ellipse cx="${x}" cy="${y}" rx="${w * 0.55}" ry="${h * 0.55}" fill="url(#pet-blush)"/>`
    + `<path d="${lines}" stroke="#ef8ea3" stroke-width="${h * 0.09}" stroke-linecap="round" opacity=".75"/>`;
}

const FACE_DEFS = `<defs><radialGradient id="pet-blush">
  <stop offset="0" stop-color="#ffa7b9" stop-opacity=".85"/>
  <stop offset=".6" stop-color="#ffb4c3" stop-opacity=".55"/>
  <stop offset="1" stop-color="#ffc1cd" stop-opacity="0"/></radialGradient></defs>`;

// Icons drawn around (0, 0), about 12 units across. Coloured shapes get a brown outline and
// a pale rim, so they read on the dark and the light floor alike.
const rim = (d, fill) =>
  `<path d="${d}" fill="${fill}" stroke="#fffaf2" stroke-width="3.2" stroke-linejoin="round" paint-order="stroke"/>`
  + `<path d="${d}" fill="${fill}" stroke="${LINE}" stroke-width="1.3" stroke-linejoin="round"/>`;
const stroke = (d, color, w = 2.2) =>
  `<path d="${d}" fill="none" stroke="#fffaf2" stroke-width="${w + 2}" stroke-linecap="round" stroke-linejoin="round"/>`
  + `<path d="${d}" fill="none" stroke="${LINE}" stroke-width="${w + 1}" stroke-linecap="round" stroke-linejoin="round"/>`
  + `<path d="${d}" fill="none" stroke="${color}" stroke-width="${w - 0.4}" stroke-linecap="round" stroke-linejoin="round"/>`;
const ICONS = {
  dots: () => [-4.5, 0, 4.5].map((x) => `<circle cx="${x}" cy="0" r="1.9" fill="#fffaf2" stroke="${LINE}" stroke-width="1.1"/>`).join(""),
  question: () => stroke("M-3 -3.2 Q-3 -6.5 0.4 -6.5 Q3.8 -6.5 3.8 -3.4 Q3.8 -1.2 0.6 0.2 L0.6 1.8", "#f4a24a")
    + `<circle cx="0.6" cy="5.2" r="1.6" fill="#f4a24a" stroke="${LINE}" stroke-width="1"/>`,
  heart: () => rim("M0 5.5 C-7 1 -6.5 -5.5 -2.6 -5.5 C-1.2 -5.5 -0.3 -4.6 0 -3.6 C0.3 -4.6 1.2 -5.5 2.6 -5.5 C6.5 -5.5 7 1 0 5.5 Z", "#f59ab0"),
  z: () => stroke("M-3.2 -3.4 H3.2 L-3.2 3.4 H3.2", "#c9b8f2", 2),
  note: () => rim("M-2.6 4.8 a2.6 2.1 0 1 1 0.1 0 Z", "#a8dcc0")
    + stroke("M-0.2 4.3 V-5.2 Q2.8 -4.2 3.8 -1.6", "#a8dcc0", 1.6),
  carrot: () => stroke("M1 -4.2 L-0.6 -7 M2.4 -4 L3.6 -7 M3.2 -3.2 L6 -4.4", "#8fcf8a", 1.6)
    + rim("M-4.8 6.2 Q-6 5 -4.6 3 L1.6 -3.6 Q3.4 -5 4.4 -3.4 Q5.4 -2 3.8 -0.4 L-2.6 5.6 Q-3.9 6.8 -4.8 6.2 Z", "#f4a24a")
    + `<path d="M0.4 -0.8 L1.8 0.4 M-1.8 1.8 L-0.6 3" stroke="${LINE}" stroke-width="0.8" stroke-linecap="round"/>`,
  sweat: () => rim("M0 -6 Q4.6 0 4.6 2.4 A4.6 4.6 0 0 1 -4.6 2.4 Q-4.6 0 0 -6 Z", "#9fd3f5")
    + `<ellipse cx="-1.6" cy="2" rx="0.9" ry="1.5" fill="#fff" opacity=".85"/>`,
  tear: () => rim("M0 -5 Q3.4 0 3.4 2 A3.4 3.4 0 0 1 -3.4 2 Q-3.4 0 0 -5 Z", "#7fb6ee")
    + rim("M6 0 Q8 3 8 4.2 A2 2 0 0 1 4 4.2 Q4 3 6 0 Z", "#7fb6ee"),
  leaf: () => rim("M-5 5 Q-6 -3 1 -6.5 Q6 -8 6.5 -6.5 Q7 0 1 4 Q-2 6 -5 5 Z", "#a8dcc0")
    + `<path d="M-4.2 4.2 Q0 -1 5 -5.6" fill="none" stroke="${LINE}" stroke-width="0.9" stroke-linecap="round"/>`
    + `<path d="M5.5 2.5 L6.4 4.6 L8.5 5.5 L6.4 6.4 L5.5 8.5 L4.6 6.4 L2.5 5.5 L4.6 4.6 Z" fill="#ffe08a" stroke="${LINE}" stroke-width="0.7" stroke-linejoin="round"/>`,
  swirl: () => stroke("M0.4 0.3 A1.2 1.2 0 1 1 -1.4 -1 A3 3 0 1 1 3 2.2 A5 5 0 1 1 -5.2 -3", "#b9a3e3", 1.8),
};

// ---------------------------------------------------------------- items

const ITEM_ICON = { food: "carrot" };

// ---------------------------------------------------------------- the pet

// The round body per pose (no arms or legs: the shape alone tells the poses apart);
// the ears and face are placed from it.
//   ears: up (spread out, tips drooping) | back (laid back, resting) | flop (down, asleep)
const POSES = {
  stand: { cx: 60, cy: 69, rx: 27, ry: 27, ears: "up" },
  walk:  { cx: 60, cy: 69, rx: 27, ry: 27, ears: "up" },   // bounces (the a-hop animation)
  sit:   { cx: 60, cy: 72, rx: 30, ry: 24, ears: "up" },   // a little lower and wider
  loaf:  { cx: 60, cy: 78, rx: 34, ry: 18, ears: "back" }, // squashed flat, head end still up
  lie:   { cx: 60, cy: 82, rx: 37, ry: 14, ears: "flop" }, // flat out
};

// What each action looks like. Left out: the pose's default / the thought's.
//   eyes:    open | sparkle (begging: bigger, shining) | relaxed (resting) | closed | happy | half | x
//   symbols: icons (ICONS) that float up from the head, one after another
//   extras:  functions returning SVG drawn on the ground (the ball)
//   anim:    CSS animation class for the whole pet
const ACTIONS = {
  thinking:       { pose: "stand", symbols: ["dots"] },
  idle:           { pose: "walk", anim: "a-hop" },
  scavenge:       { pose: "walk", anim: "a-hop", symbols: ["question"] },
  eat:            { pose: "sit", eyes: "happy", anim: "a-chew" },     // chewing only; the food is the item on the cell
  beg:            { pose: "sit", eyes: "sparkle", symbols: ["question"], anim: "a-stretch" },
  sleep:          { pose: "lie", eyes: "closed", anim: "a-breathe", symbols: ["z", "z", "z"] },
  rest:           { pose: "loaf", eyes: "relaxed", symbols: ["leaf"], anim: "a-breathe" },
  seek_attention: { pose: "sit", eyes: "sparkle", symbols: ["heart"], anim: "a-sway" },
  play_alone:     { pose: "walk", eyes: "happy", anim: "a-bounce", symbols: ["note"], extras: [ball] },
  cuddled:        { pose: "sit", eyes: "happy", anim: "a-squish", symbols: ["heart", "heart"] },
  ill:            { pose: "lie", eyes: "x" },
};

// The pet's thought: the symbol that floats up and the eyes, unless the action sets them.
const THOUGHTS = {
  content: { symbols: [],         eyes: "open" },
  hungry:  { symbols: ["carrot"], eyes: "open" },
  tired:   { symbols: ["sweat"],  eyes: "half" },
  lonely:  { symbols: ["tear"],   eyes: "open" },
  sick:    { symbols: ["swirl"],  eyes: "half" },
};

const TURN = 0.2;  // how far the face is turned toward the side it faces (share of the width)

export function drawPet(el, look) {
  const key = JSON.stringify(look) + `#${spritesVersion}`;
  if (el.dataset.look === key) return; // nothing changed, keep the current drawing (and animation)
  el.dataset.look = key;
  clearInterval(el.spriteTimer);

  const name = !look.alive ? "ill" : look.action ?? "thinking";
  const act = ACTIONS[name] ?? { pose: look.pose };
  const thought = THOUGHTS[look.expression] ?? THOUGHTS.content;
  const left = look.facing === "left";
  const still = sprites.bodies[act.pose] && { pose: act.pose, frames: [sprites.bodies[act.pose]] };
  if (sprites.actions[name] || still) drawSprite(el, sprites.actions[name] ?? still, act, thought, left, !look.alive);
  else el.innerHTML = `<div class="shadow"></div>` + petSvg(act, thought, left, !look.alive);
}

// ---------------------------------------------------------------- PNG sprites

let sprites = { actions: {}, bodies: {}, eyes: {}, faces: {} };  // only images that loaded
const boxes = {};  // per pose: where the still body is drawn, in the 120 x 100 box (for the symbols)

// The drawn part of an image (its opaque pixels), in the 120 x 100 units the symbols use
function drawnBox(img) {
  const c = document.createElement("canvas");
  c.width = img.naturalWidth; c.height = img.naturalHeight;
  const g = c.getContext("2d");
  g.drawImage(img, 0, 0);
  const { data, width, height } = g.getImageData(0, 0, c.width, c.height);
  let top = height, left = width, right = 0;
  for (let y = 0; y < height; y += 2) {
    for (let x = 0; x < width; x += 2) {
      if (data[(y * width + x) * 4 + 3] > 64) {
        if (y < top) top = y;
        if (x < left) left = x;
        if (x > right) right = x;
      }
    }
  }
  if (right < left) return null;
  const sx = 120 / width, sy = 100 / height;
  // as a pose for float(): the symbols start just above the top of the drawing
  return { cx: ((left + right) / 2) * sx, cy: top * sy + 8, rx: ((right - left) / 2) * sx * 0.6, ry: 0 };
}
let spritesVersion = 0;                   // bumped when sprites change, so drawPet redraws

// Ask the server which PNGs exist, load them, and switch those actions over once loaded.
// Runs once when the page opens; added files show after a reload.
async function loadSprites() {
  let info;
  try {
    const res = await fetch("/api/sprites", { cache: "no-store" });
    if (!res.ok) return;
    info = await res.json();
  } catch {
    return;  // no sprites: keep the SVG
  }
  for (const p of info.problems ?? []) console.warn("[sprites]", p);
  const load = (url) => new Promise((done) => {
    const img = new Image();
    img.onload = () => done(img);
    img.onerror = () => done(null);
    img.src = url;
  });

  const eyes = {};
  for (const [pose, set] of Object.entries(info.eyes ?? {})) {
    eyes[pose] = {};
    for (const [eye, url] of Object.entries(set)) if (await load(url)) eyes[pose][eye] = url;
  }
  const bodies = {};
  for (const [pose, url] of Object.entries(info.bodies ?? {})) {
    const img = await load(url);
    if (img) { bodies[pose] = url; boxes[pose] = drawnBox(img); }
  }
  const actions = {};
  for (const [name, a] of Object.entries(info.actions ?? {})) {
    const imgs = await Promise.all(a.frames.map(load));
    if (imgs.some((i) => !i)) { console.warn(`[sprites] ${name}: a frame failed to load, using the SVG`); continue; }
    actions[name] = { ...a, width: imgs[0].naturalWidth, height: imgs[0].naturalHeight };
  }
  sprites = { actions, bodies, eyes, faces: info.faces ?? {} };
  spritesVersion++;
}
loadSprites();

// The images stay still except for these: moving actions bounce like a ball (CSS in style.css)
const SPRITE_MOTION = { "a-hop": "s-hop", "a-bounce": "s-bounce" };

function drawSprite(el, s, act, thought, left, ill) {
  const set = sprites.eyes[s.pose] ?? {};
  const eyeKind = act.eyes ?? thought.eyes;
  const eyeUrl = set[eyeKind] ?? set.open;  // a missing eye state falls back to open
  // The face (blush, mouth, eyes) drawn where faces.json says (preferred), else the pose's eye images
  const face = sprites.faces.poses?.[s.pose], canvas = sprites.faces.canvas;
  const eyesLayer = face && canvas
    ? `<svg class="sprite-face" viewBox="0 0 ${canvas[0]} ${canvas[1]}" aria-hidden="true">${FACE_DEFS}`
      + (face.blush ?? []).map(([x, y, w, h]) => blushSvg(x, y, w, h)).join("")
      + (face.mouth ? mouthSvg(...face.mouth) : "")
      + face.eyes.map(([x, y]) => eyeSvg(eyeKind, x, y, face.r)).join("") + `</svg>`
    : eyeUrl ? `<img class="sprite-eyes" src="${eyeUrl}" alt="">` : "";
  const symbols = act.symbols ?? thought.symbols;
  const frames = s.frames.map((url, i) =>
    `<img class="sprite-frame" src="${url}" alt=""${i ? " hidden" : ""}>`).join("");
  el.innerHTML = `<div class="shadow"></div>
    <div class="pet-sprite${ill ? " ill" : ""}">
      <div class="sprite-motion ${SPRITE_MOTION[act.anim] ?? ""}">
        <div class="sprite-layers${left ? " mirrored" : ""}">${frames}${eyesLayer}</div>
      </div>
      <svg class="sprite-symbols" viewBox="0 0 120 100" overflow="visible" aria-hidden="true">${float(boxes[s.pose] ?? POSES[s.pose] ?? POSES.stand, symbols, left)}</svg>
    </div>`;

  // Play the frames in a loop, moving the eyes with the face when settings give offsets
  const imgs = el.querySelectorAll(".sprite-frame");
  const eyesImg = el.querySelector(".sprite-eyes");
  let i = 0;
  const show = () => {
    const off = s.eyeOffsets?.[i];
    if (eyesImg && off) {
      eyesImg.style.transform = `translate(${(off[0] / s.width) * 100}%, ${(off[1] / s.height) * 100}%)`;
    }
  };
  show();
  if (imgs.length > 1) {
    el.spriteTimer = setInterval(() => {
      imgs[i].hidden = true;
      i = (i + 1) % imgs.length;
      imgs[i].hidden = false;
      show();
    }, 1000 / (s.fps || 8));
  }
}

function petSvg(act, thought, left, ill) {
  const p = POSES[act.pose] ?? POSES.stand;
  const eyes = act.eyes ?? thought.eyes;
  const symbols = act.symbols ?? thought.symbols;

  // Drawn facing right, back to front; mirrored as a whole to face left
  const figure = [tail(p), ears(p), body(p), face(p, eyes)].join("");
  const mirror = left ? `transform="translate(120 0) scale(-1 1)"` : "";
  const ground = (act.extras ?? []).map((f) => f(p, left)).join("");
  const cls = ["pet-svg", act.anim ?? "", ill ? "ill" : ""].join(" ");
  return `<svg class="${cls}" viewBox="0 0 120 100" overflow="visible" aria-hidden="true">
    <g class="pet-figure"><g ${mirror}>${figure}</g></g>${ground}${float(p, symbols, left)}</svg>`;
}

function body({ cx, cy, rx, ry }) {
  // Round and a little fuller at the bottom, with a fluffy tuft on top
  const top = cy - ry, bot = cy + ry;
  const fx = cx + rx * TURN * 0.5;
  return `<path class="p-body" d="M${cx} ${top}
      C${cx + rx * 0.62} ${top} ${cx + rx * 1.02} ${cy - ry * 0.5} ${cx + rx} ${cy + ry * 0.1}
      C${cx + rx * 0.98} ${cy + ry * 0.75} ${cx + rx * 0.55} ${bot} ${cx} ${bot}
      C${cx - rx * 0.55} ${bot} ${cx - rx * 0.98} ${cy + ry * 0.75} ${cx - rx} ${cy + ry * 0.1}
      C${cx - rx * 1.02} ${cy - ry * 0.5} ${cx - rx * 0.62} ${top} ${cx} ${top} Z"/>
    <path class="p-fluff" d="M${fx - 7} ${top + 1.5} q1.5 -5 4.5 -1.5 q2 -5.5 5 -1 q3 -4 4.5 2.5"/>`;
}

function ears({ cx, cy, rx, ry, ears: kind }) {
  // Big soft paddle ears with pink insides, spreading out from the top of the head
  const ear = (bx, by, len, angle) => {
    const w = len * 0.62;
    return `<g transform="rotate(${angle} ${bx} ${by})">
      <path class="p-body" d="M${bx - w * 0.3} ${by} C${bx - w * 0.75} ${by - len * 0.45} ${bx - w * 0.8} ${by - len} ${bx} ${by - len}
        C${bx + w * 0.85} ${by - len} ${bx + w * 0.8} ${by - len * 0.45} ${bx + w * 0.3} ${by} Z"/>
      <path class="p-inner" d="M${bx - w * 0.12} ${by - len * 0.12} C${bx - w * 0.38} ${by - len * 0.45} ${bx - w * 0.3} ${by - len * 0.78} ${bx} ${by - len * 0.8}
        C${bx + w * 0.3} ${by - len * 0.78} ${bx + w * 0.38} ${by - len * 0.45} ${bx + w * 0.12} ${by - len * 0.12} Z"/></g>`;
  };
  const top = cy - ry + 5, t = cx + rx * TURN * 0.5;
  if (kind === "back") return ear(t - rx * 0.1, top + 3, 30, -74) + ear(t + rx * 0.12, top + 1, 30, -62);
  if (kind === "flop") return ear(t - rx * 0.2, top + 4, 28, -95) + ear(t + rx * 0.05, top + 3, 28, -82);
  return ear(t - rx * 0.4, top + 1, 34, -34) + ear(t + rx * 0.42, top + 1, 34, 32);
}

function tail({ cx, cy, rx, ry }) {
  // Facing right, so the fluffy cotton tail is on the left (behind)
  const x = cx - rx * 0.92, y = cy + ry * 0.45;
  return `<g class="p-tail"><circle cx="${x}" cy="${y}" r="6"/><circle cx="${x - 4}" cy="${y - 3}" r="4"/>
    <circle cx="${x - 4}" cy="${y + 3}" r="4"/></g>`;
}

function face({ cx, cy, rx, ry }, eyes) {
  // Turned a little to the right; nose, buck teeth and blush never change, only the eyes do
  const x = cx + rx * TURN, y = cy - ry * 0.05, ex = rx * 0.34;
  return [
    eye(x - ex, y, eyes), eye(x + ex, y, eyes),
    `<ellipse class="p-blush" cx="${x - ex - 4}" cy="${y + 8}" rx="5" ry="3"/>`,
    `<ellipse class="p-blush" cx="${x + ex + 4}" cy="${y + 8}" rx="5" ry="3"/>`,
    `<path class="p-nose" d="M${x - 2.6} ${y + 3} Q${x} ${y + 1.8} ${x + 2.6} ${y + 3} Q${x} ${y + 6.4} ${x - 2.6} ${y + 3} Z"/>`,
    `<path class="p-teeth" d="M${x - 2.6} ${y + 8} h5.2 v3.2 q0 1 -1 1 h-3.2 q-1 0 -1 -1 Z M${x} ${y + 8} v4.2"/>`,
    `<path class="p-line thin" d="M${x - 6} ${y + 6.6} Q${x - 3} ${y + 9.6} ${x} ${y + 7.6} Q${x + 3} ${y + 9.6} ${x + 6} ${y + 6.6}"/>`,
  ].join("");
}

function eye(x, y, kind) {
  return eyeSvg(kind, x, y, 4.4);  // the SVG pet's eyes: the same drawings, at its size
}

// Symbols floating up from above the head, one after another (z's grow as they rise)
function float({ cx, cy, rx, ry }, symbols, left) {
  if (!symbols?.length) return "";
  // Beside the ears, on the side the pet faces; z's grow as they go
  const x = left ? cx - rx * 0.95 : cx + rx * 0.95, y = cy - ry - 24;
  return symbols.map((name, i) => {
    const scale = name === "z" ? 0.8 + i * 0.25 : 1.15;
    const dx = (left ? -1 : 1) * i * 8;
    // the animation moves the outer group; the inner one places the icon
    return `<g class="p-sym a-rise" style="animation-delay:${(i * 2.1) / symbols.length}s">
      <g transform="translate(${x + dx} ${y}) scale(${scale})">${ICONS[name]?.() ?? ""}</g></g>`;
  }).join("");
}

// ---------------------------------------------------------------- on the ground

function ball({ cx, rx }, left) {
  const x = left ? cx - rx - 12 : cx + rx + 12;
  return `<g class="a-ball" style="transform-origin:${x}px 96px">
    <circle class="p-ball" cx="${x}" cy="87" r="8"/>
    <path class="p-ball-stripe" d="M${x - 8} 87 Q${x} 81 ${x + 8} 87"/></g>`;
}

// ---------------------------------------------------------------- items

export function drawItem(el, item) {
  // Smaller as it gets eaten (a full portion is 30)
  el.style.setProperty("--size", Math.max(0.35, Math.min(1, item.amount / 30)).toFixed(2));
  const icon = ICONS[ITEM_ICON[item.kind]];
  el.innerHTML = icon
    ? `<svg class="item-svg" viewBox="-8 -9 16 16" aria-hidden="true">${icon()}</svg>`
    : `<div class="item-icon">▪</div>`;
}
