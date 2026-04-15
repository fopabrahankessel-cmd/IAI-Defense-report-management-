from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import AicsCenter, CustomUser, OneTimeCode, Report, StudentProfile, SupervisorProfile


@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    list_display = ('username', 'email', 'first_name', 'last_name', 'role', 'center', 'is_staff', 'is_superuser')
    list_filter = ('role', 'center', 'is_staff', 'is_superuser')
    fieldsets = UserAdmin.fieldsets + (
        ('Campus Access', {'fields': ('role', 'center')}),
    )


@admin.register(StudentProfile)
class StudentProfileAdmin(admin.ModelAdmin):
    list_display = ('matricule', 'first_name', 'last_name', 'center', 'level', 'specialization', 'assigned_supervisor')
    list_filter = ('center', 'level', 'specialization')
    search_fields = ('matricule', 'first_name', 'last_name', 'user__email')
    autocomplete_fields = ('user', 'assigned_supervisor')

    def get_queryset(self, request):
        qs = super().get_queryset(request).select_related('center', 'user', 'assigned_supervisor__user')
        if request.user.is_superuser:
            return qs
        if request.user.role == CustomUser.Role.ADMIN and request.user.center:
            return qs.filter(center=request.user.center)
        return qs.none()

    def save_model(self, request, obj, form, change):
        if request.user.role == CustomUser.Role.ADMIN and request.user.center and not request.user.is_superuser:
            obj.center = request.user.center
        super().save_model(request, obj, form, change)


@admin.register(SupervisorProfile)
class SupervisorProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'center', 'student_count')
    list_filter = ('center',)
    search_fields = ('user__username', 'user__email', 'user__first_name', 'user__last_name')
    autocomplete_fields = ('user',)

    def get_queryset(self, request):
        qs = super().get_queryset(request).select_related('user', 'center')
        if request.user.is_superuser:
            return qs
        if request.user.role == CustomUser.Role.ADMIN and request.user.center:
            return qs.filter(center=request.user.center)
        return qs.none()

    @admin.display(description="Students")
    def student_count(self, obj):
        return obj.supervised_students.count()


@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    list_display = ('theme', 'student', 'promotion_year', 'status', 'grade', 'graded_at')
    list_filter = ('status', 'promotion_year', 'student__center', 'student__specialization')
    search_fields = ('theme', 'student__matricule', 'student__user__email')
    autocomplete_fields = ('student',)


@admin.register(OneTimeCode)
class OneTimeCodeAdmin(admin.ModelAdmin):
    list_display = ('student', 'supervisor', 'code', 'is_used', 'created_at')
    list_filter = ('is_used', 'student__center')
    search_fields = ('student__matricule', 'code', 'supervisor__user__email')
    autocomplete_fields = ('student', 'supervisor')


admin.site.register(AicsCenter)
