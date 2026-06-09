// manim studio — single-page client
const $ = (id) => document.getElementById(id);
const promptEl = $("prompt");
const goBtn    = $("go");
const errEl    = $("err");
const logEl    = $("log");
const statusEl = $("status");
const resultEl = $("result");
const dotEl    = $("dot");
const activeEl = $("active");
const recentEl = $("recent");

let currentAbort = null;

function setStatus(text, klass) {
  statusEl.textContent = text;
  statusEl.className = "status " + (klass || "");
}

function clearLog() {
  logEl.innerHTML = "";
  resultEl.classList.add("hidden");
  resultEl.innerHTML = "";
}

function appendLog(line, klass) {
  const span = document.createElement("span");
  if (klass) span.className = klass;
  span.textContent = line + "\n";
  logEl.appendChild(span);
  logEl.scrollTop = logEl.scrollHeight;
}

function classify(line) {
  const l = line.toLowerCase();
  if (l.startsWith("done") || l.includes("rendered")) return "ok";
  if (l.includes("fail") || l.includes("error") || l.startsWith("render < ")) return "err";
  if (l.startsWith("openai") || l.startsWith("sandbox") || l.startsWith("queued") || l.startsWith("draft") || l.startsWith("attempt")) return "info";
  return null;
}

async function submit() {
  const prompt = promptEl.value.trim();
  errEl.textContent = "";
  if (prompt.length < 5) { errEl.textContent = "say a bit more"; return; }

  goBtn.disabled = true;
  clearLog();
  setStatus("submitting…", "");
  appendLog("> " + prompt, "info");
  document.getElementById("output-panel")?.scrollIntoView({behavior: "smooth", block: "start"});

  let res;
  try {
    res = await fetch("/api/jobs", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({prompt}),
    });
  } catch (e) {
    errEl.textContent = "network error";
    setStatus("failed", "failed");
    goBtn.disabled = false;
    return;
  }
  if (!res.ok) {
    const txt = await res.text();
    errEl.textContent = txt.replace(/^[\s\S]*"detail":"?/, "").replace(/"?\}$/, "").slice(0, 200) || res.statusText;
    setStatus("rejected", "failed");
    goBtn.disabled = false;
    return;
  }
  const {job_id} = await res.json();
  setStatus("running", "");
  watch(job_id);
}

async function watch(job_id) {
  if (currentAbort) currentAbort.abort();
  const ctrl = new AbortController();
  currentAbort = ctrl;
  let offset = 0;
  let printed = "";

  while (!ctrl.signal.aborted) {
    let r;
    try {
      r = await fetch(`/api/jobs/${job_id}/poll?since=${offset}`, {signal: ctrl.signal});
    } catch (e) {
      if (ctrl.signal.aborted) return;
      await sleep(1500);
      continue;
    }
    if (!r.ok) { await sleep(1500); continue; }
    const data = await r.json();
    if (data.delta) {
      printed += data.delta;
      // flush in whole lines so classify works
      const parts = printed.split("\n");
      printed = parts.pop();
      for (const line of parts) {
        if (line.length) appendLog(line, classify(line));
      }
    }
    offset = data.offset || offset;
    if (data.status === "done") {
      if (printed) { appendLog(printed, classify(printed)); printed = ""; }
      setStatus("done", "done");
      appendLog("video ready: " + data.video_url, "ok");
      showResult(data.video_url);
      goBtn.disabled = false;
      currentAbort = null;
      return;
    }
    if (data.status === "failed") {
      if (printed) { appendLog(printed, classify(printed)); printed = ""; }
      setStatus("failed", "failed");
      appendLog("error: " + (data.error || "unknown"), "err");
      goBtn.disabled = false;
      currentAbort = null;
      return;
    }
    // brief pause if the server returned immediately with no delta
    if (!data.delta) await sleep(500);
  }
}

function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

function showResult(url) {
  resultEl.classList.remove("hidden");
  resultEl.innerHTML = `
    <video controls autoplay loop muted playsinline src="${url}"></video>
    <div class="links">
      <a href="${url}" target="_blank" rel="noreferrer">open mp4 ↗</a>
      <a href="${url}" download>download</a>
    </div>`;
}

function fmtAge(ts) {
  const s = Math.max(0, Math.floor(Date.now()/1000 - ts));
  if (s < 60) return s + "s ago";
  if (s < 3600) return Math.floor(s/60) + "m ago";
  if (s < 86400) return Math.floor(s/3600) + "h ago";
  return Math.floor(s/86400) + "d ago";
}

function renderRecent(items) {
  recentEl.innerHTML = "";
  if (!items.length) {
    const li = document.createElement("li");
    li.innerHTML = '<span class="empty">no renders yet — be the first</span>';
    recentEl.appendChild(li);
    return;
  }
  for (const it of items) {
    const li = document.createElement("li");
    const url = it.video_path ? `/videos/${it.video_path.split("/").pop()}` : "#";
    li.innerHTML = `
      <span class="when">${fmtAge(it.created_at)}</span>
      <span class="prompt-text" title="${escapeHtml(it.prompt)}">${escapeHtml(it.prompt)}</span>
      <a href="${url}" target="_blank" rel="noreferrer">▶ play</a>
    `;
    recentEl.appendChild(li);
  }
}

function escapeHtml(s) {
  return s.replace(/[&<>"']/g, (c) => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
}

async function watchStats() {
  while (true) {
    try {
      const r = await fetch("/api/stats", {cache: "no-store"});
      if (r.ok) {
        const s = await r.json();
        activeEl.textContent = s.active;
        dotEl.classList.toggle("live", s.active > 0);
        renderRecent(s.recent || []);
      }
    } catch {}
    await sleep(2500);
  }
}

// hotkey
document.addEventListener("keydown", (e) => {
  if ((e.metaKey || e.ctrlKey) && e.key === "Enter") {
    e.preventDefault();
    if (!goBtn.disabled) submit();
  }
});
goBtn.addEventListener("click", submit);

watchStats();
