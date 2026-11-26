import { drawItem, drawPet } from "./pet-view.js";

const $ = (id) => document.getElementById(id);
const POLL_MS = 1000;
let busy = false;   // a click's request is in flight
let last = null;    // the last state from the server
let facing = "right"; // which way the pet faces: the way it last moved
let lastX = null;     // the pet's x at the last refresh

async function api(path, body) {
  const res = await fetch(path, body === undefined ? {} : {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error((await res.json()).error ?? res.statusText);
  return res.json();
}

// ---------------------------------------------------------------- drawing

function render(s) {
  last = s;
  document.title = `${s.name} · pet`;
  $("name").textContent = s.name;
  $("age").textContent = `${Math.floor(s.age)}s old`;


  drawWorld(s);
}

function drawWorld(s) {
  const w = s.world;
  const world = $("world");
  world.style.setProperty("--cols", w.width);
  world.style.setProperty("--rows", w.height);
  const squash = parseFloat(getComputedStyle(world).getPropertyValue("--squash")) || 0.5;
  $("grid").style.aspectRatio = `${w.width} / ${w.height * squash}`;
  world.classList.toggle("fallen", !s.alive);

  // Items: one element per item, placed on its cell
  const items = $("items");
  items.replaceChildren();
  for (const i of w.items) {
    const el = document.createElement("div");
    el.className = `item item-${i.kind}`;
    el.style.setProperty("--x", i.x);
    el.style.setProperty("--y", i.y);
    el.title = `${i.kind} ${i.amount.toFixed(0)} at (${i.x}, ${i.y})`;
    drawItem(el, i);
    items.append(el);
  }

  // The pet: moves to its cell (CSS animates the move)
  const pet = $("pet");
  if (lastX !== null && w.x !== lastX) facing = w.x < lastX ? "left" : "right";
  lastX = w.x;
  pet.style.setProperty("--x", w.x);
  pet.style.setProperty("--y", w.y);
  pet.title = s.alive ? `${s.name} at (${w.x}, ${w.y}) · click to cuddle` : `${s.name} has fallen ill`;
  drawPet(pet, { ...s.look, facing });
}

// ---------------------------------------------------------------- clicking

function interactionKey(name) {
  return last?.interactions.find((i) => i.name === name)?.key;
}

async function act(body) {
  if (busy || !last?.alive) return;
  busy = true;
  try { render(await api("/api/interact", body)); $("error").textContent = ""; }
  catch (e) { $("error").textContent = e.message; }
  finally { busy = false; }
}

// Click the pet: cuddle
$("pet").addEventListener("click", (ev) => {
  ev.stopPropagation();
  const key = interactionKey("cuddle");
  if (key) act({ key });
});

// Click the floor (the strip of light grass, from FLOOR_TOP of the scene down): put food on
// the nearest cell of the grid, which is a little narrower than the strip; clicks above it
// (on the hills and the sky) do nothing
const FLOOR_TOP = 465 / 900;  // the strip's top edge in scene/background.svg
$("world").addEventListener("click", (ev) => {
  const key = interactionKey("feed");
  if (!key || !last) return;
  const scene = $("world").getBoundingClientRect();
  if ((ev.clientY - scene.top) / scene.height < FLOOR_TOP) return;
  const box = $("grid").getBoundingClientRect();
  const clamp = (v, n) => Math.min(Math.max(v, 0), n - 1);
  const x = clamp(Math.floor(((ev.clientX - box.left) / box.width) * last.world.width), last.world.width);
  const y = clamp(Math.floor(((ev.clientY - box.top) / box.height) * last.world.height), last.world.height);
  act({ key, x, y });
});

async function poll() {
  try { if (!busy) render(await api("/api/state")); $("error").textContent = ""; }
  catch (e) { $("error").textContent = "can't reach the server"; }
  setTimeout(poll, POLL_MS);
}

poll();
