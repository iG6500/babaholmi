#!/usr/bin/env python3
"""Babaholmi kínálat frissítése a Vinted profilból.

Futtatás a repó gyökeréből:
    python3 tools/update_inventory.py          # frissít
    python3 tools/update_inventory.py --dry    # csak megmutatja, mi változna

Mit csinál:
  * lekéri a profil aktuális termékeit (nyilvános Vinted API, anonim munkamenet),
  * kiveszi az oldalról az eladott / levett termékeket (és a képüket),
  * felveszi az új termékeket, és letölti a fő fotójukat (assets/img/<id>.jpg),
  * frissíti az árakat, a fotólistát és a meta leírásban a darabszámot,
  * újrarajzolja a megosztási képet (og-image.jpg) az új darabszámmal.

A HIDE listában lévő termékek (pl. nem babás holmik) rejtve maradnak; az új,
gyanúsan nem babás termékeket a végén kiírja, hogy el lehessen dönteni.
"""
import json
import os
import re
import subprocess
import sys
import tempfile
import time
import urllib.request
from http.cookiejar import CookieJar

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INDEX = os.path.join(ROOT, 'index.html')
IMG_DIR = os.path.join(ROOT, 'assets', 'img')
MEMBER_ID = '180210647'
UA = ('Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 '
      '(KHTML, like Gecko) Chrome/130.0 Safari/537.36')
HEADERS = {'User-Agent': UA, 'Accept-Language': 'hu-HU'}
CHROME = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
OG_PHOTOS = ['10704519528', '7414054845', '10678968485', '7945715899']
NOT_BABY = re.compile(r'női|férfi|könyv|csizma|alkalmi', re.I)
DRY = '--dry' in sys.argv


def opener():
    jar = CookieJar()
    op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
    op.addheaders = list(HEADERS.items())
    op.open('https://www.vinted.hu/', timeout=30).read()  # anonim session süti
    return op


def fetch_wardrobe(op):
    items, page = [], 1
    while True:
        url = (f'https://www.vinted.hu/api/v2/wardrobe/{MEMBER_ID}/items'
               f'?page={page}&per_page=96&order=relevance')
        req = urllib.request.Request(url, headers={'Accept': 'application/json'})
        data = json.loads(op.open(req, timeout=30).read())
        items += data['items']
        pg = data.get('pagination') or {}
        if page >= pg.get('total_pages', 1):
            return items
        page += 1
        time.sleep(1)


def norm_cond(status):
    return 'Új' if status.startswith('Új') else status


def clean(text):
    return (text or '').replace(' ', ' ').replace('|', '/').replace('"', "'").strip()


def parse_raw(html):
    start = html.index('var RAW = (\n') + len('var RAW = (\n')
    end = html.index("\n).split('\\n');", start)
    lines = []
    for ln in html[start:end].split('\n'):
        m = re.match(r'^"(.*?)(?:\\n" \+|")$', ln)
        if m:
            lines.append(m.group(1).split('|'))
    return start, end, lines


def write_raw(html, start, end, rows):
    body = []
    for i, r in enumerate(rows):
        tail = '"' if i == len(rows) - 1 else '\\n" +'
        body.append('"' + '|'.join(r) + tail)
    return html[:start] + '\n'.join(body) + html[end:]


def download_photo(op, item_id):
    html = op.open('https://www.vinted.hu/items/' + item_id, timeout=30).read().decode('utf-8', 'ignore')
    m = re.search(r'<meta property="og:image" content="([^"]+)"', html)
    if not m:
        raise RuntimeError('nincs og:image')
    raw = op.open(m.group(1).replace('&amp;', '&'), timeout=30).read()
    with tempfile.NamedTemporaryFile(suffix='.img', delete=False) as f:
        f.write(raw)
    try:
        subprocess.run(['sips', '-s', 'format', 'jpeg', '-s', 'formatOptions', '78', '-Z', '640',
                        f.name, '--out', os.path.join(IMG_DIR, item_id + '.jpg')],
                       check=True, capture_output=True)
    finally:
        os.unlink(f.name)


def render_og(count, photo_ids):
    tpl = open(os.path.join(ROOT, 'tools', 'og-template.html'), encoding='utf-8').read()
    picks = [p for p in OG_PHOTOS if p in photo_ids]
    picks += [p for p in sorted(photo_ids, reverse=True) if p not in picks]
    for key, pid in zip('ABCD', picks):
        tpl = tpl.replace('{{%s}}' % key, pid)
    tpl = tpl.replace('{{COUNT}}', str(count))
    tmp_html = os.path.join(ROOT, 'tools', '_og-render.html')
    open(tmp_html, 'w', encoding='utf-8').write(tpl)
    png = os.path.join(tempfile.gettempdir(), 'babaholmi-og.png')
    prof = tempfile.mkdtemp(prefix='babaholmi-chrome-')
    try:
        subprocess.run([CHROME, '--headless=new', '--disable-gpu', '--hide-scrollbars',
                        '--allow-file-access-from-files', '--force-device-scale-factor=1',
                        '--window-size=1200,630', '--virtual-time-budget=3000',
                        '--user-data-dir=' + prof, '--screenshot=' + png, 'file://' + tmp_html],
                       check=True, capture_output=True, timeout=60)
        subprocess.run(['sips', '-s', 'format', 'jpeg', '-s', 'formatOptions', '86', png,
                        '--out', os.path.join(ROOT, 'og-image.jpg')], check=True, capture_output=True)
    finally:
        os.unlink(tmp_html)


def main():
    html = open(INDEX, encoding='utf-8').read()
    hide = set(re.findall(r"'(\d+)'", html[html.index('var HIDE'):html.index('function categorize')]))
    start, end, rows = parse_raw(html)
    known = {r[0]: r for r in rows}

    op = opener()
    live = [i for i in fetch_wardrobe(op)
            if not (i.get('is_closed') or i.get('is_reserved') or i.get('is_hidden') or i.get('is_draft'))]
    live_by_id = {str(i['id']): i for i in live}

    removed = [r for r in rows if r[0] not in live_by_id]
    added, repriced, new_rows = [], [], []
    for r in rows:
        it = live_by_id.get(r[0])
        if not it:
            continue
        price = str(int(float(it['price']['amount'] if isinstance(it['price'], dict) else it['price'])))
        if price != r[5]:
            repriced.append((r[1], r[5], price))
            r = r[:5] + [price]
        new_rows.append(r)
    fresh = []
    for iid, it in live_by_id.items():
        if iid in known:
            continue
        price = str(int(float(it['price']['amount'] if isinstance(it['price'], dict) else it['price'])))
        row = [iid, clean(it['title']), clean(it.get('brand')), norm_cond(it.get('status') or ''),
               clean(it.get('size')), price]
        fresh.append(row)
        added.append(row)
    fresh.sort(key=lambda r: int(r[0]), reverse=True)
    new_rows = fresh + new_rows

    visible = [r for r in new_rows if r[0] not in hide]
    print(f'Vinteden most: {len(live)} aktív termék; az oldalon látható lesz: {len(visible)}')
    print(f'Kikerül ({len(removed)}):', *[f'\n  - {r[1]} ({r[5]} Ft)' for r in removed])
    print(f'Új ({len(added)}):', *[f'\n  + {r[1]} ({r[5]} Ft)' for r in added])
    print(f'Árváltozás ({len(repriced)}):', *[f'\n  ~ {t}: {a} → {b} Ft' for t, a, b in repriced])
    suspicious = [r for r in added if NOT_BABY.search(r[1])]
    if suspicious:
        print('Figyelem, ezek talán nem babás holmik (HIDE listába tehetők):',
              *[f'\n  ? {r[0]} {r[1]}' for r in suspicious])
    if DRY:
        return

    os.makedirs(IMG_DIR, exist_ok=True)
    for r in removed:
        p = os.path.join(IMG_DIR, r[0] + '.jpg')
        if os.path.exists(p):
            os.unlink(p)
    failed = []
    for r in visible:
        if os.path.exists(os.path.join(IMG_DIR, r[0] + '.jpg')):
            continue
        for attempt in range(3):
            try:
                download_photo(op, r[0])
                break
            except Exception as e:  # 429 esetén várunk és újrapróbáljuk
                time.sleep(30 * (attempt + 1))
                if attempt == 2:
                    failed.append((r[1], str(e)[:60]))
        time.sleep(5)
    if failed:
        print('Nem sikerült fotót letölteni (ikon jelenik meg helyette):', failed)

    html = write_raw(html, start, end, new_rows)
    photos = sorted(f[:-4] for f in os.listdir(IMG_DIR) if f.endswith('.jpg'))
    html = re.sub(r'var PHOTOS = \{.*?\}; /\*PHOTOS\*/',
                  'var PHOTOS = ' + json.dumps({p: 1 for p in photos}, separators=(',', ':')) + '; /*PHOTOS*/',
                  html, flags=re.S)
    html = re.sub(r'content="\d+ gondosan válogatott', f'content="{len(visible)} gondosan válogatott', html)
    open(INDEX, 'w', encoding='utf-8').write(html)

    render_og(len(visible), set(photos) - hide)
    print('Kész: index.html, assets/img és og-image.jpg frissítve.')


if __name__ == '__main__':
    main()
