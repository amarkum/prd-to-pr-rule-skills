/* Shared behaviour for the site: a safe DOM builder, the current-page marker, a tooltip, segmented controls with
   deep links, and small HTML charts (bars, grouped bars, dumbbells, a timeline) that each carry a table view.
   Text from data always goes in with textContent, never innerHTML. */
(function () {
  "use strict";

  function h(tag, attrs, ...kids) {
    const el = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs || {})) {
      if (v === null || v === undefined || v === false) continue;
      if (k === "class") el.className = v;
      else if (k === "style" && typeof v === "object") Object.assign(el.style, v);
      else if (k.startsWith("on") && typeof v === "function") el.addEventListener(k.slice(2), v);
      else if (k.startsWith("--")) el.style.setProperty(k, v);
      else el.setAttribute(k, v === true ? "" : v);
    }
    for (const kid of kids.flat()) {
      if (kid === null || kid === undefined || kid === false) continue;
      el.append(kid instanceof Node ? kid : document.createTextNode(String(kid)));
    }
    return el;
  }

  const fmt = {
    n: (v) => Number(v).toLocaleString("en-US"),
    "%": (v) => `${v}%`,
    "%2": (v) => `${Number(v).toFixed(2)}%`,
    m: (v) => `${v} min`,
    tok: (v) => `~${Number(v).toLocaleString("en-US")}`,
    score: (v) => `${v}/100`,
    x: (v) => (v === null ? "not run" : Number(v).toFixed(1))
  };

  /* A clean axis: a 1-2-2.5-5 step, the max a whole number of steps, and room past the longest bar for its label. */
  function scale(maxValue, target = 4, integer = false) {
    const raw = Math.max(maxValue, 1e-9) / target;
    const p = Math.pow(10, Math.floor(Math.log10(raw)));
    const f = raw / p;
    let step = (f <= 1 ? 1 : f <= 2 ? 2 : f <= 2.5 ? 2.5 : f <= 5 ? 5 : 10) * p;
    if (integer) step = Math.max(1, Math.round(step));
    let max = Math.ceil(maxValue / step) * step;
    if (maxValue / max > 0.82) max += step;
    return { max, ticks: Math.round(max / step) };
  }

  function niceMax(v) {
    if (v <= 0) return 1;
    const p = Math.pow(10, Math.floor(Math.log10(v)));
    for (const m of [1, 1.25, 1.5, 2, 2.5, 3, 4, 5, 6, 8, 10]) if (m * p >= v) return m * p;
    return 10 * p;
  }

  /* ---------------------------------------------------------------- tooltip */
  const tip = h("div", { class: "tooltip", role: "status", hidden: true });
  document.addEventListener("DOMContentLoaded", () => document.body.append(tip));
  function showTip(lines, x, y) {
    tip.replaceChildren(...lines.map((l, i) => (i === 0 ? h("b", {}, l) : h("span", {}, l, h("br")))));
    tip.hidden = false;
    const r = tip.getBoundingClientRect();
    const left = Math.min(window.innerWidth - r.width - 12, Math.max(12, x + 14));
    const top = y + r.height + 24 > window.innerHeight ? y - r.height - 14 : y + 16;
    tip.style.left = `${left}px`;
    tip.style.top = `${Math.max(8, top)}px`;
  }
  function hideTip() { tip.hidden = true; }
  function bindTip(el, lines) {
    el.addEventListener("pointermove", (e) => showTip(lines(), e.clientX, e.clientY));
    el.addEventListener("pointerleave", hideTip);
    el.addEventListener("focus", () => { const r = el.getBoundingClientRect(); showTip(lines(), r.left + r.width / 2, r.top + 8); });
    el.addEventListener("blur", hideTip);
  }

  /* ---------------------------------------------------------------- figure frame with table view */
  function figure(target, { title, note, legend, table }) {
    const body = h("div", { class: "viz-body" });
    const tbl = h("div", { class: "tw", hidden: true });
    let showingTable = false;
    const toggle = h("button", { class: "btn quiet small no-print", type: "button", "aria-pressed": "false" }, "Show table");
    toggle.addEventListener("click", () => {
      showingTable = !showingTable;
      tbl.hidden = !showingTable;
      body.hidden = showingTable;
      toggle.textContent = showingTable ? "Show chart" : "Show table";
      toggle.setAttribute("aria-pressed", String(showingTable));
    });
    if (table) {
      const head = h("tr", {}, table.columns.map((c, i) => h("th", { class: table.numeric && table.numeric.includes(i) ? "num" : null }, c)));
      const rows = table.rows.map((r) => h("tr", {}, r.map((c, i) => h("td", { class: table.numeric && table.numeric.includes(i) ? "num" : null },
        c instanceof Node ? c : String(c)))));
      tbl.append(h("table", {}, h("thead", {}, head), h("tbody", {}, rows)));
    }
    const fig = h("figure", { class: "viz" },
      h("figcaption", {}, h("div", {}, h("strong", {}, title), note ? h("div", { class: "note" }, note) : null), table ? toggle : null),
      legend ? h("div", { class: "legend" }, legend.map((l) => h("span", {}, h("i", { "--c": l.color }), l.name))) : null,
      body, tbl);
    target.replaceChildren(fig);
    return body;
  }

  /* ---------------------------------------------------------------- horizontal bars (one series, or emphasis) */
  function hbar(target, o) {
    const auto = scale(Math.max(...o.rows.map((r) => r.value)), 4, o.integer);
    const max = o.max || auto.max;
    const ticks = o.max ? (o.ticks || 4) : auto.ticks;
    const f = fmt[o.fmt || "n"];
    const tf = fmt[o.tickFmt || (o.fmt === "tok" ? "n" : o.fmt || "n")];
    const body = figure(target, {
      title: o.title, note: o.note, legend: o.legend,
      table: { columns: o.columns || ["", "Value", "Note"], numeric: [1], rows: o.rows.map((r) => [r.label, f(r.value), r.note || ""]) }
    });
    const list = h("div", { class: "hbar", role: "list", "--ticks": ticks });
    for (const r of o.rows) {
      const pct = Math.max(0, Math.min(100, (r.value / max) * 100));
      const bar = h("div", { class: "hbar-bar", style: { width: `calc(var(--plot) * ${pct / 100})` }, "--c": r.color || o.color || "var(--series-1)" });
      const val = h("span", { class: "hbar-val", style: { left: `calc(var(--plot) * ${pct / 100} + 6px)` } }, r.display || f(r.value));
      const row = h("div", { class: "hbar-row", role: "listitem", tabindex: "0" },
        h("div", { class: "hbar-label" }, r.dot ? h("span", { class: "stage-dot", "--c": r.dot }) : null,
          h("span", {}, r.label, r.sub ? h("small", {}, r.sub) : null)),
        h("div", { class: "hbar-track" }, bar, val));
      bindTip(row, () => [r.display || f(r.value), r.label, r.note || ""].filter(Boolean));
      list.append(row);
    }
    const axis = h("div", { class: "hbar-axis", "aria-hidden": "true" }, h("div"), h("div", { class: "hbar-ticks" },
      Array.from({ length: ticks + 1 }, (_, i) => h("span", { style: { left: `calc(var(--plot) * ${i / ticks})` } }, tf(+(max * i / ticks).toFixed(2))))));
    list.append(axis);
    body.append(list);
  }

  /* ---------------------------------------------------------------- grouped bars (two series) */
  function grouped(target, o) {
    const f = fmt[o.fmt || "x"];
    const max = o.max || 1;
    const body = figure(target, {
      title: o.title, note: o.note, legend: o.series.map((s) => ({ name: s.name, color: s.color })),
      table: { columns: ["", ...o.series.map((s) => s.name)], numeric: o.series.map((_, i) => i + 1),
               rows: o.rows.map((r) => [r.label, ...r.values.map((v) => f(v))]) }
    });
    const list = h("div", { class: "hbar grouped", role: "list", "--ticks": 4 });
    for (const r of o.rows) {
      const bars = h("div", { class: "hbar-track stack" });
      r.values.forEach((v, i) => {
        const pct = v === null ? 0 : (v / max) * 100;
        bars.append(h("div", { class: "hbar-line" },
          v === null ? h("span", { class: "hbar-val missing" }, "not run")
            : [h("div", { class: "hbar-bar", style: { width: `calc(var(--plot) * ${pct / 100})` }, "--c": o.series[i].color }),
               h("span", { class: "hbar-val", style: { left: `calc(var(--plot) * ${pct / 100} + 6px)` } }, f(v))]));
      });
      const row = h("div", { class: "hbar-row", role: "listitem", tabindex: "0" }, h("div", { class: "hbar-label" }, h("span", {}, r.label)), bars);
      bindTip(row, () => [r.label, ...o.series.map((s, i) => `${s.name}: ${f(r.values[i])}`)]);
      list.append(row);
    }
    list.append(h("div", { class: "hbar-axis", "aria-hidden": "true" }, h("div"), h("div", { class: "hbar-ticks" },
      [0, 0.25, 0.5, 0.75, 1].map((t) => h("span", { style: { left: `calc(var(--plot) * ${t})` } }, (t * max).toFixed(2).replace(/0$/, ""))))));
    body.append(list);
  }

  /* ---------------------------------------------------------------- dumbbells: before and after, each row on its own scale */
  function dumbbell(target, o) {
    const body = figure(target, {
      title: o.title, note: o.note,
      legend: [{ name: "Before, or the comparison point", color: "var(--series-mute)" }, { name: "After, as reported", color: "var(--series-1)" }],
      table: { columns: ["Company", "Measure", "Before", "After"], numeric: [2, 3],
               rows: o.rows.map((r) => [r.company, r.label, `${fmt[r.fmt](r.before)} (${r.unitBefore})`, `${fmt[r.fmt](r.after)} (${r.unitAfter})`]) }
    });
    const list = h("div", { class: "dumbbells", role: "list" });
    for (const r of o.rows) {
      const max = niceMax(Math.max(r.before, r.after) * 1.08);
      const a = (r.before / max) * 100, b = (r.after / max) * 100;
      const lo = Math.min(a, b), hi = Math.max(a, b);
      const f = fmt[r.fmt];
      const track = h("div", { class: "db-track" },
        h("div", { class: "db-line", style: { left: `${lo}%`, width: `${hi - lo}%` } }),
        h("span", { class: "db-dot before", style: { left: `${a}%` } }),
        h("span", { class: "db-dot after", style: { left: `${b}%` } }),
        h("span", { class: `db-num before ${a < b ? "left" : "right"}`, style: { left: `${a}%` } }, f(r.before)),
        h("span", { class: `db-num after ${a < b ? "right" : "left"}`, style: { left: `${b}%` } }, f(r.after)));
      const row = h("div", { class: "db-row", role: "listitem", tabindex: "0" },
        h("div", { class: "db-label" }, h("strong", {}, r.company), h("span", {}, r.label)), track,
        h("a", { class: "db-src small", href: r.url, target: "_blank", rel: "noopener" }, "source"));
      bindTip(row, () => [`${f(r.before)} → ${f(r.after)}`, `${r.company}: ${r.label}`, `${r.unitBefore} → ${r.unitAfter}`]);
      list.append(row);
    }
    body.append(list);
  }

  /* ---------------------------------------------------------------- timeline (weeks) */
  function timeline(target, o) {
    const weeks = o.weeks;
    const body = figure(target, {
      title: o.title, note: o.note,
      table: { columns: ["Setup", "Weeks", "Move on when"], numeric: [],
               rows: o.rows.map((r) => [`${r.setup}. ${r.label}`, `${r.from}-${r.to}`, r.gate]) }
    });
    const grid = h("div", { class: "tl", "--weeks": weeks });
    grid.append(h("div", { class: "tl-head" }, h("div"), h("div", { class: "tl-weeks" },
      Array.from({ length: weeks }, (_, i) => h("span", {}, (i + 1) % 2 ? String(i + 1) : "")))));
    for (const r of o.rows) {
      const bar = h("div", { class: "tl-bar", tabindex: "0", style: { gridColumn: `${r.from} / ${r.to + 1}` } },
        h("span", {}, `Setup ${r.setup}`));
      bindTip(bar, () => [`Weeks ${r.from} to ${r.to}`, r.label, `Move on when: ${r.gate}`]);
      grid.append(h("div", { class: "tl-row" }, h("div", { class: "tl-label" }, r.label), h("div", { class: "tl-track" }, bar)));
    }
    body.append(grid);
  }

  /* ---------------------------------------------------------------- segmented control with optional #deep-link */
  function segmented(target, items, onSelect, { hash = false, label = "" } = {}) {
    const wrap = h("div", { class: "seg", role: "tablist", "aria-label": label });
    const buttons = items.map((it) => h("button", { type: "button", role: "tab", "aria-selected": "false", "data-id": it.id, tabindex: "-1" },
      it.dot ? h("span", { class: "stage-dot", "--c": it.dot }) : null, it.label));
    function select(id, focus) {
      buttons.forEach((b) => {
        const on = b.dataset.id === id;
        b.setAttribute("aria-selected", String(on));
        b.tabIndex = on ? 0 : -1;
        if (on && focus) b.focus();
      });
      onSelect(id);
      if (hash && history.replaceState) { try { history.replaceState(null, "", `#${id}`); } catch (e) { /* sandboxed frames */ } }
    }
    buttons.forEach((b, i) => {
      b.addEventListener("click", () => select(b.dataset.id));
      b.addEventListener("keydown", (e) => {
        const d = e.key === "ArrowRight" || e.key === "ArrowDown" ? 1 : e.key === "ArrowLeft" || e.key === "ArrowUp" ? -1 : 0;
        if (!d) return;
        e.preventDefault();
        select(buttons[(i + d + buttons.length) % buttons.length].dataset.id, true);
      });
    });
    wrap.append(...buttons);
    target.replaceChildren(wrap);
    const fromHash = hash && location.hash.slice(1);
    select(items.some((it) => it.id === fromHash) ? fromHash : items[0].id);
    return select;
  }

  /* ---------------------------------------------------------------- nav */
  document.addEventListener("DOMContentLoaded", () => {
    const holder = document.querySelector("[data-page].page");
    const page = holder && holder.dataset.page;
    document.querySelectorAll(".topnav nav a").forEach((a) => {
      if (a.dataset.page === page) a.setAttribute("aria-current", "page");
    });
  });

  window.Site = { h, fmt, niceMax, scale, hbar, grouped, dumbbell, timeline, segmented, bindTip, showTip, hideTip };
})();
