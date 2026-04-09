from django.db import models
from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
import random
import string
import os
import io

# Optional: Try to import fitz for PDF-to-Image preview
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

    def __str__(self):
        center_info = f" - {self.center.name}" if self.center else ""
        return f"{self.username} ({self.get_role_display()}){center_info}"

class SupervisorProfile(models.Model):
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE, related_name='supervisor_profile')
    center = models.ForeignKey(AicsCenter, on_delete=models.CASCADE)

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
        # If student is assigned to a supervisor, ensure they are in the same center
        if self.assigned_supervisor and self.assigned_supervisor.center != self.center:
            raise ValidationError("Assigned supervisor must be in the same center as the student.")

    def save(self, *args, **kwargs):
        self.full_clean()
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
        # Enforce that only assigned supervisor can generate code
        if self.student.assigned_supervisor != self.supervisor:
            raise ValidationError("You can only generate codes for students assigned to you.")

    def save(self, *args, **kwargs):
        self.full_clean()
        if not self.code:
            self.code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
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

    def save(self, *args, **kwargs):
        is_new_pdf = False
        if not self.pk:
            is_new_pdf = True
        else:
            old_instance = Report.objects.get(pk=self.pk)
            if old_instance.pdf_file != self.pdf_file:
                is_new_pdf = True

        super().save(*args, **kwargs)

        if is_new_pdf and self.pdf_file and fitz:
            try:
                # Open the PDF from the file field
                pdf_bytes = self.pdf_file.read()
                doc = fitz.open(stream=pdf_bytes, filetype="pdf")
                
                if len(doc) > 0:
                    page = doc.load_page(0)  # load the first page
                    pix = page.get_pixmap()
                    img_data = pix.tobytes("png")
                    
                    # Save the image back to the preview_image field
                    preview_name = f"preview_{os.path.basename(self.pdf_file.name)}.png"
                    self.preview_image.save(preview_name, ContentFile(img_data), save=False)
                    
                    # Update without triggering save() again to avoid recursion
                    Report.objects.filter(pk=self.pk).update(preview_image=self.preview_image.name)
                doc.close()
            except Exception as e:
                # Log or handle preview generation failure silently
                print(f"Failed to generate preview: {e}")

    def __str__(self):
        return f"{self.theme} ({self.student.matricule}) - {self.get_status_display()}"
