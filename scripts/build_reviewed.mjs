// Folds reviewed/ (merged reader suggestions) into web/data/reviewed.json:
// { kural: { t: { "<n>": {t, by} }, w: { "<n>-<wi>": {surface, parts, gloss, by} } } }
import { readdirSync, readFileSync, writeFileSync, existsSync } from "node:fs";
import { join } from "node:path";

const root = new URL("..", import.meta.url).pathname;
const out = {};
const list = (d) => (existsSync(d) ? readdirSync(d).filter((f) => f.endsWith(".json")) : []);
const dir = join(root, "reviewed");
for (const text of existsSync(dir) ? readdirSync(dir, { withFileTypes: true }) : []) {
  if (!text.isDirectory() || text.name === "words") continue;
  for (const f of list(join(dir, text.name))) {
    const v = JSON.parse(readFileSync(join(dir, text.name, f), "utf8"));
    ((out[text.name] ||= { t: {}, w: {} }).t)[f.replace(".json", "")] = { t: v.t, by: v.by };
  }
}
const wdir = join(dir, "words");
for (const text of existsSync(wdir) ? readdirSync(wdir, { withFileTypes: true }) : []) {
  if (!text.isDirectory()) continue;
  for (const f of list(join(wdir, text.name))) {
    const v = JSON.parse(readFileSync(join(wdir, text.name, f), "utf8"));
    ((out[text.name] ||= { t: {}, w: {} }).w)[f.replace(".json", "")] = { surface: v.surface, parts: v.parts, gloss: v.gloss, by: v.by };
  }
}
writeFileSync(join(root, "web/data/reviewed.json"), JSON.stringify(out) + "\n");
console.log("reviewed.json:", Object.entries(out).map(([k, v]) => `${k} ${Object.keys(v.t).length} translations, ${Object.keys(v.w).length} words`).join("; ") || "empty");
