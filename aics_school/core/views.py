import datetime
import os

from django.contrib import messages
from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView
from django.core.exceptions import PermissionDenied
from django.http import FileResponse, Http404, JsonResponse
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy

from .forms import (
    GradeReportForm,
    ReportUploadForm,
    StudentSupervisorAssignmentForm,
    StudentCreationForm,
    StyledAuthenticationForm,
    SupervisorCreationForm,
)
from .models import CustomUser, OneTimeCode, Report, StudentProfile, SupervisorProfile


class SiteLoginView(LoginView):
    authentication_form = StyledAuthenticationForm
    template_name = 'registration/login.html'
    redirect_authenticated_user = True

    def get_success_url(self):
        return reverse_lazy('dashboard')


def home(request):
    return report_list(request)


def report_list(request):
    reports = Report.objects.select_related(
        'student',
        'student__user',
        'student__center',
        'student__assigned_supervisor__user',
    ).order_by('-upload_date')

    search_query = (request.GET.get('q') or '').strip()
    campus = (request.GET.get('campus') or '').strip()
    level = (request.GET.get('level') or '').strip()
    specialization = (request.GET.get('specialization') or '').strip()
    academic_year = (request.GET.get('academic_year') or '').strip()
    status = (request.GET.get('status') or '').strip()
    graded = (request.GET.get('graded') or '').strip()
    grade_min = (request.GET.get('grade_min') or '').strip()
    grade_max = (request.GET.get('grade_max') or '').strip()

    if search_query:
        reports = reports.filter(
            Q(theme__icontains=search_query)
            | Q(description__icontains=search_query)
            | Q(student__first_name__icontains=search_query)
            | Q(student__last_name__icontains=search_query)
            | Q(student__user__email__icontains=search_query)
            | Q(student__center__name__icontains=search_query)
        )

    if campus:
        reports = reports.filter(student__center_id=campus)
    if level:
        reports = reports.filter(student__level=level)
    if specialization:
        reports = reports.filter(student__specialization=specialization)
    if status:
        reports = reports.filter(status=status)
    if graded == 'yes':
        reports = reports.filter(grade__isnull=False)
    elif graded == 'no':
        reports = reports.filter(grade__isnull=True)
    if grade_min:
        try:
            reports = reports.filter(grade__gte=float(grade_min))
        except ValueError:
            pass
    if grade_max:
        try:
            reports = reports.filter(grade__lte=float(grade_max))
        except ValueError:
            pass
    if academic_year:
        try:
            year_start, year_end = academic_year.split('/', 1)
            reports = reports.filter(promotion_year=int(year_end))
        except (ValueError, TypeError):
            pass

    context = {
        'reports': reports,
        'search_query': search_query,
        'selected_campus': campus,
        'selected_level': level,
        'selected_specialization': specialization,
        'selected_academic_year': academic_year,
        'selected_status': status,
        'selected_graded': graded,
        'selected_grade_min': grade_min,
        'selected_grade_max': grade_max,
        'campus_options': StudentProfile.objects.select_related('center').values_list('center__id', 'center__name').distinct().order_by('center__name'),
        'level_options': StudentProfile._meta.get_field('level').choices,
        'specialization_options': StudentProfile._meta.get_field('specialization').choices,
        'status_options': Report.Status.choices,
        'academic_year_options': sorted(
            {report.academic_year for report in Report.objects.only('promotion_year')},
            reverse=True,
        ),
        'advanced_filters_active': any([campus, level, specialization, academic_year, status, graded, grade_min, grade_max]),
    }
    return render(request, 'core/report_list.html', context)


def report_detail(request, pk):
    report = get_object_or_404(
        Report.objects.select_related(
            'student',
            'student__user',
            'student__center',
            'student__assigned_supervisor__user',
        ),
        pk=pk,
    )
    return render(request, 'core/report_detail.html', {'report': report})


def stream_report_pdf(request, pk):
    report = get_object_or_404(Report, pk=pk)
    if not report.pdf_file:
        raise Http404("PDF not found.")

    response = FileResponse(
        report.pdf_file.open('rb'),
        content_type='application/pdf',
        as_attachment=False,
        filename=os.path.basename(report.pdf_file.name),
    )
    response['Content-Disposition'] = f'inline; filename="{os.path.basename(report.pdf_file.name)}"'
    response['Cache-Control'] = 'no-store'
    response['X-Content-Type-Options'] = 'nosniff'
    return response


def block_direct_report_media(request, path):
    raise Http404("Direct report file access is disabled.")


@login_required
def dashboard(request):
    if request.user.is_superuser or request.user.role == CustomUser.Role.ADMIN:
        return admin_dashboard(request)
    if request.user.role == CustomUser.Role.SUPERVISOR:
        return supervisor_dashboard(request)
    if request.user.role == CustomUser.Role.STUDENT:
        return student_dashboard(request)
    messages.warning(request, "Your account does not have a configured dashboard.")
    return redirect('report_list')


def _current_promotion_year():
    today = datetime.date.today()
    return today.year + 1 if today.month >= 9 else today.year


def _require_role(user, *roles):
    if not user.is_authenticated:
        raise PermissionDenied
    if user.is_superuser:
        return
    if user.role not in roles:
        raise PermissionDenied


def _report_queryset_for_admin(user):
    queryset = Report.objects.select_related('student', 'student__user', 'student__center', 'student__assigned_supervisor__user')
    if user.is_superuser:
        return queryset
    return queryset.filter(student__center=user.center)


def _student_queryset_for_admin(user):
    queryset = StudentProfile.objects.select_related('user', 'center', 'assigned_supervisor__user').order_by('matricule')
    if user.is_superuser:
        return queryset
    return queryset.filter(center=user.center)


def _supervisor_queryset_for_admin(user):
    queryset = SupervisorProfile.objects.select_related('user', 'center').order_by('user__first_name', 'user__last_name', 'user__username')
    if user.is_superuser:
        return queryset
    return queryset.filter(center=user.center)


@login_required
def admin_dashboard(request):
    _require_role(request.user, CustomUser.Role.ADMIN)

    students = _student_queryset_for_admin(request.user)
    supervisors = _supervisor_queryset_for_admin(request.user)
    reports = _report_queryset_for_admin(request.user).order_by('-upload_date')

    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'create_student':
            student_form = StudentCreationForm(request.POST, acting_user=request.user)
            supervisor_form = SupervisorCreationForm(acting_user=request.user)
            assignment_form = StudentSupervisorAssignmentForm(acting_user=request.user)
            if student_form.is_valid():
                student_form.save()
                messages.success(request, "Student created successfully.")
                return redirect('dashboard')
        elif action == 'create_supervisor':
            supervisor_form = SupervisorCreationForm(request.POST, acting_user=request.user)
            student_form = StudentCreationForm(acting_user=request.user)
            assignment_form = StudentSupervisorAssignmentForm(acting_user=request.user)
            if supervisor_form.is_valid():
                supervisor_form.save()
                messages.success(request, "Supervisor created successfully.")
                return redirect('dashboard')
        elif action == 'assign_students':
            assignment_form = StudentSupervisorAssignmentForm(request.POST, acting_user=request.user)
            student_form = StudentCreationForm(acting_user=request.user)
            supervisor_form = SupervisorCreationForm(acting_user=request.user)
            if assignment_form.is_valid():
                supervisor, updated_count = assignment_form.save()
                messages.success(
                    request,
                    f"{updated_count} student(s) assigned to {supervisor.user.get_full_name() or supervisor.user.username}.",
                )
                return redirect('dashboard')
        else:
            student_form = StudentCreationForm(acting_user=request.user)
            supervisor_form = SupervisorCreationForm(acting_user=request.user)
            assignment_form = StudentSupervisorAssignmentForm(acting_user=request.user)
    else:
        student_form = StudentCreationForm(acting_user=request.user)
        supervisor_form = SupervisorCreationForm(acting_user=request.user)
        assignment_form = StudentSupervisorAssignmentForm(acting_user=request.user)

    context = {
        'student_form': student_form,
        'supervisor_form': supervisor_form,
        'assignment_form': assignment_form,
        'students': students,
        'supervisors': supervisors,
        'reports': reports,
        'is_superadmin': request.user.is_superuser,
    }
    return render(request, 'core/admin_dashboard.html', context)


@login_required
def supervisor_dashboard(request):
    _require_role(request.user, CustomUser.Role.SUPERVISOR)

    supervisor = getattr(request.user, 'supervisor_profile', None)
    if supervisor is None:
        messages.error(request, "No supervisor profile is linked to your account.")
        return redirect('report_list')

    students = StudentProfile.objects.select_related('user', 'center', 'report').filter(
        assigned_supervisor=supervisor
    ).order_by('matricule')
    reports = Report.objects.select_related('student', 'student__user').filter(
        student__assigned_supervisor=supervisor
    ).order_by('-upload_date')

    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'generate_code':
            student = get_object_or_404(students, pk=request.POST.get('student_id'))
            otp = OneTimeCode.objects.filter(student=student, supervisor=supervisor, is_used=False).first()
            if otp is None:
                otp = OneTimeCode.objects.create(student=student, supervisor=supervisor)
            messages.success(request, f"Upload code for {student.matricule}: {otp.code}")
            return redirect('dashboard')

        if action == 'grade_report':
            report = get_object_or_404(reports, pk=request.POST.get('report_id'))
            form = GradeReportForm(request.POST, instance=report, prefix=f'report-{report.pk}')
            if form.is_valid():
                form.save()
                messages.success(request, f"Report '{report.theme}' graded successfully.")
                return redirect('dashboard')
            report_rows = []
            for item in reports:
                bound_form = form if item.pk == report.pk else GradeReportForm(instance=item, prefix=f'report-{item.pk}')
                report_rows.append({'report': item, 'form': bound_form})
            student_rows = [
                {
                    'student': student,
                    'current_code': OneTimeCode.objects.filter(
                        student=student, supervisor=supervisor, is_used=False
                    ).order_by('-created_at').first(),
                }
                for student in students
            ]
            return render(
                request,
                'core/supervisor_dashboard.html',
                {'student_rows': student_rows, 'report_rows': report_rows, 'supervisor': supervisor},
            )

    report_rows = [{'report': report, 'form': GradeReportForm(instance=report, prefix=f'report-{report.pk}')} for report in reports]
    student_rows = [
        {
            'student': student,
            'current_code': OneTimeCode.objects.filter(
                student=student, supervisor=supervisor, is_used=False
            ).order_by('-created_at').first(),
        }
        for student in students
    ]
    return render(
        request,
        'core/supervisor_dashboard.html',
        {'student_rows': student_rows, 'report_rows': report_rows, 'supervisor': supervisor},
    )


@login_required
def student_dashboard(request):
    _require_role(request.user, CustomUser.Role.STUDENT)

    student = getattr(request.user, 'student_profile', None)
    if student is None:
        messages.error(request, "No student profile is linked to your account.")
        return redirect('report_list')

    report = getattr(student, 'report', None)
    return render(request, 'core/student_dashboard.html', {'student': student, 'report': report})


@login_required
def upload_report(request):
    _require_role(request.user, CustomUser.Role.STUDENT)

    student = getattr(request.user, 'student_profile', None)
    if student is None:
        messages.error(request, "No student profile is linked to your account.")
        return redirect('dashboard')

    if hasattr(student, 'report'):
        messages.info(request, "You have already uploaded your final report.")
        return redirect('dashboard')

    if request.method == 'POST':
        form = ReportUploadForm(request.POST, request.FILES, student_profile=student)
        if form.is_valid():
            report = form.save(commit=False)
            report.student = student
            report.promotion_year = _current_promotion_year()
            report.tags = student.specialization
            report.save()

            if form.otp_instance:
                form.otp_instance.is_used = True
                form.otp_instance.save(update_fields=['is_used'])

            messages.success(request, "Report uploaded successfully.")
            return redirect('dashboard')
    else:
        form = ReportUploadForm(student_profile=student)

    return render(request, 'core/upload_report.html', {'form': form, 'student': student})


@login_required
def verify_upload_code(request):
    _require_role(request.user, CustomUser.Role.STUDENT)

    student = getattr(request.user, 'student_profile', None)
    if student is None:
        return JsonResponse({'valid': False, 'message': "No student profile found."}, status=400)

    code = (request.GET.get('code') or '').strip().upper()
    if not code:
        return JsonResponse({'valid': False, 'message': "Enter your upload code."})

    otp = OneTimeCode.objects.filter(student=student, code=code, is_used=False).first()
    if otp:
        return JsonResponse({'valid': True, 'message': "Upload code verified."})
    return JsonResponse({'valid': False, 'message': "Invalid or already used upload code."})


@login_required
def site_logout(request):
    logout(request)
    messages.success(request, "You have been logged out.")
    return redirect('login')
