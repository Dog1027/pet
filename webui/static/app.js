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

// How long the pet has lived, in words: 「出生 2 分 15 秒」
function age(seconds) {
  const s = Math.floor(seconds), m = Math.floor(s / 60), h = Math.floor(m / 60);
  if (h) return `出生 ${h} 小時 ${m % 60} 分`;
  if (m) return `出生 ${m} 分 ${s % 60} 秒`;
  return `出生 ${s} 秒`;
}

function render(s) {
  last = s;
  $("naming").hidden = s.named;
  if (!s.named) {  // no pet yet: an empty meadow and the naming card
    document.title = "寵物";
    $("name").textContent = "";
    $("age").textContent = "";
    $("fallen").hidden = true;
    $("items").replaceChildren();
    $("pet").replaceChildren();
    delete $("pet").dataset.look;
    $("world").classList.remove("fallen");
    const input = $("pet-name");
    if (!input.dataset.ready) {  // set up once per card, so typing isn't overwritten by polls
      input.dataset.ready = "1";
      input.maxLength = s.name_max;
      input.placeholder = s.suggested_name;
      input.value = "";
      setTimeout(() => input.focus(), 0);
    }
    return;
  }
  delete $("pet-name").dataset.ready;
  document.title = `${s.name} · 寵物`;
  $("name").textContent = s.name;
  $("age").textContent = age(s.age);


  drawWorld(s);
  $("fallen").hidden = s.alive;
  $("fallen-name").textContent = s.name;
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
    el.title = `紅蘿蔔（剩 ${Math.round((i.amount / 30) * 100)}%）`;
    drawItem(el, i);
    items.append(el);
  }

  // The pet: moves to its cell (CSS animates the move)
  const pet = $("pet");
  if (lastX !== null && w.x !== lastX) facing = w.x < lastX ? "left" : "right";
  lastX = w.x;
  pet.style.setProperty("--x", w.x);
  pet.style.setProperty("--y", w.y);
  pet.title = s.alive ? `${s.name} · 點一下摸摸牠` : `${s.name} 生病倒下了`;
  drawPet(pet, { ...s.look, facing });
}

// ---------------------------------------------------------------- clicking

function interactionKey(name) {
  return last?.interactions.find((i) => i.name === name)?.key;
}

async function act(body) {
  if (busy || !last?.named || !last.alive) return;
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

// Naming the new pet: an empty name takes the suggested one
$("naming").addEventListener("submit", async (ev) => {
  ev.preventDefault();
  if (busy) return;
  const input = $("pet-name");
  const name = input.value.trim() || input.placeholder;
  busy = true;
  try {
    lastX = null;
    facing = "right";
    render(await api("/api/start", { name }));
    $("error").textContent = "";
  } catch (e) { $("error").textContent = e.message; }
  finally { busy = false; }
});

// Fallen ill: start over with a new pet (named again)
$("restart").addEventListener("click", async (ev) => {
  ev.stopPropagation();
  if (busy) return;
  busy = true;
  try {
    lastX = null;
    facing = "right";
    render(await api("/api/restart", {}));
    $("error").textContent = "";
  } catch (e) { $("error").textContent = e.message; }
  finally { busy = false; }
});

async function poll() {
  try { if (!busy) render(await api("/api/state")); $("error").textContent = ""; }
  catch (e) { $("error").textContent = "連不上伺服器"; }
  setTimeout(poll, POLL_MS);
}

poll();
