import os
import random
import string

from django.contrib.auth.models import AbstractUser
from django.core.files.base import ContentFile
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

try:
    import fitz  # PyMuPDF
except ImportError:
    fitz = None

# --- 1. Core Management ---

class AicsCenter(models.Model):
    name = models.CharField(max_length=100)
    location = models.CharField(max_length=200)

    def __str__(self):
        return self.name

class Level(models.TextChoices):
    LEVEL_1 = 'L1', 'Level 1'
    LEVEL_2 = 'L2', 'Level 2'
    LEVEL_3 = 'L3', 'Level 3'

class Specialization(models.TextChoices):
    SOFTWARE_ENGINEERING = 'SE', 'Software Engineering'
    SYSTEMS_AND_NETWORKS = 'SR', 'Systems and Networks'
    GENIE_LOGICIEL = 'GL', 'Genie Logiciel'

# --- 2. User Profiles ---

class CustomUser(AbstractUser):
    class Role(models.TextChoices):
        ADMIN = 'admin', 'Admin'
        SUPERVISOR = 'supervisor', 'Supervisor'
        STUDENT = 'student', 'Student'
    
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.STUDENT)
    center = models.ForeignKey(AicsCenter, on_delete=models.SET_NULL, null=True, blank=True, help_text="Required for center-specific admins.")

    @property
    def is_campus_admin(self):
        return self.role == self.Role.ADMIN and not self.is_superuser

    @property
    def is_supervisor(self):
        return self.role == self.Role.SUPERVISOR

    @property
    def is_student(self):
        return self.role == self.Role.STUDENT

    def __str__(self):
        center_info = f" - {self.center.name}" if self.center else ""
        return f"{self.username} ({self.get_role_display()}){center_info}"

class SupervisorProfile(models.Model):
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE, related_name='supervisor_profile')
    center = models.ForeignKey(AicsCenter, on_delete=models.CASCADE)

    def clean(self):
        if self.user.role != CustomUser.Role.SUPERVISOR:
            raise ValidationError("Supervisor profile can only be attached to a supervisor user.")
        if self.user.center and self.user.center != self.center:
            raise ValidationError("Supervisor user campus must match the supervisor profile campus.")

    def save(self, *args, **kwargs):
        self.full_clean()
        if self.user.center_id != self.center_id:
            self.user.center = self.center
            self.user.save(update_fields=['center'])
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Supervisor: {self.user.get_full_name() or self.user.username} ({self.center.name})"

class StudentProfile(models.Model):
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE, related_name='student_profile')
    first_name = models.CharField(max_length=100, default="")
    last_name = models.CharField(max_length=100, default="")
    matricule = models.CharField(max_length=50, unique=True)
    center = models.ForeignKey(AicsCenter, on_delete=models.CASCADE)
    level = models.CharField(max_length=2, choices=Level.choices)
    specialization = models.CharField(max_length=2, choices=Specialization.choices, default=Specialization.SYSTEMS_AND_NETWORKS)
    assigned_supervisor = models.ForeignKey(
        SupervisorProfile, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='supervised_students'
    )

    def clean(self):
        if self.user.role != CustomUser.Role.STUDENT:
            raise ValidationError("Student profile can only be attached to a student user.")

        if self.user.center and self.user.center != self.center:
            raise ValidationError("Student user campus must match the student profile campus.")

        if self.assigned_supervisor and self.assigned_supervisor.center != self.center:
            raise ValidationError("Assigned supervisor must be in the same center as the student.")

    def save(self, *args, **kwargs):
        self.full_clean()
        if self.user.center_id != self.center_id:
            self.user.center = self.center
            self.user.save(update_fields=['center'])
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.matricule} - {self.first_name} {self.last_name}"

# --- 3. Security & Reports ---

class OneTimeCode(models.Model):
    student = models.ForeignKey(StudentProfile, on_delete=models.CASCADE, related_name='otps')
    supervisor = models.ForeignKey(SupervisorProfile, on_delete=models.CASCADE, related_name='generated_otps')
    code = models.CharField(max_length=10, unique=True)
    is_used = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def clean(self):
        if self.student.assigned_supervisor != self.supervisor:
            raise ValidationError("You can only generate codes for students assigned to you.")

        if self.student.center_id != self.supervisor.center_id:
            raise ValidationError("Student and supervisor must belong to the same campus.")

    def save(self, *args, **kwargs):
        if not self.code:
            self.code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        status = "Used" if self.is_used else "Valid"
        return f"Code for {self.student.matricule}: {self.code} ({status})"

def report_upload_path(instance, filename):
    # Format: reports/L1/SE/matricule_theme.pdf
    ext = filename.split('.')[-1]
    filename = f"{instance.student.matricule}_{instance.theme.replace(' ', '_')}.{ext}"
    return os.path.join('reports', instance.student.level, instance.student.specialization, filename)

class Report(models.Model):
    class Status(models.TextChoices):
        SUBMITTED = 'submitted', 'Submitted'
        UNDER_REVIEW = 'review', 'Under Review'
        APPROVED = 'approved', 'Approved'
        PUBLISHED = 'published', 'Published'

    student = models.OneToOneField(StudentProfile, on_delete=models.CASCADE, related_name='report')
    theme = models.CharField(max_length=255)
    description = models.TextField()
    pdf_file = models.FileField(upload_to=report_upload_path)
    preview_image = models.FileField(upload_to='reports/previews/', blank=True, null=True, help_text="Upload a preview image (FileField used to avoid Pillow dependency).")
    promotion_year = models.IntegerField()
    upload_date = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.SUBMITTED)
    tags = models.CharField(max_length=255, help_text="Comma-separated keywords", blank=True)
    grade = models.DecimalField(
        max_digits=4,
        decimal_places=2,
        blank=True,
        null=True,
        validators=[MinValueValidator(0), MaxValueValidator(20)],
        help_text="Grade over 20."
    )
    supervisor_feedback = models.TextField(blank=True)
    graded_at = models.DateTimeField(blank=True, null=True)

    @property
    def academic_year(self):
        return f"{self.promotion_year - 1}/{self.promotion_year}"

    @property
    def can_be_graded(self):
        return self.student.assigned_supervisor_id is not None

    def _generate_preview_image(self):
        if not self.pdf_file or fitz is None:
            return False

        self.pdf_file.open('rb')
        try:
            pdf_bytes = self.pdf_file.read()
            if not pdf_bytes:
                return False

            document = fitz.open(stream=pdf_bytes, filetype="pdf")
            try:
                if len(document) == 0:
                    return False
                page = document.load_page(0)
                pixmap = page.get_pixmap()
                image_data = pixmap.tobytes("png")
            finally:
                document.close()
        finally:
            self.pdf_file.close()

        preview_name = f"preview_{os.path.basename(self.pdf_file.name)}.png"
        self.preview_image.save(preview_name, ContentFile(image_data), save=False)
        return True

    def save(self, *args, **kwargs):
        pdf_changed = self._state.adding
        if not pdf_changed and self.pk:
            previous_pdf = Report.objects.filter(pk=self.pk).values_list('pdf_file', flat=True).first()
            pdf_changed = previous_pdf != self.pdf_file.name

        super().save(*args, **kwargs)

        if pdf_changed:
            generated = self._generate_preview_image()
            if generated:
                Report.objects.filter(pk=self.pk).update(preview_image=self.preview_image.name)

    def __str__(self):
        return f"{self.theme} ({self.student.matricule}) - {self.get_status_display()}"
