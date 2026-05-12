from django.core.management.base import BaseCommand
from core.models import Report

class Command(BaseCommand):
    help = 'Regenerate preview images for all reports'

    def handle(self, *args, **options):
        # First, clear existing preview_images as names have changed
        Report.objects.exclude(preview_image='').update(preview_image='')
        reports = Report.objects.exclude(pdf_file='')
        for report in reports:
            self.stdout.write(f'Generating preview for report {report.pk}')
            generated = report._generate_preview_image()
            if generated:
                report.save(update_fields=['preview_image'])
                self.stdout.write(self.style.SUCCESS(f'Generated preview for {report.pk}'))
            else:
                self.stdout.write(self.style.WARNING(f'Failed to generate preview for {report.pk}'))