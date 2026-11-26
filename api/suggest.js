// POST /api/suggest
// Turns a reader's suggestion into a GitHub pull request, as on Samskritam.ai.
//   {kind:"translation", text, n, t, current, note, name, email}
//     -> reviewed/<text>/<n>.json            {t, by}
//   {kind:"word", text, n, wi, surface, parts:[{text, lemma, gloss}], gloss, why, joins, current, name, email}
//     -> reviewed/words/<text>/<n>-<wi>.json  {surface, parts, gloss, why, by}
// Merging the pull request approves it; editing the file in the pull request
// edits it; closing it rejects it. On deploy, scripts/build_reviewed.mjs folds
// reviewed/ into web/data/reviewed.json.
//
// Env: GITHUB_TOKEN (fine-grained, this repository only: Contents and Pull
// requests, read and write), GITHUB_REPO (default ssriramhere/thamizh), and
// the Upstash variables for rate limits and the private contact email. The
// repository is public, so the email is never written to GitHub.

const crypto = require("crypto");
const URL_ = process.env.UPSTASH_REDIS_REST_URL || process.env.KV_REST_API_URL;
const TOKEN = process.env.UPSTASH_REDIS_REST_TOKEN || process.env.KV_REST_API_TOKEN;
const GH = process.env.GITHUB_TOKEN;
const REPO = process.env.GITHUB_REPO || "ssriramhere/thamizh";
const PER_IP_PER_HOUR = 10;
const PER_DAY = 50;
const EMAIL = /^[^\s@<>()\[\]\\,;:"]+@[^\s@<>()\[\]\\,;:"]+\.[^\s@<>()\[\]\\,;:"]{2,}$/;
const TEXTS = {
  kural: { title: "Tirukkuṟaḷ", max: 1330, unit: "Kuṟaḷ", url: (n) => `https://thamizh.ai/kural?n=${n}` },
};
const TAMIL = /^[஀-௿]+$/;

async function redis(commands) {
  const r = await fetch(`${URL_}/pipeline`, {
    method: "POST",
    headers: { Authorization: `Bearer ${TOKEN}`, "Content-Type": "application/json" },
    body: JSON.stringify(commands),
  });
  if (!r.ok) throw new Error(`redis ${r.status}`);
  const out = await r.json();
  const bad = out.find((x) => x.error);
  if (bad) throw new Error(bad.error);
  return out.map((x) => x.result);
}

async function gh(method, path, body) {
  const r = await fetch(`https://api.github.com/repos/${REPO}${path}`, {
    method,
    headers: { Authorization: `Bearer ${GH}`, Accept: "application/vnd.github+json",
      "X-GitHub-Api-Version": "2022-11-28", "User-Agent": "thamizh-suggest" },
    body: body ? JSON.stringify(body) : undefined,
  });
  if (r.status === 404 && method === "GET") return null;
  if (!r.ok) throw new Error(`github ${method} ${path} ${r.status} ${(await r.text()).slice(0, 200)}`);
  return r.json();
}

function readBody(req) {
  if (req.body && typeof req.body === "object") return req.body;
  try { return JSON.parse(req.body || "{}"); } catch { return {}; }
}

const clean = (s, max) => String(s || "").normalize("NFC").replace(/\s+/g, " ").trim().slice(0, max);
// Shown inside fenced blocks in the pull request, so links and @mentions stay inert.
const fence = (s) => "```text\n" + String(s).replace(/`{3,}/g, "``") + "\n```";

async function limited(req) {
  const ip = String(req.headers["x-forwarded-for"] || "").split(",")[0].trim() || "unknown";
  const day = new Date().toISOString().slice(0, 10);
  const [hits, , today] = await redis([
    ["INCR", `th:suggest:rl:${ip}`], ["EXPIRE", `th:suggest:rl:${ip}`, 3600, "NX"],
    ["INCR", `th:suggest:day:${day}`], ["EXPIRE", `th:suggest:day:${day}`, 172800, "NX"]]);
  if (hits > PER_IP_PER_HOUR) return "That's the hourly limit for suggestions from your network. Try again later.";
  if (today > PER_DAY) return "We've had many suggestions today. Please try again tomorrow.";
  return null;
}

async function openPR({ branch, path, file, message, title, body }) {
  const main = await gh("GET", "/git/ref/heads/main");
  await gh("POST", "/git/refs", { ref: `refs/heads/${branch}`, sha: main.object.sha });
  const existing = await gh("GET", `/contents/${path}?ref=main`);
  await gh("PUT", `/contents/${path}`, {
    message, branch,
    content: Buffer.from(JSON.stringify(file, null, 2) + "\n").toString("base64"),
    ...(existing ? { sha: existing.sha } : {}),
  });
  return gh("POST", "/pulls", { title, head: branch, base: "main", body });
}

const credit = (name, email) => ["", "**Credit**", fence(name || "a reader (no name given)"),
  email ? "\nThe reader left a contact email; it is stored privately, not here." : ""];

async function translation(req, res, b, T, n) {
  const t = clean(b.t, 1500), current = clean(b.current, 1500), note = clean(b.note, 600);
  const name = clean(b.name, 80), email = clean(b.email, 254).toLowerCase();
  if (t.length < 15) return res.status(400).json({ ok: false, error: "Write the full translation you suggest." });
  if (t === current) return res.status(400).json({ ok: false, error: "That's the same as the current translation. Edit it first." });
  if (email && !EMAIL.test(email)) return res.status(400).json({ ok: false, error: "Check the email address, or leave it empty." });
  const stop = await limited(req);
  if (stop) return res.status(429).json({ ok: false, error: stop });
  const sid = `${Date.now().toString(36)}${crypto.randomBytes(2).toString("hex")}`;
  const ref = `${T.title} ${n}`;
  const pr = await openPR({
    branch: `suggest-${b.text}-${n}-${sid}`, path: `reviewed/${b.text}/${n}.json`,
    file: { t, by: name || "a reader" },
    message: `Suggested translation: ${ref}`, title: `Translation suggestion: ${ref}`,
    body: [`A reader suggested a translation for **${ref}**: ${T.url(n)}`,
      "", "**Suggested**", fence(t), "", "**Current**", fence(current || "(none)"),
      ...(note ? ["", "**Reader's note**", fence(note)] : []), ...credit(name, email),
      "", "---", "**Approve:** merge. **Edit:** change `t` (the translation) or `by` (the credit) in this pull request's file, then merge. **Reject:** close."].join("\n"),
  });
  if (email) await redis([["HSET", `th:suggest:pr:${pr.number}`, "email", email, "name", name, "ref", ref]]);
  return res.status(200).json({ ok: true });
}

async function word(req, res, b, T, n) {
  const wi = Number(b.wi);
  const surface = clean(b.surface, 60);
  if (!Number.isInteger(wi) || wi < 0 || wi > 40 || !TAMIL.test(surface)) {
    return res.status(400).json({ ok: false, error: "That word wasn't recognised. Reload the page and try again." });
  }
  const parts = (Array.isArray(b.parts) ? b.parts : []).slice(0, 8).map((p) => ({
    text: clean(p && p.text, 40).replace(/\s/g, ""), lemma: clean(p && p.lemma, 40).replace(/\s/g, ""), gloss: clean(p && p.gloss, 80),
  })).filter((p) => p.text);
  if (!parts.length || parts.some((p) => !TAMIL.test(p.text) || (p.lemma && !TAMIL.test(p.lemma)))) {
    return res.status(400).json({ ok: false, error: "Write each part and its root word in Tamil letters." });
  }
  const gloss = clean(b.gloss, 120), why = clean(b.why, 600);
  const name = clean(b.name, 80), email = clean(b.email, 254).toLowerCase();
  if (why.length < 10) return res.status(400).json({ ok: false, error: "Say briefly what is wrong." });
  if (email && !EMAIL.test(email)) return res.status(400).json({ ok: false, error: "Check the email address, or leave it empty." });
  const cur = b.current && typeof b.current === "object" ? b.current : {};
  const curParts = (Array.isArray(cur.parts) ? cur.parts : []).slice(0, 8)
    .map((p) => `${clean(p && p.text, 40)} (${clean(p && p.lemma, 40)}): ${clean(p && p.gloss, 80)}`);
  const stop = await limited(req);
  if (stop) return res.status(429).json({ ok: false, error: stop });
  const sid = `${Date.now().toString(36)}${crypto.randomBytes(2).toString("hex")}`;
  const ref = `${T.title} ${n}`;
  const show = (ps, g) => ps.join("\n") + `\nWhole word: ${g || "(none)"}`;
  const pr = await openPR({
    branch: `suggest-word-${b.text}-${n}-${wi}-${sid}`, path: `reviewed/words/${b.text}/${n}-${wi}.json`,
    file: { surface, parts, gloss, why, by: name || "a reader" },
    message: `Suggested correction: ${surface} in ${ref}`, title: `Word correction: ${surface} in ${ref}`,
    body: [`A reader suggested a correction to **${surface}** (word ${wi + 1}) in **${ref}**: ${T.url(n)}`,
      "", b.joins ? "✓ The parts join back to the printed word by the joining rules."
        : "⚠ The parts do **not** join back to the printed word by the site's joining rules. Check the split, or the rules may be missing a case.",
      "", "**Suggested**", fence(show(parts.map((p) => `${p.text} (${p.lemma || "?"}): ${p.gloss}`), gloss)),
      "", "**Current**", fence(show(curParts, clean(cur.gloss, 120))), "", "**Why**", fence(why), ...credit(name, email),
      "", "---", "**Approve:** merge. **Edit:** change `parts`, `gloss` or `by` in this pull request's file, then merge. Don't change `surface`: it identifies the word. **Reject:** close."].join("\n"),
  });
  if (email) await redis([["HSET", `th:suggest:pr:${pr.number}`, "email", email, "name", name, "ref", `${ref} ${surface}`]]);
  return res.status(200).json({ ok: true });
}

module.exports = async (req, res) => {
  res.setHeader("Cache-Control", "no-store");
  if (req.method !== "POST") {
    res.setHeader("Allow", "POST");
    return res.status(405).json({ ok: false, error: "Use POST." });
  }
  if (!URL_ || !TOKEN || !GH) return res.status(503).json({ ok: false, error: "Suggestions are not connected yet." });
  const b = readBody(req);
  if (b.website) return res.status(200).json({ ok: true });  // honeypot
  const T = TEXTS[b.text], n = Number(b.n);
  if (!T || !Number.isInteger(n) || n < 1 || n > T.max) {
    return res.status(400).json({ ok: false, error: "That verse wasn't recognised. Reload the page and try again." });
  }
  try {
    if (b.kind === "translation") return await translation(req, res, b, T, n);
    if (b.kind === "word") return await word(req, res, b, T, n);
    return res.status(400).json({ ok: false, error: "Unknown kind of suggestion." });
  } catch (e) {
    console.error("suggest", e);
    return res.status(502).json({ ok: false, error: "We couldn't save your suggestion just now. Please try again." });
  }
};
