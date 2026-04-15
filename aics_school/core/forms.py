from django import forms
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.password_validation import validate_password
from django.utils import timezone

from .models import (
    AicsCenter,
    CustomUser,
    OneTimeCode,
    Report,
    StudentProfile,
    SupervisorProfile,
)


class StyledAuthenticationForm(AuthenticationForm):
    username = forms.CharField(widget=forms.TextInput(attrs={'class': 'form-control', 'autofocus': True}))
    password = forms.CharField(widget=forms.PasswordInput(attrs={'class': 'form-control'}))


class UserCreationBaseForm(forms.ModelForm):
    password1 = forms.CharField(label="Password", widget=forms.PasswordInput(attrs={'class': 'form-control'}))
    password2 = forms.CharField(label="Confirm password", widget=forms.PasswordInput(attrs={'class': 'form-control'}))

    class Meta:
        model = CustomUser
        fields = ['first_name', 'last_name', 'email', 'username']
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'username': forms.TextInput(attrs={'class': 'form-control'}),
        }

    def clean(self):
        cleaned_data = super().clean()
        password1 = cleaned_data.get('password1')
        password2 = cleaned_data.get('password2')
        if password1 and password2 and password1 != password2:
            self.add_error('password2', "Passwords do not match.")
        if password1:
            validate_password(password1, self.instance)
        return cleaned_data

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data['password1'])
        if commit:
            user.save()
        return user


class SupervisorCreationForm(UserCreationBaseForm):
    campus = forms.ModelChoiceField(
        queryset=AicsCenter.objects.all(),
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    class Meta(UserCreationBaseForm.Meta):
        fields = UserCreationBaseForm.Meta.fields

    def __init__(self, *args, acting_user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.acting_user = acting_user
        if acting_user and acting_user.is_campus_admin and acting_user.center:
            self.fields['campus'].initial = acting_user.center
            self.fields['campus'].queryset = AicsCenter.objects.filter(pk=acting_user.center_id)

    def clean_campus(self):
        campus = self.cleaned_data.get('campus') or getattr(self.acting_user, 'center', None)
        if not campus:
            raise forms.ValidationError("Campus is required.")
        return campus

    def save(self, commit=True):
        user = super().save(commit=False)
        user.role = CustomUser.Role.SUPERVISOR
        user.center = self.cleaned_data['campus']
        user.is_staff = False
        if commit:
            user.save()
            SupervisorProfile.objects.create(user=user, center=user.center)
        return user


class StudentCreationForm(UserCreationBaseForm):
    matricule = forms.CharField(widget=forms.TextInput(attrs={'class': 'form-control'}))
    level = forms.ChoiceField(choices=StudentProfile._meta.get_field('level').choices, widget=forms.Select(attrs={'class': 'form-select'}))
    specialization = forms.ChoiceField(
        choices=StudentProfile._meta.get_field('specialization').choices,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    campus = forms.ModelChoiceField(
        queryset=AicsCenter.objects.all(),
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    class Meta(UserCreationBaseForm.Meta):
        fields = UserCreationBaseForm.Meta.fields

    def __init__(self, *args, acting_user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.acting_user = acting_user
        if acting_user and acting_user.is_campus_admin and acting_user.center:
            campus_qs = AicsCenter.objects.filter(pk=acting_user.center_id)
            self.fields['campus'].initial = acting_user.center
        else:
            campus_qs = AicsCenter.objects.all()
        self.fields['campus'].queryset = campus_qs

    def clean_campus(self):
        campus = self.cleaned_data.get('campus') or getattr(self.acting_user, 'center', None)
        if not campus:
            raise forms.ValidationError("Campus is required.")
        return campus

    def save(self, commit=True):
        user = super().save(commit=False)
        user.role = CustomUser.Role.STUDENT
        user.center = self.cleaned_data['campus']
        user.is_staff = False
        if commit:
            user.save()
            StudentProfile.objects.create(
                user=user,
                first_name=user.first_name,
                last_name=user.last_name,
                matricule=self.cleaned_data['matricule'],
                center=user.center,
                level=self.cleaned_data['level'],
                specialization=self.cleaned_data['specialization'],
            )
        return user


class StudentSupervisorAssignmentForm(forms.Form):
    supervisor = forms.ModelChoiceField(
        queryset=SupervisorProfile.objects.select_related('user', 'center'),
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    students = forms.ModelMultipleChoiceField(
        queryset=StudentProfile.objects.select_related('user', 'center', 'assigned_supervisor__user'),
        widget=forms.SelectMultiple(attrs={'class': 'form-select', 'size': 10}),
        help_text="Select up to 15 students to assign in this batch.",
    )

    def __init__(self, *args, acting_user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.acting_user = acting_user
        if acting_user and acting_user.is_campus_admin and acting_user.center:
            supervisor_qs = SupervisorProfile.objects.filter(center=acting_user.center).select_related('user', 'center')
            student_qs = StudentProfile.objects.filter(center=acting_user.center).select_related('user', 'center', 'assigned_supervisor__user')
        else:
            supervisor_qs = SupervisorProfile.objects.select_related('user', 'center')
            student_qs = StudentProfile.objects.select_related('user', 'center', 'assigned_supervisor__user')
        self.fields['supervisor'].queryset = supervisor_qs
        self.fields['students'].queryset = student_qs.order_by('matricule')
        self.fields['supervisor'].label_from_instance = (
            lambda supervisor: f"{supervisor.user.get_full_name() or supervisor.user.username} ({supervisor.center.name})"
        )
        self.fields['students'].label_from_instance = (
            lambda student: (
                f"{student.matricule} - {student.first_name} {student.last_name} "
                f"({student.center.name})"
            )
        )

    def clean_students(self):
        students = self.cleaned_data.get('students')
        if students and len(students) > 15:
            raise forms.ValidationError("You can assign a maximum of 15 students in one action.")
        return students

    def clean(self):
        cleaned_data = super().clean()
        supervisor = cleaned_data.get('supervisor')
        students = cleaned_data.get('students')
        if supervisor and students:
            invalid_students = [student for student in students if student.center_id != supervisor.center_id]
            if invalid_students:
                self.add_error('students', "All selected students must belong to the same campus as the supervisor.")
        return cleaned_data

    def save(self):
        supervisor = self.cleaned_data['supervisor']
        students = self.cleaned_data['students']
        updated = students.update(assigned_supervisor=supervisor)
        return supervisor, updated


class ReportUploadForm(forms.ModelForm):
    upload_code = forms.CharField(
        max_length=10,
        help_text="Enter the 8-character upload code provided by your supervisor.",
        widget=forms.TextInput(attrs={'class': 'form-control', 'autocomplete': 'off'})
    )

    class Meta:
        model = Report
        fields = ['theme', 'description', 'pdf_file', 'upload_code']
        widgets = {
            'theme': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
            'pdf_file': forms.ClearableFileInput(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, student_profile=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.student_profile = student_profile
        self.otp_instance = None

    def clean_pdf_file(self):
        pdf_file = self.cleaned_data.get('pdf_file')
        if pdf_file and not pdf_file.name.lower().endswith('.pdf'):
            raise forms.ValidationError("Only PDF files are allowed.")
        return pdf_file

    def clean_upload_code(self):
        return (self.cleaned_data.get('upload_code') or '').strip().upper()

    def clean(self):
        cleaned_data = super().clean()
        upload_code = cleaned_data.get('upload_code')
        if not self.student_profile:
            raise forms.ValidationError("A logged-in student is required for uploads.")

        if Report.objects.filter(student=self.student_profile).exists():
            raise forms.ValidationError("You have already uploaded your final report.")

        if upload_code:
            try:
                self.otp_instance = OneTimeCode.objects.get(
                    student=self.student_profile,
                    code=upload_code,
                    is_used=False,
                )
            except OneTimeCode.DoesNotExist:
                self.add_error('upload_code', "Invalid or already used upload code.")
        return cleaned_data


class GradeReportForm(forms.ModelForm):
    class Meta:
        model = Report
        fields = ['grade', 'supervisor_feedback', 'status']
        widgets = {
            'grade': forms.NumberInput(attrs={'class': 'form-control', 'min': 0, 'max': 20, 'step': '0.01'}),
            'supervisor_feedback': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'status': forms.Select(attrs={'class': 'form-select'}),
        }

    def save(self, commit=True):
        report = super().save(commit=False)
        if report.grade is not None:
            report.graded_at = timezone.now()
        if commit:
            report.save()
        return report
