from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('reports/', views.report_list, name='report_list'),
    path('report/<int:pk>/', views.report_detail, name='report_detail'),
    path('report/<int:pk>/pdf/', views.stream_report_pdf, name='stream_report_pdf'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('upload/', views.upload_report, name='upload_report'),
    path('upload/verify-code/', views.verify_upload_code, name='verify_upload_code'),
    path('api/students-for-supervisor/<int:supervisor_id>/', views.get_students_for_supervisor, name='students_for_supervisor'),
    path('login/', views.SiteLoginView.as_view(), name='login'),
    path('logout/', views.site_logout, name='logout'),
]
