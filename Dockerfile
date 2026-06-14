FROM php:5.6-apache

RUN docker-php-ext-install mysql mysqli
RUN docker-php-ext-configure gd && docker-php-ext-install gd
RUN a2enmod rewrite
# Allow .htaccess overrides (needed for Joomla SEF URLs)
RUN sed -i 's/AllowOverride None/AllowOverride All/g' /etc/apache2/apache2.conf

COPY docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh

ENTRYPOINT ["/docker-entrypoint.sh"]
CMD ["apache2-foreground"]
