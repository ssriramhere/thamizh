// POST /api/share   {voice, text, n, how}   counts a reel shared, downloaded or copied
// GET  /api/share   totals by voice and by how, for deciding which voice to keep
// Counts live in Upstash under th:share:*; nothing about the reader is kept
// beyond a per-IP hourly cap, which expires.

const URL_ = process.env.UPSTASH_REDIS_REST_URL || process.env.KV_REST_API_URL;
const TOKEN = process.env.UPSTASH_REDIS_REST_TOKEN || process.env.KV_REST_API_TOKEN;
const VOICES = ["male", "female"];
const HOWS = ["share", "link", "copy", "download"];
const PER_IP_PER_HOUR = 30;

async function redis(commands) {
  const r = await fetch(`${URL_}/pipeline`, {
    method: "POST",
    headers: { Authorization: `Bearer ${TOKEN}`, "Content-Type": "application/json" },
    body: JSON.stringify(commands),
  });
  if (!r.ok) throw new Error(`redis ${r.status}`);
  return (await r.json()).map((x) => x.result);
}

module.exports = async (req, res) => {
  try {
    if (req.method === "GET") {
      const keys = VOICES.flatMap((v) => HOWS.map((h) => `th:share:${v}:${h}`));
      const vals = await redis(keys.map((k) => ["GET", k]));
      const out = {};
      VOICES.forEach((v, i) => {
        out[v] = {};
        HOWS.forEach((h, j) => { out[v][h] = Number(vals[i * HOWS.length + j] || 0); });
      });
      res.setHeader("Cache-Control", "no-store");
      return res.status(200).json(out);
    }
    if (req.method !== "POST") return res.status(405).end();
    let b = req.body;
    if (typeof b === "string") { try { b = JSON.parse(b); } catch (e) { b = {}; } }
    b = b || {};
    const voice = VOICES.includes(b.voice) ? b.voice : null;
    const how = HOWS.includes(b.how) ? b.how : null;
    if (!voice || !how) return res.status(400).end();
    const ip = (req.headers["x-forwarded-for"] || "").split(",")[0].trim() || "unknown";
    const day = new Date().toISOString().slice(0, 10);
    const [hits] = await redis([["INCR", `th:share:ip:${ip}`], ["EXPIRE", `th:share:ip:${ip}`, 3600]]);
    if (hits > PER_IP_PER_HOUR) return res.status(204).end();
    const text = /^[a-z]+$/.test(b.text || "") ? b.text : "other";
    await redis([
      ["INCR", `th:share:${voice}:${how}`],
      ["INCR", `th:share:day:${day}:${voice}:${how}`],
      ["INCR", `th:share:verse:${text}-${Number(b.n) || 0}:${voice}`],
    ]);
    return res.status(204).end();
  } catch (e) {
    return res.status(204).end();
  }
};
