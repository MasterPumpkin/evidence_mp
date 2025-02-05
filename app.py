import os

# Pokud se settings nachází v /srv/app/moje_aplikace,
# bude obsah pro DJANGO_SETTINGS_MODULE: moje_aplikace.settings
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "evidence_mp.settings")

from django.core.wsgi import get_wsgi_application
application = get_wsgi_application()