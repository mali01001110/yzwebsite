"""
Answer a data-subject request: export or erase everything held for one visitor.

    python manage.py visitor_data --export <visitor_id>
    python manage.py visitor_data --delete <visitor_id> --yes

The identifier is the rotating salted hash, which is the only handle that
exists — no raw IP address is stored anywhere, so there is nothing else to
search by. That limits what these commands can reach: the salt rotates every 24
hours, so a request reaches only the rows recorded under the identifier given.
Earlier activity carries a different identifier and is already unlinkable,
which is the point of rotating the salt in the first place.
"""
from __future__ import annotations

import json

from django.core.management.base import BaseCommand, CommandError

from analytics.exports import (
    delete_ip_data,
    delete_visitor_data,
    export_ip_data,
    export_visitor_data,
)


class Command(BaseCommand):
    help = 'Export or erase all stored analytics data for one visitor identifier.'

    def add_arguments(self, parser) -> None:
        group = parser.add_mutually_exclusive_group(required=True)
        group.add_argument('--export', metavar='VISITOR_ID', help='Print everything held, as JSON.')
        group.add_argument('--delete', metavar='VISITOR_ID', help='Erase everything held.')
        group.add_argument(
            '--export-ip',
            metavar='IP_ADDRESS',
            help='Print the raw-address listing row for one address.',
        )
        group.add_argument(
            '--delete-ip',
            metavar='IP_ADDRESS',
            help='Erase the raw-address listing row for one address.',
        )
        parser.add_argument('--yes', action='store_true', help='Confirm an erasure.')
        parser.add_argument('--output', help='Write the export to this file instead of stdout.')

    def handle(self, *args, **options) -> None:
        if options['export']:
            self._export(options['export'], options['output'])
        elif options['export_ip']:
            self._export_ip(options['export_ip'], options['output'])
        elif options['delete_ip']:
            self._delete_ip(options['delete_ip'], options['yes'])
        else:
            self._delete(options['delete'], options['yes'])

    def _export_ip(self, ip_address: str, output_path: str | None) -> None:
        payload = json.dumps(export_ip_data(ip_address), indent=2, default=str)
        if output_path:
            with open(output_path, 'w', encoding='utf-8') as handle:
                handle.write(payload)
            self.stdout.write(self.style.SUCCESS(f'Wrote {output_path}'))
        else:
            self.stdout.write(payload)

    def _delete_ip(self, ip_address: str, confirmed: bool) -> None:
        if not confirmed:
            raise CommandError('Erasure is irreversible. Re-run with --yes to confirm.')

        if delete_ip_data(ip_address):
            self.stdout.write(self.style.SUCCESS(f'Erased the record for {ip_address}.'))
        else:
            self.stdout.write(self.style.WARNING('No record held for that address.'))

    def _export(self, visitor_id: str, output_path: str | None) -> None:
        payload = json.dumps(export_visitor_data(visitor_id), indent=2, default=str)
        if output_path:
            with open(output_path, 'w', encoding='utf-8') as handle:
                handle.write(payload)
            self.stdout.write(self.style.SUCCESS(f'Wrote {output_path}'))
        else:
            self.stdout.write(payload)

    def _delete(self, visitor_id: str, confirmed: bool) -> None:
        if not confirmed:
            raise CommandError('Erasure is irreversible. Re-run with --yes to confirm.')

        removed = delete_visitor_data(visitor_id)
        if not removed.get('visitors'):
            self.stdout.write(self.style.WARNING('No data held for that identifier.'))
            return

        for table, count in removed.items():
            self.stdout.write(f'  {table}: {count}')
        self.stdout.write(self.style.SUCCESS('Erased.'))
