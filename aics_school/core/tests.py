from unittest.mock import MagicMock, patch

from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from .forms import StudentSupervisorAssignmentForm
from .models import AicsCenter, CustomUser, OneTimeCode, Report, StudentProfile, SupervisorProfile


class CoreWorkflowTests(TestCase):
    def setUp(self):
        self.center = AicsCenter.objects.create(name="Main Campus", location="Douala")
        self.other_center = AicsCenter.objects.create(name="Annex Campus", location="Yaounde")

        self.supervisor_user = CustomUser.objects.create_user(
            username="supervisor1",
            password="StrongPass123!",
            email="supervisor@example.com",
            first_name="Nora",
            last_name="Jones",
            role=CustomUser.Role.SUPERVISOR,
            center=self.center,
        )
        self.supervisor = SupervisorProfile.objects.create(user=self.supervisor_user, center=self.center)

        self.student_user = CustomUser.objects.create_user(
            username="student1",
            password="StrongPass123!",
            email="student@example.com",
            first_name="Alice",
            last_name="Mbia",
            role=CustomUser.Role.STUDENT,
            center=self.center,
        )
        self.student = StudentProfile.objects.create(
            user=self.student_user,
            first_name="Alice",
            last_name="Mbia",
            matricule="AICS001",
            center=self.center,
            level="L3",
            specialization="SE",
            assigned_supervisor=self.supervisor,
        )

    def test_student_can_exist_without_supervisor_assignment(self):
        self.student.assigned_supervisor = None
        self.student.full_clean()

    def test_assignment_form_limits_each_batch_to_fifteen_students(self):
        extra_students = []
        for index in range(2, 18):
            user = CustomUser.objects.create_user(
                username=f"student{index}",
                password="StrongPass123!",
                email=f"student{index}@example.com",
                first_name=f"Student{index}",
                last_name="Test",
                role=CustomUser.Role.STUDENT,
                center=self.center,
            )
            extra_students.append(
                StudentProfile.objects.create(
                    user=user,
                    first_name=f"Student{index}",
                    last_name="Test",
                    matricule=f"AICS{index:03d}",
                    center=self.center,
                    level="L3",
                    specialization="SE",
                )
            )

        form = StudentSupervisorAssignmentForm(
            data={
                'supervisor': self.supervisor.pk,
                'students': [student.pk for student in [self.student, *extra_students]],
            }
        )

        self.assertFalse(form.is_valid())
        self.assertIn("maximum of 15 students", form.errors['students'][0])

    def test_assignment_form_assigns_selected_students_to_supervisor(self):
        self.student.assigned_supervisor = None
        self.student.save()

        second_user = CustomUser.objects.create_user(
            username="student-batch",
            password="StrongPass123!",
            email="batch@example.com",
            first_name="Batch",
            last_name="Student",
            role=CustomUser.Role.STUDENT,
            center=self.center,
        )
        second_student = StudentProfile.objects.create(
            user=second_user,
            first_name="Batch",
            last_name="Student",
            matricule="AICS777",
            center=self.center,
            level="L2",
            specialization="SR",
        )

        form = StudentSupervisorAssignmentForm(
            data={
                'supervisor': self.supervisor.pk,
                'students': [self.student.pk, second_student.pk],
            }
        )

        self.assertTrue(form.is_valid(), form.errors)
        supervisor, updated = form.save()
        self.assertEqual(supervisor.pk, self.supervisor.pk)
        self.assertEqual(updated, 2)
        self.student.refresh_from_db()
        second_student.refresh_from_db()
        self.assertEqual(self.student.assigned_supervisor_id, self.supervisor.pk)
        self.assertEqual(second_student.assigned_supervisor_id, self.supervisor.pk)

    def test_student_can_verify_upload_code_live(self):
        self.client.login(username="student1", password="StrongPass123!")
        OneTimeCode.objects.create(student=self.student, supervisor=self.supervisor, code="ABC12345")

        response = self.client.get(reverse('verify_upload_code'), {'code': 'ABC12345'})

        self.assertEqual(response.status_code, 200)
        self.assertJSONEqual(response.content, {'valid': True, 'message': 'Upload code verified.'})

    def test_student_upload_marks_code_used_and_creates_report(self):
        self.client.login(username="student1", password="StrongPass123!")
        otp = OneTimeCode.objects.create(student=self.student, supervisor=self.supervisor, code="UPLOAD01")
        pdf_file = SimpleUploadedFile("report.pdf", b"%PDF-1.4 test report", content_type="application/pdf")

        response = self.client.post(
            reverse('upload_report'),
            {
                'theme': 'Campus Network Monitoring',
                'description': 'Final year report',
                'upload_code': 'UPLOAD01',
                'pdf_file': pdf_file,
            },
            follow=True,
        )

        self.assertRedirects(response, reverse('dashboard'))
        report = Report.objects.get(student=self.student)
        otp.refresh_from_db()
        self.assertEqual(report.theme, 'Campus Network Monitoring')
        self.assertTrue(otp.is_used)

    def test_student_cannot_upload_more_than_one_report(self):
        Report.objects.create(
            student=self.student,
            theme="Existing Report",
            description="Already uploaded",
            pdf_file=SimpleUploadedFile("existing.pdf", b"%PDF-1.4 existing", content_type="application/pdf"),
            promotion_year=2026,
        )
        self.client.login(username="student1", password="StrongPass123!")

        response = self.client.get(reverse('upload_report'), follow=True)

        self.assertRedirects(response, reverse('dashboard'))

    def test_supervisor_can_only_generate_code_for_assigned_student(self):
        outsider_user = CustomUser.objects.create_user(
            username="outsider",
            password="StrongPass123!",
            email="outsider@example.com",
            first_name="Out",
            last_name="Sider",
            role=CustomUser.Role.STUDENT,
            center=self.other_center,
        )
        outsider_supervisor_user = CustomUser.objects.create_user(
            username="supervisor2",
            password="StrongPass123!",
            email="supervisor2@example.com",
            first_name="Other",
            last_name="Supervisor",
            role=CustomUser.Role.SUPERVISOR,
            center=self.other_center,
        )
        outsider_supervisor = SupervisorProfile.objects.create(user=outsider_supervisor_user, center=self.other_center)
        outsider_student = StudentProfile.objects.create(
            user=outsider_user,
            first_name="Out",
            last_name="Sider",
            matricule="AICS999",
            center=self.other_center,
            level="L2",
            specialization="SR",
            assigned_supervisor=outsider_supervisor,
        )

        with self.assertRaises(ValidationError):
            OneTimeCode(student=outsider_student, supervisor=self.supervisor, code="FAILCODE").full_clean()

    def test_report_pdf_streams_inline(self):
        report = Report.objects.create(
            student=self.student,
            theme="Inline PDF",
            description="Rendered inside platform",
            pdf_file=SimpleUploadedFile("inline.pdf", b"%PDF-1.4 inline", content_type="application/pdf"),
            promotion_year=2026,
        )

        response = self.client.get(reverse('stream_report_pdf', args=[report.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')
        self.assertIn('inline;', response['Content-Disposition'])

    @patch('core.models.fitz')
    def test_report_save_generates_preview_automatically(self, mock_fitz):
        mock_document = MagicMock()
        mock_page = MagicMock()
        mock_pixmap = MagicMock()

        mock_fitz.open.return_value = mock_document
        mock_document.__len__.return_value = 1
        mock_document.load_page.return_value = mock_page
        mock_page.get_pixmap.return_value = mock_pixmap
        mock_pixmap.tobytes.return_value = b'png-bytes'

        report = Report.objects.create(
            student=self.student,
            theme="Preview PDF",
            description="Preview generated from save",
            pdf_file=SimpleUploadedFile("preview.pdf", b"%PDF-1.4 preview", content_type="application/pdf"),
            promotion_year=2026,
        )

        report.refresh_from_db()
        self.assertTrue(report.preview_image.name.endswith('.png'))

    def test_report_list_supports_search_and_advanced_filters(self):
        Report.objects.create(
            student=self.student,
            theme="Network Monitoring",
            description="Campus monitoring report",
            pdf_file=SimpleUploadedFile("network.pdf", b"%PDF-1.4 network", content_type="application/pdf"),
            promotion_year=2026,
            grade=18,
            status=Report.Status.APPROVED,
        )

        second_supervisor_user = CustomUser.objects.create_user(
            username="supervisor3",
            password="StrongPass123!",
            email="supervisor3@example.com",
            first_name="Mila",
            last_name="Stone",
            role=CustomUser.Role.SUPERVISOR,
            center=self.center,
        )
        second_supervisor = SupervisorProfile.objects.create(user=second_supervisor_user, center=self.center)
        second_student_user = CustomUser.objects.create_user(
            username="student2",
            password="StrongPass123!",
            email="student2@example.com",
            first_name="Brian",
            last_name="Kola",
            role=CustomUser.Role.STUDENT,
            center=self.center,
        )
        second_student = StudentProfile.objects.create(
            user=second_student_user,
            first_name="Brian",
            last_name="Kola",
            matricule="AICS002",
            center=self.center,
            level="L2",
            specialization="SR",
            assigned_supervisor=second_supervisor,
        )
        Report.objects.create(
            student=second_student,
            theme="Cloud Security",
            description="Security report",
            pdf_file=SimpleUploadedFile("cloud.pdf", b"%PDF-1.4 cloud", content_type="application/pdf"),
            promotion_year=2025,
            status=Report.Status.SUBMITTED,
        )

        response = self.client.get(
            reverse('report_list'),
            {'q': 'Network', 'status': Report.Status.APPROVED, 'graded': 'yes', 'level': 'L3'},
        )

        self.assertEqual(response.status_code, 200)
        reports = list(response.context['reports'])
        self.assertEqual(len(reports), 1)
        self.assertEqual(reports[0].theme, "Network Monitoring")
