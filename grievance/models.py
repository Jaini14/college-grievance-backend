# models.py
from django.db import models
from django.contrib.auth.models import AbstractUser
from django.conf import settings

# ✅ CUSTOM USER
class User(AbstractUser):
    ROLE_CHOICES = (
        ('STUDENT', 'Student'),
        ('FACULTY', 'Faculty'),
        ('ADMIN', 'Admin'),
        ('STAFF', 'Staff')
    )

    def save(self, *args, **kwargs):
        if self.is_superuser:
          self.role = "ADMIN"
        super().save(*args, **kwargs)

    full_name = models.CharField(max_length=255)
    phone_number = models.CharField(max_length=15)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    department = models.CharField(max_length=100, null=True, blank=True)

    enrollment_no = models.CharField(max_length=50, null=True, blank=True)
    specialization = models.CharField(max_length=100, null=True, blank=True)
    staff_function = models.CharField(max_length=100,blank=True,null=True)
   
    def __str__(self):
        return self.email

# ✅ GRIEVANCE MODEL
class Grievance(models.Model):
    STATUS_CHOICES = (
        ('NEW', 'New'),
        ('ASSIGNED', 'Assigned'),
        ('IN_PROGRESS', 'In Progress'),
        ('RESOLVED', 'Resolved'),
    )

    grievance_id = models.AutoField(primary_key=True)
    subject = models.CharField(max_length=255)
    description = models.TextField()
    category = models.CharField(max_length=100)

    department = models.CharField(max_length=100)
    submitted_by = models.ForeignKey(User, on_delete=models.CASCADE)

    assigned_to = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned'
    )

    # ✅ ADD THIS
    assigned_message = models.TextField(null=True, blank=True)

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='NEW')
    faculty_remark = models.TextField(null=True, blank=True)

    date_filed = models.DateTimeField(auto_now_add=True)

     # ✅ ADD THIS
    image = models.ImageField(
        upload_to='grievance_images/',
        null=True,
        blank=True
    )

    date_filed = models.DateTimeField(
        auto_now_add=True
    )
    
    resolution_image = models.ImageField(
    upload_to="resolution_proofs/",
    blank=True,
    null=True
    )
    
    def __str__(self):
        return self.subject

# ✅ CHATBOT HISTORY MODEL
class ChatMessage(models.Model):
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE
    )

    question = models.TextField()

    answer = models.TextField()

    created_at = models.DateTimeField(
        auto_now_add=True
    )

class StaffExpertise(models.Model):

    staff = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="expertise"
    )

    keyword = models.CharField(
        max_length=100
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

class DepartmentMeeting(models.Model):
    MODE_CHOICES = [
        ("ONLINE", "Online"),
        ("OFFLINE", "Offline"),
    ]

    title = models.CharField(max_length=200)
    description = models.TextField()
    department = models.CharField(max_length=100)

    meeting_type = models.CharField(
        max_length=10,
        choices=MODE_CHOICES
    )

    meeting_link = models.URLField(
        blank=True,
        null=True
    )

    meeting_location = models.CharField(
        max_length=255,
        blank=True,
        null=True
    )

    meeting_datetime = models.DateTimeField()

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

class Notification(models.Model):
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE
    )

    message = models.TextField()

    is_read = models.BooleanField(
        default=False
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    def __str__(self):
        return self.message

import random
from django.utils import timezone
from datetime import timedelta


class EmailOTP(models.Model):
    email = models.EmailField(unique=True)

    otp = models.CharField(
        max_length=6
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    def is_valid(self):
        return timezone.now() < (
            self.created_at + timedelta(minutes=5)
        )

    def __str__(self):
        return self.email
    

    def __str__(self):
        return self.title

