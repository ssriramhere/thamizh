# Thamizh.ai

AI for Tamil. Read classical Tamil the way it was composed: Tirukkuṟaḷ word by
word and letter by letter, with every couplet scanned by the rules of yāppu.
Built for every level, from no Tamil at all to scholar.

## Layout

| Path | What it is |
|---|---|
| `engine/tamil.py` | Tamil letters: split, classify (short, long, bare consonant, āytam), transliterate (ISO 15919) |
| `engine/yappu.py` | The meter engine: joining rules, nēr/nirai, feet, linkages, mōṉai/etukai, kuṟaḷ veṇpā; and `rejoin`, which checks a proposed word split |
| `pipeline/build_kural.py` | Builds the couplet text from five open editions (majority reading; the meter breaks ties) |
| `pipeline/build_web.py` | Writes the site data: `web/data/kural/index.json` and one file per chapter |
| `pipeline/gemini_kural.py` | Generates the AI layers (word splits and glosses, translations, today's Tamil, explanation) with Gemini on Vertex AI, checking every answer |
| `data/build/` | The built text, and `kural_review.json` (couplets no reading scans) |
| `data/corrections.json` | Proposed fixes for typos every source shares |
| `data/ai/kural/` | AI output, one file per couplet |
| `web/` | The static site served at thamizh.ai |

## The meter engine

The rules are deterministic; no AI model decides the meter. Modern printings
separate the words of a couplet, but meter runs on the joined text, so the
engine first re-applies the joining rules (a final shortened u drops before a
vowel, a bare consonant takes the next vowel, consonants double after a lone
short letter, glides), then finds the foot boundaries that make a valid kuṟaḷ
veṇpā, preferring boundaries at the printed word breaks. Where needed it also
tries the known licences: the silent i (kuṟṟiyalikaram), the shortened ai
(aikārakkuṟukkam), and the āytam counted as a short letter.

All 1,330 couplets of the built text scan as kuṟaḷ veṇpā.

## Build

```bash
python pipeline/build_kural.py /path/to/sources   # data/build/kural_text.json
python pipeline/gemini_kural.py all --skip-existing   # data/ai/kural/*.json (needs Vertex AI)
python pipeline/build_web.py                       # web/data/kural/
```

The site is static (`web/`), deployed on Vercel.
