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
holds a proposed correction for each, applied only when the corrected couplet
scans as a kuṟaḷ veṇpā. These still need checking against a printed edition.
