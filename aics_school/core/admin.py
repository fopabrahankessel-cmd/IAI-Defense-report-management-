from django.contrib import admin
from .models import AicsCenter, CustomUser, StudentProfile, SupervisorProfile, Report, OneTimeCode

@admin.register(CustomUser)
class CustomUserAdmin(admin.ModelAdmin):
    list_display = ('username', 'role', 'center', 'is_staff')
    list_filter = ('role', 'center', 'is_staff')
    search_fields = ('username', 'email')

@admin.register(StudentProfile)
class StudentProfileAdmin(admin.ModelAdmin):
    list_display = ('matricule', 'first_name', 'last_name', 'center', 'level', 'specialization')
    list_filter = ('center', 'level', 'specialization')
    search_fields = ('matricule', 'first_name', 'last_name')

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        if request.user.role == CustomUser.Role.ADMIN and request.user.center:
            return qs.filter(center=request.user.center)
        return qs.none()

    def save_model(self, request, obj, form, change):
        if not request.user.is_superuser and request.user.role == CustomUser.Role.ADMIN:
            if request.user.center:
                obj.center = request.user.center
        super().save_model(request, obj, form, change)

@admin.register(SupervisorProfile)
class SupervisorProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'center')
    list_filter = ('center',)

admin.site.register(AicsCenter)
admin.site.register(Report)
admin.site.register(OneTimeCode)
