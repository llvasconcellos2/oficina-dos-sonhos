"""
fix-bad-pdf-links.py - strip incorrectly appended .pdf from HTML links.

The strip-itemid.ps1 script accidentally added .pdf to links that use the
original index.php?... format (not yet converted to the wget @-style).
Those links are not PDF files, so the .pdf suffix must be removed.

Usage:
    python scripts/fix-bad-pdf-links.py           # dry-run
    python scripts/fix-bad-pdf-links.py --fix     # apply
"""

import os
import re
import html as html_mod
import sys
from urllib.parse import unquote

RIP_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'rip')
RIP_DIR = os.path.normpath(RIP_DIR)
FIX = '--fix' in sys.argv

real_pdfs = {f for f in os.listdir(RIP_DIR) if f.endswith('.pdf')}
print(f'Real PDF files in rip/: {len(real_pdfs)}')

ATTR_RE = re.compile(
    r'(\b(?:href|src|action)\s*=\s*(["\']))([^"\']*\.pdf)\2',
    re.IGNORECASE,
)

SKIP_SCHEMES = ('http:', 'https:', 'ftp:', '//', 'mailto:', 'javascript:', 'data:')


def is_real_pdf(url):
    """Return True if the url resolves to an actual PDF file in rip/."""
    # HTML-unescape (&amp; -> &), then URL-decode once (%253A -> %3A)
    resolved = unquote(html_mod.unescape(url))
    lower = resolved.lower()
    # External links: never strip (they may be real PDFs on remote servers)
    if any(lower.startswith(s) for s in SKIP_SCHEMES):
        return True
    # Local: check against the set of real PDF filenames
    basename = os.path.basename(resolved)
    return basename in real_pdfs


patched = 0

for fname in sorted(os.listdir(RIP_DIR)):
    if not fname.lower().endswith('.html'):
        continue
    path = os.path.join(RIP_DIR, fname)
    with open(path, encoding='utf-8', errors='replace') as f:
        content = f.read()

    def fix_match(m):
        attr_prefix = m.group(1)
        quote = m.group(2)
        url = m.group(3)
        if is_real_pdf(url):
            return m.group(0)         # keep — real PDF or external
        stripped = url[:-4]           # drop .pdf
        print(f'  FIX: {url!r}  ->  {stripped!r}')
        return f'{attr_prefix}{stripped}{quote}'

    updated = ATTR_RE.sub(fix_match, content)
    if updated != content:
        print(f'PATCH: {fname}')
        patched += 1
        if FIX:
            with open(path, 'w', encoding='utf-8') as f:
                f.write(updated)

suffix = '' if FIX else ' (dry-run -- pass --fix to apply)'
print(f'\nPatched: {patched} files{suffix}')
