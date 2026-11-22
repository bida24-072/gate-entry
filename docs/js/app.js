import { api, ApiError, getSession, setSession, clearSession } from "./api.js";

/* ---------- tiny DOM helper: text only, never innerHTML (names are untrusted input) ---------- */
function h(tag, props = {}, ...children) {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(props)) {
    if (k === "class") el.className = v;
    else if (k.startsWith("on")) el.addEventListener(k.slice(2), v);
    else if (v !== false && v != null) el.setAttribute(k, v === true ? "" : String(v));
  }
  for (const c of children.flat()) el.append(c instanceof Node ? c : document.createTextNode(String(c ?? "")));
  return el;
}

const pretty = (s) => String(s).replaceAll("_", " ");
const fmtTime = (iso) => new Date(iso).toLocaleTimeString();
const badge = (text, kind) => h("span", { class: `badge ${kind}` }, pretty(text));

function ago(iso) {
  if (!iso) return "never";
  const s = Math.max(0, Math.round((Date.now() - new Date(iso).getTime()) / 1000));
  if (s < 60) return `${s}s ago`;
  if (s < 3600) return `${Math.round(s / 60)}m ago`;
  if (s < 86400) return `${Math.round(s / 3600)}h ago`;
  return `${Math.round(s / 86400)}d ago`;
}

function note() {
  const el = h("p", { class: "note", role: "status" });
  return {
    el,
    set(text, kind = "") {
      el.className = `note ${kind}`;
      el.textContent = text;
    },
  };
}

function field(label, input) {
  return h("label", {}, label, input);
}

/* Polls fn; backs off on errors; skips work while the tab is hidden. Returns a stop function. */
function poller(fn, baseMs) {
  let stopped = false;
  let timer = null;
  let delay = baseMs;
  const tick = async () => {
    if (stopped) return;
    if (!document.hidden) {
      try {
        await fn();
        delay = baseMs;
      } catch (e) {
        if (e instanceof ApiError && e.status === 401) return;
        delay = Math.min(delay * 2, 30000);
      }
    }
    if (!stopped) timer = setTimeout(tick, delay);
  };
  tick();
  return () => {
    stopped = true;
    clearTimeout(timer);
  };
}

/* ---------- views: each returns { el, cleanup? } ---------- */

function viewLogin() {
  const msg = note();
  const email = h("input", { type: "email", required: true, autocomplete: "username" });
  const password = h("input", { type: "password", required: true, autocomplete: "current-password" });
  const btn = h("button", { type: "submit" }, "Sign in");
  const form = h(
    "form",
    {
      class: "stack",
      onsubmit: async (e) => {
        e.preventDefault();
        btn.disabled = true;
        msg.set("Signing in…");
        try {
          const r = await api("/api/v1/auth/login", {
            method: "POST",
            body: { email: email.value, password: password.value },
          });
          setSession({ token: r.access_token, role: r.role, name: r.name });
          location.hash = "#/" + homeFor(r.role);
        } catch (err) {
          msg.set(err.message, "error");
          btn.disabled = false;
        }
      },
    },
    field("Email", email),
    field("Password", password),
    btn,
    msg.el
  );
  return { el: h("div", { class: "card login" }, h("h1", {}, "Campus Gate Control"), form) };
}

function tile(label) {
  const n = h("div", { class: "n" }, "–");
  return { el: h("div", { class: "tile" }, n, h("div", { class: "l" }, label)), set: (v) => (n.textContent = String(v)) };
}

function viewLive() {
  const tAllow = tile("Allowed (last 50)");
  const tDeny = tile("Denied (last 50)");
  const tRefer = tile("Referred to guard");
  const tInside = tile("On campus now");
  const status = note();
  const body = h("tbody");
  const table = h(
    "table",
    {},
    h("thead", {}, h("tr", {}, h("th", {}, "Time"), h("th", {}, "Gate"), h("th", {}, "Result"), h("th", {}, "Reason"))),
    body
  );

  const cleanup = poller(async () => {
    try {
      const [events, stats] = await Promise.all([api("/api/v1/events?limit=50"), api("/api/v1/stats")]);
      const count = (r) => events.filter((e) => e.result === r).length;
      tAllow.set(count("allow"));
      tDeny.set(count("deny"));
      tRefer.set(count("refer_to_guard"));
      tInside.set(stats.on_campus);
      body.replaceChildren(
        ...events.map((e) =>
          h("tr", {}, h("td", {}, fmtTime(e.occurred_at)), h("td", {}, e.gate), h("td", {}, badge(e.result, e.result)), h("td", {}, pretty(e.reason)))
        )
      );
      status.set(`Live · updated ${new Date().toLocaleTimeString()}`);
    } catch (e) {
      status.set(`Connection problem: ${e.message}`, "error");
      throw e;
    }
  }, 3000);

  const el = h(
    "div",
    {},
    h("h1", {}, "Live gate activity"),
    h("div", { class: "tiles" }, tAllow.el, tDeny.el, tRefer.el, tInside.el),
    h("div", { class: "card" }, status.el, h("div", { class: "scroll" }, table))
  );
  return { el, cleanup };
}

function viewGates() {
  const status = note();
  const body = h("tbody");
  const table = h(
    "table",
    {},
    h("thead", {}, h("tr", {}, h("th", {}, "Gate"), h("th", {}, "Type"), h("th", {}, "Direction"), h("th", {}, "Status"), h("th", {}, "Last seen"))),
    body
  );
  const cleanup = poller(async () => {
    try {
      const gates = await api("/api/v1/gates");
      body.replaceChildren(
        ...gates.map((g) => {
          let state = "never";
          if (g.last_seen_at) state = Date.now() - new Date(g.last_seen_at).getTime() < 90000 ? "online" : "offline";
          return h("tr", {}, h("td", {}, g.name), h("td", {}, g.kind), h("td", {}, g.direction), h("td", {}, badge(state, state)), h("td", {}, ago(g.last_seen_at)));
        })
      );
      status.set(`Updated ${new Date().toLocaleTimeString()} · a gate is “online” if it was seen in the last 90 seconds`);
    } catch (e) {
      status.set(`Connection problem: ${e.message}`, "error");
      throw e;
    }
  }, 10000);
  const el = h("div", {}, h("h1", {}, "Gate health"), h("div", { class: "card" }, status.el, h("div", { class: "scroll" }, table)));
  return { el, cleanup };
}

function localInput(d) {
  const p = (n) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}T${p(d.getHours())}:${p(d.getMinutes())}`;
}

function viewVisitors() {
  const msg = note();
  const result = h("div");
  const activeBody = h("tbody");
  const name = h("input", { required: true, maxlength: 200 });
  const idNo = h("input", { required: true, maxlength: 64 });
  const host = h("input", { required: true, maxlength: 200 });
  const purpose = h("input", { required: true, maxlength: 300 });
  const until = h("input", { type: "datetime-local", required: true, value: localInput(new Date(Date.now() + 8 * 3600 * 1000)) });
  const btn = h("button", { type: "submit" }, "Issue pass");

  async function loadActive() {
    try {
      const rows = await api("/api/v1/visitors/active");
      activeBody.replaceChildren(
        ...rows.map((v) => h("tr", {}, h("td", {}, v.full_name), h("td", {}, v.host), h("td", {}, fmtTime(v.valid_until))))
      );
    } catch (e) {
      msg.set(e.message, "error");
    }
  }

  const form = h(
    "form",
    {
      class: "stack",
      onsubmit: async (e) => {
        e.preventDefault();
        const untilDate = new Date(until.value);
        if (Number.isNaN(untilDate.getTime())) return msg.set("Choose a valid expiry date and time.", "error");
        btn.disabled = true;
        msg.set("Issuing pass…");
        try {
          const r = await api("/api/v1/visitors", {
            method: "POST",
            body: {
              full_name: name.value.trim(),
              id_number: idNo.value.trim(),
              host: host.value.trim(),
              purpose: purpose.value.trim(),
              valid_until: untilDate.toISOString(),
            },
          });
          const copy = h(
            "button",
            {
              type: "button",
              class: "secondary",
              onclick: async () => {
                try {
                  await navigator.clipboard.writeText(r.qr_token);
                  copy.textContent = "Copied";
                } catch {
                  copy.textContent = "Copy failed — select the text manually";
                }
              },
            },
            "Copy token"
          );
          result.replaceChildren(
            h(
              "div",
              { class: "card" },
              h("h2", {}, `Pass issued for ${r.full_name ?? name.value.trim()}`),
              h("p", { class: "muted" }, "Pass token (shown once). Encode it in the visitor's QR code or give it to them:"),
              h("div", { class: "token mono" }, r.qr_token),
              copy,
              h("p", { class: "muted" }, `Valid until ${new Date(r.valid_until).toLocaleString()}`)
            )
          );
          form.reset();
          until.value = localInput(new Date(Date.now() + 8 * 3600 * 1000));
          msg.set("Pass created.", "ok");
          loadActive();
        } catch (err) {
          msg.set(err.message, "error");
        } finally {
          btn.disabled = false;
        }
      },
    },
    field("Visitor full name", name),
    field("ID / Omang / passport number", idNo),
    field("Host (who they are visiting)", host),
    field("Purpose of visit", purpose),
    field("Pass valid until (max 24 hours)", until),
    btn,
    msg.el
  );

  const el = h(
    "div",
    {},
    h("h1", {}, "Visitors"),
    h("div", { class: "card" }, h("h2", {}, "Register a visitor"), form),
    result,
    h(
      "div",
      { class: "card" },
      h("h2", {}, "Currently valid passes"),
      h("div", { class: "scroll" }, h("table", {}, h("thead", {}, h("tr", {}, h("th", {}, "Visitor"), h("th", {}, "Host"), h("th", {}, "Valid until"))), activeBody))
    )
  );
  loadActive();
  return { el };
}

function viewRegistration() {
  const msg = note();
  const out = h("div");
  const input = h("input", { placeholder: "Student number", required: true, autocomplete: "off" });
  let currentNo = null;

  async function load(no) {
    if (!no) return;
    msg.set("Loading…");
    try {
      const s = await api(`/api/v1/registration/students/${encodeURIComponent(no)}`);
      currentNo = s.student_no;
      msg.set("");
      draw(s);
    } catch (e) {
      currentNo = null;
      out.replaceChildren();
      msg.set(e.message, "error");
    }
  }

  async function act(fn, okText) {
    msg.set("Working…");
    try {
      await fn();
      await load(currentNo);
      msg.set(okText, "ok");
    } catch (e) {
      msg.set(e.message, "error");
    }
  }

  function draw(s) {
    const credRows = s.credentials.map((c) =>
      h(
        "tr",
        {},
        h("td", {}, c.id),
        h("td", {}, c.type),
        h("td", {}, badge(c.revoked ? "revoked" : "active", c.revoked ? "revoked" : "active")),
        h(
          "td",
          {},
          c.revoked
            ? ""
            : h(
                "button",
                {
                  class: "danger",
                  onclick: () => {
                    if (confirm(`Revoke ${c.type} credential #${c.id}? The student will no longer be able to use it.`))
                      act(() => api(`/api/v1/registration/credentials/${c.id}`, { method: "DELETE" }), "Credential revoked.");
                  },
                },
                "Revoke"
              )
        )
      )
    );

    const type = h("select", {}, h("option", { value: "card" }, "RFID / student card"), h("option", { value: "fingerprint" }, "Fingerprint"), h("option", { value: "face" }, "Face"));
    const value = h("input", { required: true, maxlength: 256, autocomplete: "off", placeholder: "Tap the card on the reader" });
    const consent = h("input", { type: "checkbox" });
    type.addEventListener("change", () => {
      value.placeholder = type.value === "card" ? "Tap the card on the reader" : "Template reference ID from the enrolment device";
    });
    const credForm = h(
      "form",
      {
        class: "stack",
        onsubmit: (e) => {
          e.preventDefault();
          if (!consent.checked) return msg.set("Consent must be confirmed first.", "error");
          act(
            () => api(`/api/v1/registration/students/${encodeURIComponent(s.student_no)}/credentials`, { method: "POST", body: { type: type.value, value: value.value.trim(), consent_given: true } }),
            "Credential registered."
          );
        },
      },
      field("Credential type", type),
      field("Card UID or template reference", value),
      h("label", { class: "check" }, consent, "The student has given consent to this credential being registered"),
      h("button", { type: "submit" }, "Register credential")
    );

    const plate = h("input", { required: true, maxlength: 16, placeholder: "e.g. B123 ABC" });
    const vehForm = h(
      "form",
      {
        class: "row",
        onsubmit: (e) => {
          e.preventDefault();
          act(() => api(`/api/v1/registration/students/${encodeURIComponent(s.student_no)}/vehicles`, { method: "POST", body: { plate: plate.value } }), "Vehicle registered.");
        },
      },
      plate,
      h("button", { type: "submit" }, "Add vehicle")
    );

    out.replaceChildren(
      h(
        "div",
        { class: "card" },
        h("h2", {}, s.full_name),
        h("p", {}, `Student no. ${s.student_no} · `, badge(s.status, s.status), s.inside ? " · currently on campus" : " · currently off campus")
      ),
      h(
        "div",
        { class: "card" },
        h("h2", {}, "Credentials"),
        s.credentials.length
          ? h("div", { class: "scroll" }, h("table", {}, h("thead", {}, h("tr", {}, h("th", {}, "ID"), h("th", {}, "Type"), h("th", {}, "Status"), h("th", {}, ""))), h("tbody", {}, credRows)))
          : h("p", { class: "muted" }, "No credentials yet."),
        h("h2", {}, "Add credential"),
        credForm
      ),
      h(
        "div",
        { class: "card" },
        h("h2", {}, "Vehicles"),
        s.vehicles.length ? h("ul", {}, s.vehicles.map((v) => h("li", { class: "mono" }, `${v.plate} (${v.status})`))) : h("p", { class: "muted" }, "No vehicles yet."),
        vehForm
      )
    );
  }

  const search = h(
    "form",
    {
      class: "row",
      onsubmit: (e) => {
        e.preventDefault();
        load(input.value.trim());
      },
    },
    input,
    h("button", { type: "submit" }, "Look up")
  );
  return { el: h("div", {}, h("h1", {}, "Student registration"), h("div", { class: "card" }, search, msg.el), out) };
}

/* ---------- routing + shell ---------- */

const ROUTES = {
  live: { label: "Live", roles: ["guard", "admin"], view: viewLive },
  gates: { label: "Gates", roles: ["guard", "admin"], view: viewGates },
  visitors: { label: "Visitors", roles: ["guard", "admin"], view: viewVisitors },
  registration: { label: "Registration", roles: ["registrar", "admin"], view: viewRegistration },
};

function homeFor(role) {
  return role === "registrar" ? "registration" : "live";
}

function shell(session, current, content) {
  const links = Object.entries(ROUTES)
    .filter(([, r]) => r.roles.includes(session.role))
    .map(([key, r]) => h("a", { href: `#/${key}`, class: key === current ? "active" : "" }, r.label));
  return h(
    "div",
    {},
    h(
      "header",
      {},
      h("span", { class: "brand" }, "Campus Gate Control"),
      h("nav", {}, links),
      h(
        "span",
        { class: "who" },
        `${session.name} (${session.role})`,
        h(
          "button",
          {
            class: "secondary",
            onclick: () => {
              clearSession();
              location.hash = "#/login";
            },
          },
          "Sign out"
        )
      )
    ),
    h("main", {}, content)
  );
}

let cleanup = null;

function render() {
  if (cleanup) {
    cleanup();
    cleanup = null;
  }
  const root = document.getElementById("app");
  const session = getSession();
  const name = location.hash.replace(/^#\//, "");
  root.replaceChildren();

  if (!session) {
    if (name !== "login") {
      location.hash = "#/login";
      return;
    }
    root.append(viewLogin().el);
    return;
  }
  const route = ROUTES[name];
  if (!route || !route.roles.includes(session.role)) {
    location.hash = "#/" + homeFor(session.role);
    return;
  }
  const v = route.view();
  cleanup = v.cleanup || null;
  root.append(shell(session, name, v.el));
}

window.addEventListener("hashchange", render);
render();
