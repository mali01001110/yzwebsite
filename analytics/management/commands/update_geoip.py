"""
Download or refresh the MaxMind GeoLite2 databases.

Optional. Country already resolves for free from Cloudflare's ``CF-IPCountry``
header, so this is only needed for city, coordinates and ASN — and the ASN data
is what powers the datacenter bot signal.

Requires a free MaxMind account. Set ``MAXMIND_LICENSE_KEY`` in the environment
and ``ANALYTICS['GEOIP_PATH']`` to a writable directory, then::

    python manage.py update_geoip

On Render the container filesystem is ephemeral, so this belongs in
``build.sh`` rather than being run once by hand — otherwise the databases
disappear on the next deploy. The combined download is roughly 70 MB.

Uses urllib from the standard library rather than requests: this runs at most
once per deploy and adding an HTTP dependency for it would be disproportionate.
"""
from __future__ import annotations

import os
import shutil
import tarfile
import tempfile
import urllib.error
import urllib.request
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from analytics import geo
from analytics.defaults import get_setting

DOWNLOAD_URL = (
    'https://download.maxmind.com/app/geoip_download'
    '?edition_id={edition}&license_key={key}&suffix=tar.gz'
)
EDITIONS = {
    'GeoLite2-City': 'GEOIP_CITY_FILENAME',
    'GeoLite2-ASN': 'GEOIP_ASN_FILENAME',
}
TIMEOUT_SECONDS = 300


class Command(BaseCommand):
    help = 'Download the MaxMind GeoLite2 City and ASN databases into GEOIP_PATH.'

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            '--license-key',
            default=os.environ.get('MAXMIND_LICENSE_KEY', ''),
            help='MaxMind licence key. Defaults to $MAXMIND_LICENSE_KEY.',
        )
        parser.add_argument(
            '--path',
            default=None,
            help="Target directory. Defaults to ANALYTICS['GEOIP_PATH'].",
        )
        parser.add_argument(
            '--status',
            action='store_true',
            help='Report which databases are present, and download nothing.',
        )

    def handle(self, *args, **options) -> None:
        if options['status']:
            self._report_status()
            return

        licence_key = options['license_key']
        if not licence_key:
            raise CommandError(
                'No licence key. Pass --license-key or set MAXMIND_LICENSE_KEY. '
                'A free key is available from maxmind.com; country-level data '
                'needs none, since it comes from the Cloudflare header.'
            )

        target = Path(options['path'] or get_setting('GEOIP_PATH') or '')
        if not str(target):
            raise CommandError("Set ANALYTICS['GEOIP_PATH'] or pass --path.")

        target.mkdir(parents=True, exist_ok=True)

        for edition, setting_name in EDITIONS.items():
            destination = target / get_setting(setting_name)
            self.stdout.write(f'Downloading {edition}…')
            try:
                self._download_edition(edition, licence_key, destination)
            except urllib.error.HTTPError as error:
                raise CommandError(
                    f'{edition} download failed with HTTP {error.code}. '
                    'A 401 means the licence key is wrong.'
                )
            except (urllib.error.URLError, OSError) as error:
                raise CommandError(f'{edition} download failed: {error}')
            self.stdout.write(self.style.SUCCESS(f'  wrote {destination}'))

        # The readers memory-map their file for the process lifetime, so a
        # fresh download is invisible until they are dropped.
        geo.reset_readers()
        self.stdout.write(self.style.SUCCESS('GeoIP databases updated.'))

    def _download_edition(self, edition: str, licence_key: str, destination: Path) -> None:
        """
        Fetch one tarball and extract the single .mmdb inside it.

        Written to a temporary file and moved into place, so an interrupted
        download cannot leave a truncated database that the reader would then
        fail on at runtime.
        """
        url = DOWNLOAD_URL.format(edition=edition, key=licence_key)

        with tempfile.TemporaryDirectory() as workspace:
            archive = Path(workspace) / f'{edition}.tar.gz'
            with urllib.request.urlopen(url, timeout=TIMEOUT_SECONDS) as response:
                with archive.open('wb') as handle:
                    shutil.copyfileobj(response, handle)

            with tarfile.open(archive, 'r:gz') as tar:
                member = next(
                    (m for m in tar.getmembers() if m.name.endswith('.mmdb')), None
                )
                if member is None:
                    raise CommandError(f'No .mmdb found inside the {edition} archive.')

                # Flattened deliberately: the archive nests the database under a
                # dated directory, and extracting the member name verbatim would
                # also honour any path traversal inside it.
                member.name = Path(member.name).name
                tar.extract(member, path=workspace, filter='data')

            shutil.move(str(Path(workspace) / member.name), str(destination))

    def _report_status(self) -> None:
        status = geo.database_status()
        self.stdout.write(f'GEOIP_ENABLED: {status["enabled"]}')
        self.stdout.write(f'GEOIP_PATH:    {status["path"] or "(unset)"}')
        if not status['files']:
            self.stdout.write(self.style.WARNING('No path configured; nothing to check.'))
            return
        for name, present in status['files'].items():
            style = self.style.SUCCESS if present else self.style.WARNING
            self.stdout.write(style(f'  {name}: {"present" if present else "missing"}'))
