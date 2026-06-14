"""
check_links.py - find broken local links in the rip/ wget crawl.

Usage:
    python check_links.py           # scan rip/ next to this script
    python check_links.py --quiet   # omit summary line at the end

Output lines are in VSCode-clickable format:
    rip/path/file.html:line:col: BROKEN [attr] "original" -> "resolved_path"
"""

import os
import re
import sys
import html as html_mod
from urllib.parse import unquote

ATTR_RE = re.compile(r'\b(href|src|action)\s*=\s*(["\'])([^"\']*)\2', re.IGNORECASE)

SKIP_SCHEMES = ('http:', 'https:', 'ftp:', '//', 'mailto:', 'javascript:', 'data:')

RIP_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'rip')
SITE_PREFIX = '/oficinadossonhos/'


def resolve(raw_value, html_file_abs):
    """Return the absolute filesystem path the link should point to, or None to skip."""
    # HTML-decode (&amp; -> &) then URL-decode once (%253A -> %3A)
    # wget saves filenames with single-encoded chars (%3A), but HTML may double-encode them
    value = unquote(html_mod.unescape(raw_value).strip())

    if not value:
        return None

    lower = value.lower()
    if any(lower.startswith(s) for s in SKIP_SCHEMES):
        return None

    # Strip fragment
    if '#' in value:
        value = value[:value.index('#')]
    if not value:
        return None

    # Absolute paths
    if value.startswith('/'):
        if value.startswith(SITE_PREFIX):
            rel = value[len(SITE_PREFIX):]
        else:
            rel = value.lstrip('/')
        return os.path.normpath(os.path.join(RIP_DIR, rel.replace('/', os.sep)))

    # Relative path — resolve from the HTML file's directory
    base_dir = os.path.dirname(html_file_abs)
    return os.path.normpath(os.path.join(base_dir, value.replace('/', os.sep)))


def wget_fallback(raw_value, html_file_abs):
    """For PHP query-string URLs, try the wget @-encoded filename."""
    value = unquote(html_mod.unescape(raw_value).strip())
    if '?' not in value:
        return None

    # Convert ?key=val&key2=val2 -> @key=val&key2=val2 then append .html
    wget_name = value.replace('?', '@') + '.html'

    if wget_name.startswith('/'):
        if wget_name.startswith(SITE_PREFIX):
            rel = wget_name[len(SITE_PREFIX):]
        else:
            rel = wget_name.lstrip('/')
        return os.path.normpath(os.path.join(RIP_DIR, rel.replace('/', os.sep)))

    base_dir = os.path.dirname(html_file_abs)
    return os.path.normpath(os.path.join(base_dir, wget_name.replace('/', os.sep)))


def check_file(html_file_abs):
    """Yield (line_num, col, attr, raw_value, resolved_path) for each broken link."""
    try:
        with open(html_file_abs, encoding='utf-8', errors='replace') as f:
            for line_num, line in enumerate(f, 1):
                for m in ATTR_RE.finditer(line):
                    attr = m.group(1).lower()
                    raw_value = m.group(3)
                    col = m.start(3) + 1  # 1-based, points to the URL value

                    resolved = resolve(raw_value, html_file_abs)
                    if resolved is None:
                        continue  # skip (external / anchor / empty)

                    if os.path.exists(resolved):
                        continue  # OK

                    # wget appends .html to every crawled page — try that first
                    if os.path.exists(resolved + '.html'):
                        continue  # OK via wget .html suffix

                    # Try wget fallback for PHP query strings (? -> @, + .html)
                    fallback = wget_fallback(raw_value, html_file_abs)
                    if fallback and os.path.exists(fallback):
                        continue  # OK via wget filename
                    if fallback and os.path.exists(fallback + '.html'):
                        continue  # OK via wget filename + .html

                    yield line_num, col, attr, raw_value, resolved
    except OSError as e:
        print(f'ERROR reading {html_file_abs}: {e}', file=sys.stderr)


def main():
    quiet = '--quiet' in sys.argv

    if not os.path.isdir(RIP_DIR):
        print(f'ERROR: rip/ directory not found at {RIP_DIR}', file=sys.stderr)
        sys.exit(1)

    broken_count = 0
    file_count = 0

    for dirpath, _dirs, filenames in os.walk(RIP_DIR):
        for fname in filenames:
            if not fname.lower().endswith('.html'):
                continue
            abs_path = os.path.join(dirpath, fname)
            rel_path = os.path.relpath(abs_path, os.path.dirname(RIP_DIR))
            file_count += 1

            for line_num, col, attr, raw_value, resolved in check_file(abs_path):
                broken_count += 1
                resolved_rel = os.path.relpath(resolved, os.path.dirname(RIP_DIR))
                print(f'{rel_path}:{line_num}:{col}: BROKEN [{attr}] "{raw_value}" -> "{resolved_rel}"')

    if not quiet:
        print(f'\n--- {broken_count} broken link(s) in {file_count} HTML file(s) ---', file=sys.stderr)


if __name__ == '__main__':
    main()
