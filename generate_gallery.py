#!/usr/bin/env python3
"""
Generate missing phocagallery HTML and RSS files for the Oficina dos Sonhos archive.
Run from the project root: python generate_gallery.py
"""

import os
import re

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
SQL_PATH = os.path.join(PROJECT_ROOT, 'db', 'oficinadossonhos.sql')
RIP_DIR = os.path.join(PROJECT_ROOT, 'rip')
IMAGES_DIR = os.path.join(RIP_DIR, 'images', 'phocagallery')
TEMPLATE_FILE = os.path.join(
    RIP_DIR,
    'index.php@option=com_phocagallery&view=category&id=33%3Apatati-patata-na-oficina&Itemid=20.html',
)

# Canonical Itemid for each root gallery category (from main nav)
ITEMID_MAP = {3: 92, 18: 99, 35: 96, 42: 95, 54: 101}


# ---------------------------------------------------------------------------
# SQL parsing
# ---------------------------------------------------------------------------

def parse_sql_values(block):
    """Parse a SQL VALUES string into a list of field lists (strings)."""
    rows = []
    i = 0
    n = len(block)
    while i < n:
        while i < n and block[i] != '(':
            i += 1
        if i >= n:
            break
        i += 1  # skip '('
        fields = []
        buf = []
        in_str = False
        while i < n:
            c = block[i]
            if in_str:
                if c == '\\':
                    buf.append(c)
                    if i + 1 < n:
                        buf.append(block[i + 1])
                    i += 2
                    continue
                elif c == "'":
                    if i + 1 < n and block[i + 1] == "'":
                        buf.append("'")
                        i += 2
                        continue
                    in_str = False
                else:
                    buf.append(c)
            else:
                if c == "'":
                    in_str = True
                elif block[i:i + 4] == 'NULL':
                    buf = []
                    i += 4
                    continue
                elif c == ',':
                    fields.append(''.join(buf).strip())
                    buf = []
                elif c == ')':
                    fields.append(''.join(buf).strip())
                    rows.append(fields)
                    break
                else:
                    buf.append(c)
            i += 1
        i += 1  # past ')'
    return rows


def _find_values_block(content, marker, start=0):
    """Return the content starting just after VALUES for the INSERT at marker."""
    pos = content.find(marker, start)
    if pos < 0:
        return None, -1
    values_pos = content.find('VALUES', pos)
    if values_pos < 0:
        return None, -1
    return content[values_pos + len('VALUES'):], values_pos


def parse_sql(sql_path):
    with open(sql_path, encoding='utf-8') as f:
        content = f.read()

    # ---- categories ----
    # parse_sql_values is a state-machine that handles ';' inside strings, so
    # we just pass the rest of the file from after the VALUES keyword and let it
    # stop naturally when there are no more '(' rows.
    categories = {}
    block, _ = _find_values_block(content, 'INSERT INTO `jos_phocagallery_categories`')
    if block is not None:
        for row in parse_sql_values(block):
            if len(row) >= 18:
                try:
                    cid = int(row[0])
                    categories[cid] = {
                        'id': cid,
                        'parent_id': int(row[1]),
                        'title': row[2],
                        'alias': row[4],
                        'hits': int(row[17]) if row[17].strip() else 0,
                    }
                except (ValueError, IndexError):
                    pass

    # ---- images ----
    # Three INSERT blocks exist for jos_phocagallery. Starting from the first
    # VALUES keyword and feeding the rest of the file to parse_sql_values()
    # covers all three blocks in one pass — the state machine skips the INSERT
    # headers between blocks and gracefully rejects non-image rows.
    images_by_catid = {}
    block, _ = _find_values_block(content, 'INSERT INTO `jos_phocagallery` ')
    if block is not None:
        for row in parse_sql_values(block):
            if len(row) >= 13:
                try:
                    cid = int(row[1])
                    img = {
                        'id': int(row[0]),
                        'catid': cid,
                        'title': row[3],
                        'alias': row[4],
                        'filename': row[5].lstrip('/'),
                        'hits': int(row[8]) if row[8].strip() else 0,
                        'ordering': int(row[12]) if row[12].strip() else 0,
                    }
                    images_by_catid.setdefault(cid, []).append(img)
                except (ValueError, IndexError):
                    pass

    for cid in images_by_catid:
        images_by_catid[cid].sort(key=lambda x: x['ordering'])

    return categories, images_by_catid


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def get_itemid(catid, categories):
    """Walk the parent chain to find the canonical Itemid."""
    if catid in ITEMID_MAP:
        return ITEMID_MAP[catid]
    seen = set()
    cid = catid
    while cid not in seen:
        seen.add(cid)
        cat = categories.get(cid)
        if not cat or cat['parent_id'] == 0:
            break
        pid = cat['parent_id']
        if pid in ITEMID_MAP:
            return ITEMID_MAP[pid]
        cid = pid
    return 20


def find_existing_catids(rip_dir):
    """Return set of catids that already have a gallery page in rip/."""
    existing = set()
    pat = re.compile(r'com_phocagallery.*view=category.*&id=(\d+)')
    for fname in os.listdir(rip_dir):
        m = pat.search(fname)
        if m:
            existing.add(int(m.group(1)))
    return existing


def split_filename(filename):
    """'FOLDER/name.jpg' -> ('FOLDER', 'name.jpg')."""
    fn = filename.lstrip('/')
    if '/' in fn:
        return fn.split('/', 1)
    return '', fn


# ---------------------------------------------------------------------------
# HTML generation
# ---------------------------------------------------------------------------

def build_gallery_grid(catid, images):
    """Build the .phocagallery-box-file divs for each image."""
    parts = []
    for img in images:
        folder, fname = split_filename(img['filename'])
        if not folder:
            continue
        thumb_m = f'images/phocagallery/{folder}/thumbs/phoca_thumb_m_{fname}'
        thumb_l = f'images/phocagallery/{folder}/thumbs/phoca_thumb_l_{fname}'
        title = img['title']
        piclens = f'/{folder}/{fname}'
        parts.append(
            f'\t\t\t<div class="phocagallery-box-file" style="height:258px; width:220px">\n'
            f'\t\t\t\t<center>\n'
            f'\t\t\t\t\t<div class="phocagallery-box-file-first" style="height:218px;width:218px;">\n'
            f'\t\t\t\t\t\t<div class="phocagallery-box-file-second">\n'
            f'\t\t\t\t\t\t\t<div class="phocagallery-box-file-third">\n'
            f'\t\t\t\t\t\t\t\t<center>\n'
            f'\t\t\t\t\t\t\t\t<a class="shadowbox-button" title="{title}" href="{thumb_l}"'
            f' rel="shadowbox[PhocaGallery];options={{slideshowDelay:5}}" >'
            f'<img src="{thumb_m}" alt="{title}"  />'
            f'<span class="mbf-item">#phocagallerypiclens {catid}-phocagallerypiclenscode-{piclens}</span>'
            f'</a>\t\n'
            f'\t\t\t\t\t\t\t\t</center>\n'
            f'\t\t\t\t\t\t\t</div>\n'
            f'\t\t\t\t\t\t</div>\n'
            f'\t\t\t\t\t</div>\n'
            f'\t\t\t\t</center>\n'
            f'\t\t\t\t\n'
            f'\t\t\t<div class="name" style="font-size:12px">{title}</div>'
            f'<div class="detail" style="margin-top:2px">'
            f'<a href="javascript:PicLensLite.start();" title="PicLens" >'
            f'<img src="http://lite.piclens.com/images/PicLensButton.png" alt="PicLens"'
            f' width="16" height="12" border="0" style="margin-bottom:2px" /></a>'
            f'</div><div style="clear:both"></div></div>'
        )
    return '\n'.join(parts)


def build_stats_top3(catid, alias, itemid, images):
    """Build top-3 most-viewed image divs for the statistics panel."""
    top3 = sorted(images, key=lambda x: x['hits'], reverse=True)[:3]
    parts = []
    for img in top3:
        folder, fname = split_filename(img['filename'])
        if not folder:
            continue
        thumb_m = f'images/phocagallery/{folder}/thumbs/phoca_thumb_m_{fname}'
        detail_url = (
            f'index.php@option=com_phocagallery&amp;view=detail&amp;'
            f'catid={catid}%253A{alias}&amp;'
            f'id={img["id"]}%253A{img["alias"]}&amp;'
            f'tmpl=component&amp;Itemid={itemid}.html'
        )
        parts.append(
            f'\t\t\t<div class="phocagallery-box-file" style="height:258px; width:220px">\n'
            f'\t\t\t\t<center>\n'
            f'\t\t\t\t\t<div class="phocagallery-box-file-first" style="height:218px;width:218px;">\n'
            f'\t\t\t\t\t\t<div class="phocagallery-box-file-second">\n'
            f'\t\t\t\t\t\t\t<div class="phocagallery-box-file-third">\n'
            f'\t\t\t\t\t\t\t\t<center>\n'
            f'\t\t\t\t\t\t\t\t<a class="modal-button" href="{detail_url}"'
            f' rel="{{handler: \'iframe\', size: {{x: 680, y: 560}}, overlayOpacity: 0.3}}" >'
            f'<img src="{thumb_m}" alt="{img["title"]}"  /></a>\n'
            f'\t\t\t\t\t\t\t\t</center>\n'
            f'\t\t\t\t\t\t\t</div>\n'
            f'\t\t\t\t\t\t</div>\n'
            f'\t\t\t\t\t</div>\n'
            f'\t\t\t\t</center>\n'
            f'\t\t\t\t\n'
            f'\t\t\t<div class="name" style="font-size:12px">{img["title"]}</div>'
            f'<div class="detail" style="margin-top:2px;text-align:left">'
            f'<img src="components/com_phocagallery/assets/images/icon-viewed.gif"'
            f' alt="Detalhes da imagem"  />'
            f'&nbsp;&nbsp; {img["hits"]} x</div><div style="clear:both"></div></div>'
        )
    return '\n'.join(parts)


def build_dynamic_section(cat, images, itemid):
    """Build the full dynamic content block: gallery grid + pagination + stats."""
    catid = cat['id']
    alias = cat['alias']
    title = cat['title']
    hits = cat['hits']
    n_images = len(images)

    page_url = (
        f'index.php@option=com_phocagallery&amp;view=category&amp;'
        f'id={catid}%253A{alias}&amp;Itemid={itemid}.html'
    )

    grid_html = build_gallery_grid(catid, images)
    top3_html = build_stats_top3(catid, alias, itemid, images)

    return (
        f'<div class="componentheading">Galeria de Fotos - {title}</div>'
        f'<div class="contentpane"></div>'
        f'<form action="{page_url}" method="post" name="adminForm">'
        f'<div id="phocagallery"><div class="phoca-hr"></div>'
        f'{grid_html}\n'
        f'\t<div style="clear:both"></div>\n'
        f'</div>\n\n'
        f'<p>&nbsp;</p>\n\n'
        f'<div><center>'
        f'<div style="margin:0 10px 0 10px;display:inline;">Exibir num&nbsp;'
        f'<select name="limit" id="limit" class="inputbox" size="1" onchange="this.form.submit()">'
        f'<option value="5" >5</option>'
        f'<option value="10" >10</option>'
        f'<option value="15" >15</option>'
        f'<option value="20"  selected="selected">20</option>'
        f'<option value="50" >50</option>'
        f'<option value="0" >Todos</option>'
        f'</select></div>'
        f'<div style="margin:0 10px 0 10px;display:inline;" class="sectiontablefooter" ></div>'
        f'<div style="margin:0 10px 0 10px;display:inline;" class="pagecounter"></div>'
        f'</center></div></form>'
        f'<div>&nbsp;</div>'
        f'<div id="phocagallery-pane"><dl class="tabs" id="pane">'
        # votes tab
        f'<dt id="votes"><span>'
        f'<img src="components/com_phocagallery/assets/images/icon-vote.gif" alt=""  />'
        f'&nbsp;Nota</span></dt>'
        f'<dd><div id="phocagallery-votes">\n'
        f'<div style="font-size:1px;height:1px;margin:0px;padding:0px;">&nbsp;</div>\n'
        f'<fieldset>\n<legend>Vote nesta categoria</legend>\n\t\t\t\n'
        f'<p><strong>Nota</strong>: 0 / 0 voto</p>'
        f'<ul class="star-rating">'
        f'<li class="current-rating" style="width:0px"></li>'
        f'<li><span class="star1"></span></li>'
        f'<li><span class="stars2"></span></li>'
        f'<li><span class="stars3"></span></li>'
        f'<li><span class="stars4"></span></li>'
        f'<li><span class="stars5"></span></li>'
        f'</ul>'
        f'<p>Apenas usuários registrado pode votar nesta categoria</p>\t\n'
        f'</fieldset>\n</div>\n</dd>'
        # comments tab
        f'<dt id="comments"><span>'
        f'<img src="components/com_phocagallery/assets/images/icon-comment.gif" alt=""  />'
        f'&nbsp;Comentários</span></dt>'
        f'<dd><div id="phocagallery-comments">'
        f'<div style="font-size:1px;height:1px;margin:0px;padding:0px;">&nbsp;</div>'
        f'<fieldset><legend>Adicionar comentário</legend>'
        f'<p>Apenas usuários registrado pode comentar</p>\t\n'
        f'</fieldset>\n</div>\n</dd>'
        # statistics tab
        f'<dt id="statistics"><span>'
        f'<img src="components/com_phocagallery/assets/images/icon-statistics.gif" alt=""  />'
        f'&nbsp;Estatísticas</span></dt>'
        f'<dd><div id="phocagallery-statistics">\n'
        f'<div style="font-size:1px;height:1px;margin:0px;padding:0px;">&nbsp;</div>'
        f'<fieldset><legend>Categoria</legend><table>'
        f'<tr><td>Número de imagens publicadas na categoria: </td><td>{n_images}</td></tr>'
        f'<tr><td>Número de imagens não publicadas na categoria: </td><td>0</td></tr>'
        f'<tr><td>Categoria visualizada: </td><td>{hits} x</td></tr>'
        f'</table></fieldset>'
        f'<fieldset><legend>Imagens mais vistas nesta categoria</legend>'
        f'{top3_html}'
        f'</fieldset></div>\n</dd>'
        f'</dl></div>'
        f'<p>&nbsp;</p><div style="text-align:center"></div><p>&nbsp;</p>'
    )


def generate_html(template, cat, images, itemid):
    """Produce the full HTML for a gallery category page."""
    catid = cat['id']
    alias = cat['alias']
    title = cat['title']

    html = template

    # 1. Page <title>
    html = html.replace(
        '<title>Galeria de Fotos - Patati Patata na Oficina</title>',
        f'<title>Galeria de Fotos - {title}</title>',
    )

    # 2. PicLens RSS <link>
    html = html.replace(
        'href="images/phocagallery/33.rss"',
        f'href="images/phocagallery/{catid}.rss"',
    )

    # 3. Accessibility skip links + form action (all share the same URL substring)
    old_url = (
        'index.php@option=com_phocagallery&amp;view=category&amp;'
        'id=33%253Apatati-patata-na-oficina&amp;Itemid=20.html'
    )
    new_url = (
        f'index.php@option=com_phocagallery&amp;view=category&amp;'
        f'id={catid}%253A{alias}&amp;Itemid={itemid}.html'
    )
    html = html.replace(old_url, new_url)

    # 4. Dynamic content: componentheading through end of stats
    new_section = build_dynamic_section(cat, images, itemid)
    old_section = re.search(
        r'<div class="componentheading">Galeria de Fotos - Patati Patata na Oficina</div>'
        r'.*?'
        r'</dl></div><p>&nbsp;</p><div style="text-align:center"></div><p>&nbsp;</p>',
        html, re.DOTALL,
    )
    if old_section:
        html = html[:old_section.start()] + new_section + html[old_section.end():]

    return html


# ---------------------------------------------------------------------------
# RSS generation
# ---------------------------------------------------------------------------

def generate_rss(catid, images):
    """Build a PicLens-compatible RSS feed for a gallery category."""
    items = []
    for img in images:
        folder, fname = split_filename(img['filename'])
        if not folder:
            continue
        thumb_l = f'/images/phocagallery/{folder}/thumbs/phoca_thumb_l_{fname}'
        full = f'/images/phocagallery/{folder}/{fname}'
        guid = f'{catid}-phocagallerypiclenscode-/{folder}/{fname}'
        items.append(
            f'        <item>\n'
            f'            <title>{img["title"]}</title>\n'
            f'            <link>{thumb_l}</link>\n'
            f'            <media:thumbnail url="{thumb_l}" />\n'
            f'            <media:content url="{full}" />\n'
            f'            <guid isPermaLink="false">{guid}</guid>\n'
            f'        </item>'
        )
    return (
        '<?xml version="1.0" encoding="utf-8" standalone="yes"?>\n'
        '<rss xmlns:media="http://search.yahoo.com/mrss"'
        ' xmlns:atom="http://www.w3.org/2005/Atom" version="2.0">\n'
        '    <channel>\n'
        '        <atom:icon>http://www.phoca.cz/images/phoca-piclens.png</atom:icon>\n'
        + '\n'.join(items) + '\n'
        '    </channel>\n'
        '</rss>\n'
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print('Parsing SQL...', end=' ', flush=True)
    categories, images_by_catid = parse_sql(SQL_PATH)
    print(f'found {len(categories)} categories, images in {len(images_by_catid)} categories.')

    existing = find_existing_catids(RIP_DIR)
    print(f'Existing category pages ({len(existing)}): {sorted(existing)}')

    with open(TEMPLATE_FILE, encoding='utf-8') as f:
        template = f.read()

    missing = sorted(set(categories) - existing)
    print(f'Missing categories ({len(missing)}): {missing}\n')

    html_count = rss_count = 0

    for catid in missing:
        cat = categories[catid]
        alias = cat['alias']
        itemid = get_itemid(catid, categories)
        images = images_by_catid.get(catid, [])

        # HTML
        html_fname = (
            f'index.php@option=com_phocagallery&view=category'
            f'&id={catid}%3A{alias}&Itemid={itemid}.html'
        )
        html_path = os.path.join(RIP_DIR, html_fname)
        if not os.path.exists(html_path):
            html_content = generate_html(template, cat, images, itemid)
            with open(html_path, 'w', encoding='utf-8') as f:
                f.write(html_content)
            print(f'  [HTML] {html_fname}  ({len(images)} images)')
            html_count += 1

        # RSS
        rss_path = os.path.join(IMAGES_DIR, f'{catid}.rss')
        if not os.path.exists(rss_path):
            rss_content = generate_rss(catid, images)
            with open(rss_path, 'w', encoding='utf-8') as f:
                f.write(rss_content)
            print(f'  [RSS]  {catid}.rss')
            rss_count += 1

    print(f'\nDone. Generated {html_count} HTML files and {rss_count} RSS files.')


if __name__ == '__main__':
    main()
