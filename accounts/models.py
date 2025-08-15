from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone
import uuid

class User(AbstractUser):
    ROLES = (
        ('admin', 'Administrator'),
        ('moderator', 'Moderator'),
        ('speaker', 'Speaker'),
        ('attendee', 'Attendee'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    role = models.CharField(max_length=20, choices=ROLES, default='attendee')
    avatar = models.ImageField(upload_to='avatars/', null=True, blank=True)
    bio = models.TextField(max_length=500, blank=True)
    is_online = models.BooleanField(default=False)
    last_seen = models.DateTimeField(auto_now=True)
    notification_settings = models.JSONField(default=dict)
    
    def __str__(self):
        return f"{self.username} ({self.get_role_display()})"