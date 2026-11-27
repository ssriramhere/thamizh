# Sources of the Tirukkuṟaḷ text

`pipeline/build_kural.py` reads the Tamil text of the 1,330 couplets from five
open digital editions. Clone them into one folder and pass its path:

| Folder | Source | Licence |
|---|---|---|
| `tk/` | https://github.com/tk120404/thirukkural | Apache-2.0 |
| `pypi/x/` | the `thirukkural` package on PyPI (unzipped wheel) | MIT |
| `nramc_thirukkural-api/` | https://github.com/nramc/thirukkural-api | MIT |
| `prodev717_openthirukkural/` | https://github.com/prodev717/openthirukkural | MIT |
| `vijayanandrp_Thirukkural-Tamil-Dataset/` | https://github.com/vijayanandrp/Thirukkural-Tamil-Dataset | see repo |

Only the Tamil couplets and the chapter names are taken. No commentary or
translation from these sources is used.

The five editions share most of their typos, so they are not fully
independent. Seven couplets carry a typo in every source; `data/corrections.json`
holds the correction for each, applied only when the corrected couplet scans
as a kuṟaḷ veṇpā. All seven were checked by the editor on 2026-11-27.

# Sources of the Caṅkam texts

`pipeline/import_pm.py` reads Project Madurai's Unicode HTML etexts:

| File | Text | Prepared by |
|---|---|---|
| `pm0110.html` | Kuṟuntokai, 401 poems | Dr. K. Kalyanasundaram (etext, web); Ms. Sarala Sandirasegarane (proofreading) |
| `pm0057.html` | Puṟanāṉūṟu, 397 poems (200 is missing in the etext; 267 and 268 are lost) | Staff and students of K.A.P. Viswanatham Higher Secondary School, Tiruchirappalli; Dr. K. Kalyanasundaram (web) |

Download them from https://projectmadurai.org/ into one folder and pass its
path. Project Madurai asks that the header page be kept intact when the file
is distributed; `projectmadurai/` holds each header unchanged.

Kept: the poem number, the lines, tiṇai, the speaker (Kuṟuntokai) or tuṟai
(Puṟanāṉūṟu), the poet, and the person addressed. Dropped: the modern titles
of the Puṟanāṉūṟu poems, the editor's notes (some cite commentators), and the
editorial punctuation, and stray characters from the etext's old encoding
(a middle dot · for ஃ; backticks, underscores and a few others).
`data/corrections_pm.json` fixes the three places where a note runs into a
poem.
