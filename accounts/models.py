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
    
    class Meta:
        indexes = [
            models.Index(fields=['is_online', 'last_seen']),
        ]   
    
    @property
    def recently_seen(self):
        """True if user was active in last 5 minutes (300 seconds)."""
        if not self.last_seen:
            return False
        return (timezone.now() - self.last_seen).total_seconds() < 300