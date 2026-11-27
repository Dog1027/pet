// How the pet and the items are drawn. Change this file to change the pet's look.
//
// drawPet(el, look) is called on every refresh with the pet's element (#pet). The page
// positions the element on the pet's cell (and moves it); this function only draws what is
// inside it. The floor is seen at a slant, so things stand on their cell: each child is
// anchored at the cell's centre and rises above it (see style.css). Clicking the drawing
// (.pet-sprite) cuddles the pet.
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
// The pet is Moffy, from PNGs in webui/static/sprites/ (names: webui/sprites.py, served as
// /api/sprites; made from design.png by `just sprites`): each action shows its pose's body
// (or the action's own frames, in a loop), mirrored to face left. On the body this file draws
// the face (blush, mouth, eyes where faces.json says) and the symbols floating up from the
// head; only the eyes change with what the pet does or thinks:
//   ACTIONS  per action: pose, eyes, symbols, motion
//   THOUGHTS the symbol and eyes for each thought, when the action doesn't set them

// ---------------------------------------------------------------- eyes and icons
// Drawn here in the style of design.jpg: soft rounded strokes, the palette's pink / orange /
// mint, a brown outline on coloured icons.

const INK = "#111";      // eyes and mouth: plain black
const LINE = "#6e4c3d";  // icon outlines

// One eye of radius r centred on (x, y) (faces.json gives where and how big)
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
    case "closed": // asleep: a soft downward curve
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
  carrot: () => carrotSvg(),
  sweat: () => rim("M0 -6 Q4.6 0 4.6 2.4 A4.6 4.6 0 0 1 -4.6 2.4 Q-4.6 0 0 -6 Z", "#9fd3f5")
    + `<ellipse cx="-1.6" cy="2" rx="0.9" ry="1.5" fill="#fff" opacity=".85"/>`,
  tear: () => rim("M0 -5 Q3.4 0 3.4 2 A3.4 3.4 0 0 1 -3.4 2 Q-3.4 0 0 -5 Z", "#7fb6ee")
    + rim("M6 0 Q8 3 8 4.2 A2 2 0 0 1 4 4.2 Q4 3 6 0 Z", "#7fb6ee"),
  leaf: () => rim("M-5 5 Q-6 -3 1 -6.5 Q6 -8 6.5 -6.5 Q7 0 1 4 Q-2 6 -5 5 Z", "#a8dcc0")
    + `<path d="M-4.2 4.2 Q0 -1 5 -5.6" fill="none" stroke="${LINE}" stroke-width="0.9" stroke-linecap="round"/>`
    + `<path d="M5.5 2.5 L6.4 4.6 L8.5 5.5 L6.4 6.4 L5.5 8.5 L4.6 6.4 L2.5 5.5 L4.6 4.6 Z" fill="#ffe08a" stroke="${LINE}" stroke-width="0.7" stroke-linejoin="round"/>`,
  swirl: () => stroke("M0.4 0.3 A1.2 1.2 0 1 1 -1.4 -1 A3 3 0 1 1 3 2.2 A5 5 0 1 1 -5.2 -3", "#b9a3e3", 1.8),
};

// A plump carrot lying on its side, leaves at the top right, tip at the bottom left (the
// line CARROT_TOP -> CARROT_TIP below, which the bites follow). Warm orange with a darker
// orange outline, a highlight and a few ridges; three round mint leaves.
function carrotSvg() {
  const leaf = (x, y, rot, rx = 1.9, ry = 3.3) =>
    `<ellipse cx="${x}" cy="${y}" rx="${rx}" ry="${ry}" transform="rotate(${rot} ${x} ${y})"
      fill="#a9dea0" stroke="#5f9e62" stroke-width="0.9"/>`;
  const body = "M-6 6.9 Q-6.9 6.1 -5.8 4.1 L0.2 -3.3 Q2.4 -6 5 -4.3 Q7.2 -2.6 5.2 -0.3 L-3.6 6.1 Q-5 7.4 -6 6.9 Z";
  return `<g stroke-linejoin="round" stroke-linecap="round">`
    + `<path d="${body}" fill="none" stroke="#fffaf2" stroke-width="3.2"/>`   // pale rim, for the dark floor
    + leaf(3.2, -6.6, -28) + leaf(6.6, -6.4, 40) + leaf(5.3, -7.6, 8, 1.7, 3.6)
    + `<path d="${body}" fill="#f7983a" stroke="#c4621c" stroke-width="1.1"/>`
    + `<path d="M-4.4 4.4 L0.9 -2.1 Q2.3 -3.9 4 -3.3" fill="none" stroke="#ffc888" stroke-width="1.4" opacity=".9"/>`
    + `<path d="M0.4 0.4 l1.5 1.1 M-1.6 2.6 l1.3 1 M2.6 -1.8 l1.2 0.9" fill="none" stroke="#c4621c" stroke-width="0.8"/>`
    + `</g>`;
}

// ---------------------------------------------------------------- the pet

// What each action looks like. Left out: the thought's eyes and symbols, no motion.
//   pose:    which body (stand / walk / sit / loaf / lie)
//   eyes:    open | sparkle (begging: bigger, shining) | relaxed (resting) | closed | happy | half | x
//   symbols: icons (ICONS) that float up from the head, one after another
//   motion:  hop (bouncing along) | bounce (bouncing in place); the picture is still otherwise
const ACTIONS = {
  thinking:       { pose: "stand", symbols: ["dots"] },
  idle:           { pose: "walk", motion: "hop" },
  scavenge:       { pose: "walk", motion: "hop", symbols: ["question"] },
  eat:            { pose: "sit", eyes: "happy" },  // the food is the item on the cell
  beg:            { pose: "sit", eyes: "sparkle", symbols: ["question"] },
  sleep:          { pose: "lie", eyes: "closed", symbols: ["z", "z", "z"] },
  rest:           { pose: "loaf", eyes: "relaxed", symbols: ["leaf"] },
  seek_attention: { pose: "sit", eyes: "sparkle", symbols: ["heart"] },
  play_alone:     { pose: "walk", eyes: "happy", motion: "bounce", symbols: ["note"] },
  cuddled:        { pose: "sit", eyes: "happy", symbols: ["heart", "heart"] },
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

export function drawPet(el, look) {
  if (!spritesLoaded) return;  // nothing until the pictures are in
  const key = JSON.stringify(look) + `#${spritesVersion}`;
  if (el.dataset.look === key) return; // nothing changed, keep the current drawing (and animation)
  el.dataset.look = key;
  clearInterval(el.spriteTimer);

  const name = !look.alive ? "ill" : look.action ?? "thinking";
  const act = ACTIONS[name] ?? { pose: look.pose };
  const thought = THOUGHTS[look.expression] ?? THOUGHTS.content;
  const body = sprites.actions[name]
    ?? (sprites.bodies[act.pose] && { pose: act.pose, frames: [sprites.bodies[act.pose]] });
  if (body) drawSprite(el, body, act, thought, look.facing === "left", !look.alive);
  else el.innerHTML = "";  // no picture for this pose (loadSprites said why in the console)
}

// ---------------------------------------------------------------- loading the PNGs

let sprites = { actions: {}, bodies: {}, faces: {} };  // only images that loaded
const boxes = {};          // per pose: where the body is drawn, in the 120 x 100 box (for the symbols)
let spritesVersion = 0;    // bumped when sprites change, so drawPet redraws
let spritesLoaded = false; // drawPet waits for this

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
  // the symbols start just above the top of the drawing
  return { cx: ((left + right) / 2) * sx, cy: top * sy + 8, rx: ((right - left) / 2) * sx * 0.6, ry: 0 };
}

// Ask the server which PNGs exist and load them all at once. Runs once when the page opens;
// changed files show after a reload.
async function loadSprites() {
  try {
    await loadSpriteImages();
  } finally {
    spritesLoaded = true;
  }
}

async function loadSpriteImages() {
  let info;
  try {
    const res = await fetch("/api/sprites", { cache: "no-store" });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    info = await res.json();
  } catch (e) {
    console.error("[sprites] can't list the pet's pictures:", e);
    return;
  }
  for (const p of info.problems ?? []) console.warn("[sprites]", p);
  if (!Object.keys(info.bodies ?? {}).length && !Object.keys(info.actions ?? {}).length) {
    console.error("[sprites] no pictures of the pet in webui/static/sprites/; run `just sprites`");
  }
  const load = (url) => new Promise((done) => {
    const img = new Image();
    img.onload = () => done(img);
    img.onerror = () => { console.error("[sprites] can't load", url); done(null); };
    img.src = url;
  });

  const bodies = {}, actions = {};
  await Promise.all([
    ...Object.entries(info.bodies ?? {}).map(async ([pose, url]) => {
      const img = await load(url);
      if (img) { bodies[pose] = url; boxes[pose] = drawnBox(img); }
    }),
    ...Object.entries(info.actions ?? {}).map(async ([name, a]) => {
      const imgs = await Promise.all(a.frames.map(load));
      if (imgs.every(Boolean)) actions[name] = a;
    }),
  ]);
  sprites = { actions, bodies, faces: info.faces ?? {} };
  spritesVersion++;
}
loadSprites();

const DEFAULT_BOX = { cx: 60, cy: 30, rx: 20, ry: 0 };  // where symbols go if a pose wasn't measured

function drawSprite(el, s, act, thought, left, ill) {
  const eyes = act.eyes ?? thought.eyes;
  // The face (blush, mouth, eyes), where faces.json says
  const face = sprites.faces.poses?.[s.pose], canvas = sprites.faces.canvas;
  const faceLayer = face && canvas
    ? `<svg class="sprite-face" viewBox="0 0 ${canvas[0]} ${canvas[1]}" aria-hidden="true">${FACE_DEFS}`
      + (face.blush ?? []).map(([x, y, w, h]) => blushSvg(x, y, w, h)).join("")
      + (face.mouth ? mouthSvg(...face.mouth) : "")
      + face.eyes.map(([x, y]) => eyeSvg(eyes, x, y, face.r)).join("") + `</svg>`
    : "";
  const frames = s.frames.map((url, i) =>
    `<img class="sprite-frame" src="${url}" alt=""${i ? " hidden" : ""}>`).join("");
  el.innerHTML = `<div class="shadow"></div>
    <div class="pet-sprite${ill ? " ill" : ""}">
      <div class="sprite-motion ${act.motion ? `s-${act.motion}` : ""}">
        <div class="sprite-layers${left ? " mirrored" : ""}">${frames}${faceLayer}</div>
      </div>
      <svg class="sprite-symbols" viewBox="0 0 120 100" overflow="visible" aria-hidden="true">${float(boxes[s.pose] ?? DEFAULT_BOX, act.symbols ?? thought.symbols, left)}</svg>
    </div>`;

  // An action with several frames plays them in a loop
  const imgs = el.querySelectorAll(".sprite-frame");
  if (imgs.length > 1) {
    let i = 0;
    el.spriteTimer = setInterval(() => {
      imgs[i].hidden = true;
      i = (i + 1) % imgs.length;
      imgs[i].hidden = false;
    }, 1000 / (s.fps || 8));
  }
}

// Symbols floating up from above the head, one after another (z's grow as they rise)
function float({ cx, cy, rx, ry }, symbols, left) {
  if (!symbols?.length) return "";
  // Beside the ears, on the side the pet faces
  const x = left ? cx - rx * 0.95 : cx + rx * 0.95, y = cy - ry - 24;
  return symbols.map((name, i) => {
    const scale = name === "z" ? 0.8 + i * 0.25 : 1.15;
    const dx = (left ? -1 : 1) * i * 8;
    // the animation moves the outer group; the inner one places the icon
    return `<g class="p-sym a-rise" style="animation-delay:${(i * 2.1) / symbols.length}s">
      <g transform="translate(${x + dx} ${y}) scale(${scale})">${ICONS[name]?.() ?? ""}</g></g>`;
  }).join("");
}

// ---------------------------------------------------------------- items

const ITEM_ICON = { food: "carrot" };

export function drawItem(el, item) {
  // Food is eaten away bit by bit: the share left of a full portion (30) stays, cut off with
  // a bitten edge; the item keeps its size
  const left = Math.max(0, Math.min(1, item.amount / 30));
  const icon = ICONS[ITEM_ICON[item.kind]];
  if (!icon) { el.innerHTML = `<div class="item-icon">▪</div>`; return; }
  const id = `bite-${item.x}-${item.y}`;
  const mask = item.kind === "food" && left < 0.999 ? biteMask(id, left) : "";
  el.innerHTML = `<svg class="item-svg" viewBox="-8 -9 16 16" aria-hidden="true">${mask}
    <g${mask ? ` mask="url(#${id})"` : ""}>${icon()}</g></svg>`;
}

// The carrot (ICONS.carrot) runs from where its leaves grow (top right) to its tip (bottom
// left); it is eaten from the tip. The mask keeps the `left` share of it next to the leaves,
// with three bites taken out of the cut.
const CARROT_TOP = [4.2, -3.6], CARROT_TIP = [-6.2, 7.2];

function biteMask(id, left) {
  const [sx, sy] = CARROT_TOP, [ex, ey] = CARROT_TIP;
  const len = Math.hypot(ex - sx, ey - sy);
  const ux = (ex - sx) / len, uy = (ey - sy) / len;  // towards the tip
  const nx = -uy, ny = ux;                           // across the carrot
  const cx = sx + ux * len * left, cy = sy + uy * len * left;  // where it's bitten off
  const pt = (a, b) => `${cx + ux * a + nx * b} ${cy + uy * a + ny * b}`;
  const gone = `M${pt(0, -20)} L${pt(30, -20)} L${pt(30, 20)} L${pt(0, 20)} Z`;
  const bites = [-2.4, 0, 2.4].map((k, i) =>
    `<circle cx="${cx - ux * 0.2 + nx * k}" cy="${cy - uy * 0.2 + ny * k}" r="${i === 1 ? 1.5 : 1.25}" fill="#000"/>`).join("");
  return `<defs><mask id="${id}" maskUnits="userSpaceOnUse" x="-12" y="-12" width="24" height="24">
    <rect x="-12" y="-12" width="24" height="24" fill="#fff"/><path d="${gone}" fill="#000"/>${bites}</mask></defs>`;
}
