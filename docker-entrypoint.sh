#!/bin/bash
set -e

# Patch DB host to Docker service name (idempotent — safe to re-run)
grep -q "var \$host = 'db'" /var/www/html/configuration.php 2>/dev/null || \
  sed -i "s/var \$host = 'localhost'/var \$host = 'db'/" /var/www/html/configuration.php

# Create .htaccess from Joomla's template if not present (enables clean URLs)
if [ ! -f /var/www/html/.htaccess ] && [ -f /var/www/html/htaccess.txt ]; then
  cp /var/www/html/htaccess.txt /var/www/html/.htaccess
fi

exec "$@"
