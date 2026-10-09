from django.core.management.base import BaseCommand, CommandError

from mes.importers import import_test_reports


class Command(BaseCommand):
    help = "Import product builds and test reports from a test-report workbook (.xlsx/.xlsm)."

    def add_arguments(self, parser):
        parser.add_argument("path", help="Path to the workbook")

    def handle(self, *args, path, **options):
        try:
            count = import_test_reports(path)
        except FileNotFoundError:
            raise CommandError(f"File not found: {path}")
        self.stdout.write(self.style.SUCCESS(f"Imported {count} test report(s)."))
