#admin.py
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User, Grievance

admin.site.register(User, UserAdmin)
admin.site.register(Grievance)
