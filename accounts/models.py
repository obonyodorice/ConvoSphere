from django.contrib.auth.models import AbstractUser
from django.db import models
from django.urls import reverse
import uuid

class User(AbstractUser):

    USER_ROLES = [
        ('member', 'Member'),
        ('moderator', 'Moderator'),
        ('speaker', 'Speaker'),
        ('admin', 'Admin'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(unique=True)
    avatar = models.ImageField(upload_to='avatars/', null=True, blank=True)
    bio = models.TextField(max_length=500, blank=True)
    location = models.CharField(max_length=100, blank=True)
    website = models.URLField(blank=True)
 
    role = models.CharField(max_length=20, choices=USER_ROLES, default='member')
    is_online = models.BooleanField(default=False)
    last_seen = models.DateTimeField(auto_now=True)

    notification_settings = models.JSONField(default=dict, blank=True)

    profile_completed = models.BooleanField(default=False)
    email_verified = models.BooleanField(default=False)

    reputation_score = models.IntegerField(default=0)
    total_posts = models.IntegerField(default=0)
    total_events_attended = models.IntegerField(default=0)
    
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username', 'first_name', 'last_name']
    
    class Meta:
        db_table = 'accounts_user'
        ordering = ['-date_joined']
    
    def __str__(self):
        return f"{self.get_full_name() or self.username} ({self.email})"
    
    def get_absolute_url(self):
        return reverse('accounts:profile', kwargs={'pk': self.pk})
    
    @property
    def display_name(self):

        return self.get_full_name() or self.username
    
    def get_default_notification_settings(self):
     
        return {
            'email_notifications': True,
            'chat_mentions': True,
            'event_reminders': True,
            'forum_replies': True,
            'new_followers': True,
            'system_announcements': True,
        }
    
    def save(self, *args, **kwargs):
      
        if not self.notification_settings:
            self.notification_settings = self.get_default_notification_settings()

        self.profile_completed = bool(
            self.first_name and self.last_name and self.bio and self.avatar
        )
        
        super().save(*args, **kwargs)


class UserActivity(models.Model):
 
    ACTIVITY_TYPES = [
        ('login', 'Login'),
        ('logout', 'Logout'),
        ('chat_message', 'Chat Message'),
        ('forum_post', 'Forum Post'),
        ('event_join', 'Event Join'),
        ('profile_update', 'Profile Update'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='activities')
    activity_type = models.CharField(max_length=20, choices=ACTIVITY_TYPES)
    description = models.TextField(blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-timestamp']
        verbose_name_plural = 'User Activities'
    
    def __str__(self):
        return f"{self.user.username} - {self.get_activity_type_display()}"


class UserConnection(models.Model):
   
    follower = models.ForeignKey(User, on_delete=models.CASCADE, related_name='following')
    following = models.ForeignKey(User, on_delete=models.CASCADE, related_name='followers')
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ('follower', 'following')
    
    def __str__(self):
        return f"{self.follower.username} follows {self.following.username}"