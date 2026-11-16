# Babaholmi

Statikus weboldal, GitHub Pages-en futtatható.

- `index.html` – az oldal
- `assets/` – React, a dc-runtime és a betűtípusok (minden helyben, nincs CDN-függés)
- `Babaholmi – Babaholmi.html` – az eredeti, egyfájlos export (forrás)

## Közzététel
Settings → Pages → Source: *Deploy from a branch* → Branch: `main` / `/ (root)` → Save.

## Kínálat frissítése
```bash
python3 tools/update_inventory.py --dry   # csak megmutatja a változásokat
python3 tools/update_inventory.py         # frissít: eladottak ki, újak be fotóval, darabszám, og-image
```
Utána `git add -A && git commit -m "Kínálat frissítése" && git push`.
