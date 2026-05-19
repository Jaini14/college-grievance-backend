# from rest_framework_simplejwt.views import TokenObtainPairView
from django.urls import path
from .views import *

urlpatterns = [
    # AUTH
    path('register/', register),
    path('login/', login),
    path('chatbot/', chatbot_response),

    # PROFILE
    path('profile/', profile),
    path('profile/update/', update_profile),
    
    # GRIEVANCE
    path('grievance/create/', create_grievance),
    path('grievance/update-status/', update_status),
    path('grievance/assign/', assign_grievance),         # ✅ NEW
    path('grievance-report/<int:id>/', grievance_report),# ✅ NEW

    # DASHBOARDS
    path('student/dashboard/', student_dashboard),
    path('faculty/dashboard/', faculty_dashboard),
    path('admin/dashboard/', admin_dashboard),           # ✅ NEW  
    path('public-analytics/', public_analytics),
    path('analytics/', admin_analytics),     
    path('create-meeting/', create_meeting),   
    path("faculty/notifications/",faculty_notifications),
    path("send-otp/",send_registration_otp),
    path("verify-register/",verify_otp_and_register),
    path('faculty/notifications/delete/<int:notification_id>/', delete_notification),
    
]

