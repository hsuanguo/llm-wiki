// llm-wiki web UI — vanilla JS, no framework.
// Views: wikis (overview), wiki (page list + editor), graph, log, raw drift.

const state = {
  wikis: [],
  currentWiki: null,
  currentPage: null,
  graph: null,
  sections: ["concepts", "summaries", "entities", "insights"],
};

const $ = (sel, el = document) => el.querySelector(sel);
const $$ = (sel, el = document) => Array.from(el.querySelectorAll(sel));

const api = {
  async get(url) {
    const res = await fetch(url);
    if (!res.ok) throw new Error((await res.json()).error || res.statusText);
    return res.json();
  },
  async send(url, method, body) {
    const res = await fetch(url, {
      method,
      headers: body ? { "Content-Type": "application/json" } : {},
      body: body ? JSON.stringify(body) : undefined,
    });
    if (!res.ok) throw new Error((await res.json()).error || res.statusText);
    return res.status === 204 ? null : res.json();
  },
};

// --- routing ---

function go(hash) {
  if (location.hash !== hash) location.hash = hash;
}

function readRoute() {
  const hash = location.hash.replace(/^#/, "");
  if (!hash || hash === "/") return { view: "wikis" };
  const parts = hash.split("/").filter(Boolean);
  if (parts[0] === "graph") return { view: "graph", wiki: parts[1] };
  if (parts[0] === "log") return { view: "log", wiki: parts[1] };
  if (parts[0] === "raw") return { view: "raw", wiki: parts[1] };
  if (parts.length === 1) return { view: "wiki", wiki: parts[0] };
  if (parts.length >= 2) {
    return { view: "page", wiki: parts[0], rel: parts.slice(1).join("/") };
  }
  return { view: "wikis" };
}

window.addEventListener("hashchange", render);

// --- views ---

async function render() {
  const route = readRoute();
  // sidebar state
  $$(".sidebar__section").forEach((s) => (s.hidden = true));
  if (route.view === "wikis") {
    $('[data-view="wikis"]').hidden = false;
    await loadWikis();
  } else {
    $('[data-view="wiki"]').hidden = false;
    state.currentWiki = route.wiki;
    await renderWikiSidebar(route);
    await renderContent(route);
  }
}

async function loadWikis() {
  const data = await api.get("/api/wikis");
  state.wikis = data.wikis;
  const ul = $("#wikis-list");
  ul.innerHTML = "";
  if (!data.wikis.length) {
    const li = document.createElement("li");
    li.className = "empty";
    li.textContent = "no wikis yet";
    ul.appendChild(li);
  } else {
    for (const w of data.wikis) {
      const li = document.createElement("li");
      const a = document.createElement("a");
      a.href = `#/${encodeURIComponent(w.name)}`;
      a.textContent = w.name;
      const pill = document.createElement("span");
      pill.className = "pill";
      pill.textContent = w.counts.total;
      li.append(a, pill);
      ul.appendChild(li);
    }
  }
  renderWikisOverview(data.wikis);
}

function renderWikisOverview(wikis) {
  const total = wikis.reduce((sum, w) => sum + w.counts.total, 0);
  const concepts = wikis.reduce((s, w) => s + w.counts.concepts, 0);
  const insights = wikis.reduce((s, w) => s + w.counts.insights, 0);
  const entities = wikis.reduce((s, w) => s + w.counts.entities, 0);
  const summaries = wikis.reduce((s, w) => s + w.counts.summaries, 0);

  const c = $("#content");
  c.innerHTML = `
    <div class="page-eyebrow">All wikis · ${wikis.length} vault${wikis.length === 1 ? "" : "s"}</div>
    <h1 class="page-title">Your knowledge, indexed.</h1>
    <div class="page-meta"><span>OKF 0.2 ready</span><span>obsidian-compatible</span><span>${total} pages total</span></div>

    <div class="stats">
      ${statBlock("Concepts", concepts, `${concepts === 0 ? "—" : "compound ideas across the vault"}`, concepts > 0 ? "accent" : "")}
      ${statBlock("Entities", entities, "people, tools, organisations", "")}
      ${statBlock("Insights", insights, "point-in-time syntheses", insights > 0 ? "warm" : "")}
      ${statBlock("Summaries", summaries, "raw-source distillations", "")}
      ${statBlock("Wikis", wikis.length, wikis.length === 1 ? "single vault" : "multi-wiki setup", wikis.length > 1 ? "warm" : "")}
      ${statBlock("Pages", total, "across all wikis", total > 0 ? "accent" : "")}
    </div>

    <h2 class="index-section">Vault</h2>
    ${wikis.length ? `
      <div class="index-list">
        ${wikis.map((w) => `
          <div class="index-row">
            <div class="index-row__title"><a href="#/${encodeURIComponent(w.name)}">${escapeHtml(w.name)}</a></div>
            <div class="index-row__desc">${escapeHtml(w.description || "no description")}</div>
            <div class="index-row__date">${w.counts.total} pages</div>
          </div>`).join("")}
      </div>` : `<p class="empty">No wikis yet. Create one with <em>+ New wiki</em> in the sidebar.</p>`}
  `;
}

function statBlock(label, value, caption, modifier) {
  const klass = modifier ? ` stat__value--${modifier}` : "";
  return `
    <div class="stat">
      <div class="stat__label">${label}</div>
      <div class="stat__value${klass}">${value}</div>
      <div class="stat__caption">${escapeHtml(caption)}</div>
    </div>`;
}

async function renderWikiSidebar(route) {
  $("#wiki-name").textContent = route.wiki;
  const wiki = await api.get(`/api/wikis/${encodeURIComponent(route.wiki)}`);
  const sections = $("#section-list");
  sections.innerHTML = "";
  for (const sec of state.sections) {
    const n = wiki.counts[sec] || 0;
    if (n === 0) continue;
    const li = document.createElement("li");
    const a = document.createElement("a");
    a.href = `#/${encodeURIComponent(route.wiki)}/${sec}`;
    a.textContent = sec;
    const pill = document.createElement("span");
    pill.className = "pill";
    pill.textContent = n;
    li.append(a, pill);
    sections.appendChild(li);
  }
  if (wiki.counts.overview) {
    const li = document.createElement("li");
    const a = document.createElement("a");
    a.href = `#/${encodeURIComponent(route.wiki)}/overview.md`;
    a.textContent = "overview";
    const pill = document.createElement("span");
    pill.className = "pill";
    pill.textContent = "1";
    li.append(a, pill);
    sections.appendChild(li);
  }
}

async function renderContent(route) {
  const c = $("#content");
  if (route.view === "wiki") {
    renderWikiIndex(c, route.wiki);
  } else if (route.view === "page") {
    renderPage(c, route.wiki, route.rel);
  } else if (route.view === "graph") {
    renderGraph(c, route.wiki);
  } else if (route.view === "log") {
    renderLog(c, route.wiki);
  } else if (route.view === "raw") {
    renderRaw(c, route.wiki);
  }
}

async function renderWikiIndex(c, wiki) {
  const data = await api.get(`/api/wikis/${encodeURIComponent(wiki)}`);
  const pages = (await api.get(`/api/wikis/${encodeURIComponent(wiki)}/pages`)).pages;

  const eyebrow = `${wiki} · ${data.counts.total} page${data.counts.total === 1 ? "" : "s"}`;
  const eyebrowAccent = data.counts.total > 0 ? "warm" : "";
  const c0 = pages.filter((p) => p.category === "concepts").length;
  const c1 = pages.filter((p) => p.category === "summaries").length;
  const c2 = pages.filter((p) => p.category === "entities").length;
  const c3 = pages.filter((p) => p.category === "insights").length;

  c.innerHTML = `
    <div class="page-eyebrow">${escapeHtml(eyebrow)}</div>
    <h1 class="page-title">${escapeHtml(wiki)}</h1>
    <div class="page-meta">
      <span>${escapeHtml(data.description || "no description")}</span>
      <span>OKF 0.2 native</span>
    </div>

    <div class="stats">
      ${statBlock("Total", data.counts.total, "concept pages", data.counts.total > 0 ? "accent" : "")}
      ${statBlock("Concepts", c0, "compound ideas", "")}
      ${statBlock("Entities", c2, "people, tools, products", "")}
      ${statBlock("Summaries", c1, "raw-source distillations", "")}
      ${statBlock("Insights", c3, "syntheses", c3 > 0 ? "warm" : "")}
      ${statBlock("Overview", data.counts.overview, "evolving synthesis", data.counts.overview ? "accent" : "")}
    </div>

    ${state.sections
      .filter((s) => pages.some((p) => p.category === s))
      .map((s) => renderSection(s, pages.filter((p) => p.category === s)))
      .join("")}
    ${pages.some((p) => p.category === "overview") ? renderSection("overview", pages.filter((p) => p.category === "overview")) : ""}
  `;
}

function renderSection(name, items) {
  return `
    <h2 class="index-section">${escapeHtml(name)}</h2>
    <div class="index-list">
      ${items
        .map(
          (p) => `
        <div class="index-row">
          <div class="index-row__title"><a href="#/${encodeURIComponent(state.currentWiki)}/${encodeURIComponent(p.rel_path)}">${escapeHtml(p.title || p.rel_path)}</a></div>
          <div class="index-row__desc">${escapeHtml(p.description || "(no description)")}</div>
          <div class="index-row__date">${escapeHtml(p.updated || "")}</div>
        </div>`,
        )
        .join("")}
    </div>`;
}

async function renderPage(c, wiki, rel) {
  try {
    const page = await api.get(`/api/wikis/${encodeURIComponent(wiki)}/pages/${rel}`);
    state.currentPage = page;
    const fm = page.frontmatter || {};
    const tags = (fm.tags || []).join(", ");
    c.innerHTML = `
      <div class="page-eyebrow"><a href="#/${encodeURIComponent(wiki)}">${escapeHtml(wiki)}</a> · ${escapeHtml(rel)}</div>
      <h1 class="page-title">${escapeHtml(fm.title || rel)}</h1>
      <div class="page-meta">
        <span>type: ${escapeHtml(fm.type || "")}</span>
        ${fm.updated ? `<span>updated: ${escapeHtml(fm.updated)}</span>` : ""}
        ${tags ? `<span>tags: ${escapeHtml(tags)}</span>` : ""}
        ${fm.resource ? `<span>resource: ${escapeHtml(fm.resource)}</span>` : ""}
      </div>
      <p class="page-meta"><em>${escapeHtml(fm.description || "")}</em></p>
      <div class="toolbar">
        <button class="btn" data-action="edit">Edit</button>
        <button class="btn btn--ghost" data-action="delete">Delete</button>
      </div>
      <div class="page-body" id="page-body">${renderBody(page.body, wiki)}</div>
    `;
    $('[data-action="edit"]', c).addEventListener("click", () =>
      renderEditor(c, wiki, rel, page),
    );
    $('[data-action="delete"]', c).addEventListener("click", () => deletePage(wiki, rel));
  } catch (e) {
    c.innerHTML = `<div class="flash flash--err">${escapeHtml(e.message)}</div>`;
  }
}

function renderBody(body, wiki) {
  // Render [[wikilink]] and [[slug|label]] as anchors. Escape HTML first.
  const escaped = escapeHtml(body);
  return escaped.replace(/\[\[([^\]|#]+)(?:#[^\]|]*)?(?:\|([^\]]+))?\]\]/g, (_, slug, label) => {
    const text = (label || slug).trim();
    // default to concepts/ if a section is unknown
    const target = `${encodeURIComponent(wiki)}/${encodeURIComponent("concepts/" + slug.replace(/^concepts\//, "") + ".md")}`;
    return `<a href="#/${target}">${escapeHtml(text)}</a>`;
  });
}

function renderEditor(c, wiki, rel, page) {
  const fm = { ...(page.frontmatter || {}) };
  const body = page.body || "";
  c.innerHTML = `
    <div class="page-eyebrow">Editing · ${escapeHtml(rel)}</div>
    <h1 class="page-title">${escapeHtml(fm.title || rel)}</h1>
    <form class="editor" id="edit-form">
      <div class="fm-grid">
        <div>
          <label>Title</label>
          <input name="title" value="${escapeHtml(fm.title || "")}" />
        </div>
        <div>
          <label>Type</label>
          <input name="type" value="${escapeHtml(fm.type || "")}" />
        </div>
        <div style="grid-column: 1 / span 2;">
          <label>Description</label>
          <input name="description" value="${escapeHtml(fm.description || "")}" />
        </div>
        <div>
          <label>Tags (comma-separated)</label>
          <input name="tags" value="${escapeHtml((fm.tags || []).join(", "))}" />
        </div>
        <div>
          <label>Updated (YYYY-MM-DD)</label>
          <input name="updated" value="${escapeHtml(fm.updated || new Date().toISOString().slice(0, 10))}" />
        </div>
        <div style="grid-column: 1 / span 2;">
          <label>Resource</label>
          <input name="resource" value="${escapeHtml(fm.resource || "")}" />
        </div>
      </div>
      <label>Body (markdown, supports [[wikilinks]])</label>
      <textarea name="body">${escapeHtml(body)}</textarea>
      <div class="toolbar">
        <button type="submit" class="btn">Save</button>
        <button type="button" class="btn btn--ghost" id="cancel-edit">Cancel</button>
      </div>
    </form>
  `;
  $("#edit-form", c).addEventListener("submit", async (ev) => {
    ev.preventDefault();
    const fd = new FormData(ev.target);
    const frontmatter = {
      title: fd.get("title") || rel,
      type: fd.get("type") || "concept",
      description: fd.get("description") || "",
      tags: String(fd.get("tags") || "").split(",").map((s) => s.trim()).filter(Boolean),
      updated: fd.get("updated") || new Date().toISOString().slice(0, 10),
    };
    const r = fd.get("resource");
    if (r) frontmatter.resource = r;
    try {
      await api.send(`/api/wikis/${encodeURIComponent(wiki)}/pages/${rel}`, "PUT", {
        frontmatter,
        body: fd.get("body") || "",
      });
      go(`#/${encodeURIComponent(wiki)}/${rel}`);
    } catch (e) {
      alert(e.message);
    }
  });
  $("#cancel-edit", c).addEventListener("click", () => renderPage(c, wiki, rel));
}

async function deletePage(wiki, rel) {
  if (!confirm(`Delete ${rel}?`)) return;
  await api.send(`/api/wikis/${encodeURIComponent(wiki)}/pages/${rel}`, "DELETE");
  go(`#/${encodeURIComponent(wiki)}`);
}

// --- graph ---

async function renderGraph(c, wiki) {
  c.innerHTML = `
    <div class="page-eyebrow">${escapeHtml(wiki)} · graph</div>
    <h1 class="page-title">${escapeHtml(wiki)} — knowledge graph</h1>
    <div class="page-meta"><span>nodes: <em id="node-count">—</em></span><span>edges: <em id="edge-count">—</em></span></div>
    <div class="graph-wrap"><svg id="graph-svg" xmlns="http://www.w3.org/2000/svg"></svg></div>
    <div class="graph-legend">
      <span><span class="swatch" style="background:#143b2c"></span>concept</span>
      <span><span class="swatch" style="background:#b8421a"></span>entity</span>
      <span><span class="swatch" style="background:#1c1b18"></span>summary</span>
      <span><span class="swatch" style="background:#8a8479"></span>insight</span>
      <span><span class="swatch" style="background:#cfc7b8;border:1px solid #1c1b18"></span>overview</span>
    </div>
  `;
  const data = await api.get(`/api/wikis/${encodeURIComponent(wiki)}/graph`);
  state.graph = data;
  $("#node-count").textContent = data.nodes.length;
  $("#edge-count").textContent = data.edges.length;
  drawGraph(data);
}

function drawGraph(data) {
  const svg = $("#graph-svg");
  const W = svg.clientWidth || 800;
  const H = svg.clientHeight || 520;
  svg.setAttribute("viewBox", `0 0 ${W} ${H}`);
  while (svg.firstChild) svg.removeChild(svg.firstChild);

  const nodes = data.nodes.map((n, i) => ({
    ...n,
    x: 60 + ((i * 73) % (W - 120)),
    y: 40 + ((i * 131) % (H - 80)),
    r: 5 + Math.min(8, Math.log2(1 + (n.title || "").length)),
  }));
  const byId = Object.fromEntries(nodes.map((n) => [n.id, n]));

  const colorFor = (type) => {
    switch (type) {
      case "concept": return "#143b2c";
      case "entity": return "#b8421a";
      case "summary": return "#1c1b18";
      case "insight": return "#8a8479";
      case "overview": return "#f6f1e7";
      default: return "#1c1b18";
    }
  };

  // edges
  const ns = "http://www.w3.org/2000/svg";
  for (const e of data.edges) {
    const s = byId[e.source];
    const t = byId[e.target];
    if (!s || !t) continue;
    const line = document.createElementNS(ns, "line");
    line.setAttribute("x1", s.x);
    line.setAttribute("y1", s.y);
    line.setAttribute("x2", t.x);
    line.setAttribute("y2", t.y);
    line.setAttribute("class", "graph-link");
    line.setAttribute("stroke-width", "1");
    svg.appendChild(line);
  }

  // nodes
  for (const n of nodes) {
    const g = document.createElementNS(ns, "g");
    g.setAttribute("class", "graph-node");
    g.setAttribute("transform", `translate(${n.x},${n.y})`);
    const circle = document.createElementNS(ns, "circle");
    circle.setAttribute("r", n.r);
    circle.setAttribute("fill", colorFor(n.type));
    if (n.type === "overview") circle.setAttribute("stroke", "#1c1b18");
    const text = document.createElementNS(ns, "text");
    text.setAttribute("x", n.r + 4);
    text.setAttribute("y", 3);
    text.textContent = n.title;
    g.append(circle, text);
    g.style.cursor = "pointer";
    g.addEventListener("click", () => go(`#/${encodeURIComponent(state.currentWiki)}/${encodeURIComponent(n.id)}`));
    svg.appendChild(g);
  }
}

// --- log + raw ---

async function renderLog(c, wiki) {
  const data = await api.get(`/api/wikis/${encodeURIComponent(wiki)}/log`);
  c.innerHTML = `
    <div class="page-eyebrow">${escapeHtml(wiki)} · log</div>
    <h1 class="page-title">Recent activity</h1>
    <pre class="log">${escapeHtml(data.log || "(empty)")}</pre>
  `;
}

async function renderRaw(c, wiki) {
  const data = await api.get(`/api/wikis/${encodeURIComponent(wiki)}/raw`);
  c.innerHTML = `
    <div class="page-eyebrow">${escapeHtml(wiki)} · raw drift</div>
    <h1 class="page-title">Raw sources</h1>
    <pre class="log">${escapeHtml(data.report || "")}</pre>
    <div class="toolbar"><button class="btn" id="raw-sync">Sync files.log</button></div>
  `;
  $("#raw-sync").addEventListener("click", async () => {
    await api.send(`/api/wikis/${encodeURIComponent(wiki)}/raw/sync`, "POST");
    renderRaw(c, wiki);
  });
}

// --- modal: new wiki / new page ---

function openModal(title, fields) {
  const modal = $("#modal");
  $("#modal-title").textContent = title;
  $("#modal-body").innerHTML = fields
    .map(
      (f) => `
      <label>${escapeHtml(f.label)}</label>
      ${f.textarea
        ? `<textarea name="${f.name}" rows="4">${escapeHtml(f.value || "")}</textarea>`
        : `<input name="${f.name}" value="${escapeHtml(f.value || "")}" placeholder="${escapeHtml(f.placeholder || "")}" />`}
    `,
    )
    .join("");
  modal.returnValue = "";
  modal.showModal();
  return new Promise((resolve) => {
    $("#modal-form").onsubmit = (ev) => {
      // dialog form submit; do not preventDefault — let dialog close
      const data = Object.fromEntries(new FormData(ev.target).entries());
      resolve({ action: ev.submitter?.value, data });
    };
    modal.addEventListener("close", () => resolve({ action: modal.returnValue, data: {} }), { once: true });
  });
}

$("#btn-new-wiki").addEventListener("click", async (ev) => {
  ev.preventDefault();
  const { action, data } = await openModal("Create a new wiki", [
    { name: "name", label: "Wiki name (folder)", placeholder: "greek-history" },
    { name: "domain", label: "Domain / purpose", placeholder: "Greek history" },
    { name: "sources", label: "Source types", value: "articles, URLs, papers" },
  ]);
  if (action !== "confirm" || !data.name) return;
  try {
    await api.send("/api/wikis", "POST", data);
    go(`#/${encodeURIComponent(data.name)}`);
  } catch (e) {
    alert(e.message);
  }
});

$("#btn-new-page").addEventListener("click", async (ev) => {
  ev.preventDefault();
  if (!state.currentWiki) return;
  const { action, data } = await openModal("Create a new page", [
    { name: "rel", label: "Path (e.g. concepts/rag.md)", placeholder: "concepts/new-page.md" },
    { name: "title", label: "Title" },
    { name: "type", label: "Type", value: "concept" },
  ]);
  if (action !== "confirm" || !data.rel) return;
  try {
    await api.send(
      `/api/wikis/${encodeURIComponent(state.currentWiki)}/pages/${data.rel}`,
      "PUT",
      {
        frontmatter: {
          title: data.title || data.rel,
          type: data.type || "concept",
          description: "",
          tags: [],
          updated: new Date().toISOString().slice(0, 10),
        },
        body: `# ${data.title || data.rel}\n\n## Description\n\n## See Also\n\n`,
      },
    );
    go(`#/${encodeURIComponent(state.currentWiki)}/${data.rel}`);
  } catch (e) {
    alert(e.message);
  }
});

$("#back-to-wikis").addEventListener("click", (ev) => {
  ev.preventDefault();
  go("#/");
});

// --- helpers ---

function escapeHtml(s) {
  if (s === null || s === undefined) return "";
  return String(s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

// Expose a tiny render hook so the brand link goes home.
$("#brand-link").addEventListener("click", (ev) => {
  ev.preventDefault();
  go("#/");
});

render();