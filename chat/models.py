# chat/models.py
from django.db import models
from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.utils import timezone
from datetime import timedelta
import uuid
from django.db.models.signals import post_save
from django.dispatch import receiver

class ChatRoom(models.Model):
    ROOM_TYPES = (
        ('forum', 'Forum Chat'),
        ('event', 'Event Chat'),
        ('private', 'Private Chat'),
        ('group', 'Group Chat'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100)
    room_type = models.CharField(max_length=20, choices=ROOM_TYPES)
    description = models.TextField(blank=True)
    
    # Generic foreign key for linking to forums/events
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE, null=True, blank=True)
    object_id = models.UUIDField(null=True, blank=True)
    linked_object = GenericForeignKey('content_type', 'object_id')
    
    members = models.ManyToManyField(settings.AUTH_USER_MODEL, related_name='chat_rooms')
    admins = models.ManyToManyField(settings.AUTH_USER_MODEL, related_name='admin_chat_rooms', blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Real-time features
    last_activity = models.DateTimeField(auto_now=True)
    message_count = models.PositiveIntegerField(default=0)
    
    class Meta:
        indexes = [
            models.Index(fields=['last_activity']),
            models.Index(fields=['is_active', 'room_type']), 
        ]

    
    def __str__(self):
        return f"{self.user.username} activity"
    
    @property
    def is_recently_active(self):
        """Check if user was active in the last 10 minutes"""
        threshold = timezone.now() - timedelta(minutes=10)
        return self.last_activity >= threshold
    
    def set_online_status(self, is_online, current_room=None):
        """Update online status and current room"""
        self.is_online = is_online
        self.last_activity = timezone.now()
        
        if current_room:
            self.current_room = current_room
        elif not is_online:
            self.current_room = None
            self.last_seen = timezone.now()
        
        self.save()


class ChatEvent(models.Model):
    """Log important chat events for real-time notifications"""
    EVENT_TYPES = (
        ('user_joined', 'User Joined'),
        ('user_left', 'User Left'),
        ('message_sent', 'Message Sent'),
        ('room_created', 'Room Created'),
        ('room_updated', 'Room Updated'),
        ('user_promoted', 'User Promoted'),
        ('user_demoted', 'User Demoted'),
        ('message_deleted', 'Message Deleted'),
        ('message_edited', 'Message Edited'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    event_type = models.CharField(max_length=20, choices=EVENT_TYPES)
    room = models.ForeignKey(ChatRoom, on_delete=models.CASCADE, related_name='events')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    target_user = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        null=True, 
        blank=True,
        related_name='targeted_events'
    )
    message = models.ForeignKey(Message, on_delete=models.CASCADE, null=True, blank=True)
    
    # Event data
    event_data = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['room', '-created_at']),
            models.Index(fields=['event_type', '-created_at']),
        ]
    
    def __str__(self):
        return f"{self.get_event_type_display()} in {self.room.name} by {self.user.username}"

@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_user_activity_tracker(sender, instance, created, **kwargs):
    """Create activity tracker for new users"""
    if created:
        UserActivity.objects.create(user=instance)

# Custom managers for optimized queries
class ChatRoomManager(models.Manager):
    def with_unread_counts(self, user):
        """Get rooms with unread message counts for a user"""
        return self.get_queryset().prefetch_related('messages', 'members').annotate(
            unread_count=models.Count(
                'messages',
                filter=~models.Q(messages__read_by=user) & ~models.Q(messages__sender=user)
            )
        )
    
    def with_last_messages(self):
        """Get rooms with their last messages"""
        return self.get_queryset().prefetch_related(
            models.Prefetch(
                'messages',
                queryset=Message.objects.select_related('sender').order_by('-created_at')[:1],
                to_attr='latest_messages'
            )
        )
    
    def for_user(self, user):
        """Get rooms that the user is a member of"""
        return self.get_queryset().filter(members=user, is_active=True)


class MessageManager(models.Manager):
    def unread_for_user(self, user):
        """Get unread messages for a user"""
        return self.get_queryset().exclude(read_by=user).exclude(sender=user)
    
    def in_room_since(self, room, since_time):
        """Get messages in a room since a specific time"""
        return self.get_queryset().filter(room=room, created_at__gte=since_time)


# Update the models to use custom managers
ChatRoom.objects = ChatRoomManager()
Message.objects = MessageManager()

# Utility functions for real-time features
class RealTimeUtils:
    @staticmethod
    def get_online_users(threshold_minutes=10):
        """Get users who have been active within the threshold"""
        threshold = timezone.now() - timedelta(minutes=threshold_minutes)
        return settings.AUTH_USER_MODEL.objects.filter(
            activity_tracker__last_activity__gte=threshold
        ).select_related('activity_tracker')
    
    @staticmethod
    def get_room_online_count(room, threshold_minutes=10):
        """Get count of online users in a specific room"""
        threshold = timezone.now() - timedelta(minutes=threshold_minutes)
        return room.members.filter(
            activity_tracker__last_activity__gte=threshold
        ).count()
    
    @staticmethod
    def get_user_unread_counts(user):
        """Get unread message counts for all user's rooms"""
        memberships = RoomMembership.objects.filter(user=user).select_related('room')
        return {
            membership.room.id: membership.unread_count 
            for membership in memberships
        }
    
    @staticmethod
    def get_recent_activities(limit=10, hours=24):
        """Get recent chat activities"""
        threshold = timezone.now() - timedelta(hours=hours)
        return ChatEvent.objects.filter(
            created_at__gte=threshold
        ).select_related('user', 'room', 'message')[:limit]
    
    @staticmethod
    def cleanup_old_data():
        """Clean up old typing indicators and other temporary data"""
        # Remove old typing indicators
        TypingIndicator.cleanup_old_indicators()
        
        # Remove old chat events (keep last 30 days)
        threshold = timezone.now() - timedelta(days=30)
        ChatEvent.objects.filter(created_at__lt=threshold).delete()
    
    @staticmethod
    def update_user_activity(user, room=None):
        """Update user's last activity"""
        activity, created = UserActivity.objects.get_or_create(user=user)
        activity.set_online_status(True, room)
        ordering = ['-last_activity']
    
    def __str__(self):
        return f"{self.name} ({self.get_room_type_display()})"
    
    @property
    def online_members_count(self):
        """Get count of currently online members"""
        threshold = timezone.now() - timedelta(minutes=10)
        return self.members.filter(last_activity__gte=threshold).count()
    
    @property
    def last_message(self):
        """Get the most recent message in this room"""
        return self.messages.first()
    
    def get_unread_count_for_user(self, user):
        """Get unread message count for a specific user"""
        return self.messages.exclude(read_by=user).exclude(sender=user).count()
    
    def get_other_user(self, current_user):
        """For private chats, get the other user"""
        if self.room_type == 'private':
            return self.members.exclude(id=current_user.id).first()
        return None
    
    def increment_message_count(self):
        """Increment message count and update last activity"""
        self.message_count += 1
        self.last_activity = timezone.now()
        self.save(update_fields=['message_count', 'last_activity'])


class Message(models.Model):
    MESSAGE_TYPES = (
        ('text', 'Text'),
        ('file', 'File'),
        ('image', 'Image'),
        ('system', 'System'),
        ('emoji', 'Emoji'),
        ('sticker', 'Sticker'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    room = models.ForeignKey(ChatRoom, on_delete=models.CASCADE, related_name='messages')
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    message_type = models.CharField(max_length=20, choices=MESSAGE_TYPES, default='text')
    content = models.TextField()
    file_attachment = models.FileField(upload_to='chat_files/', null=True, blank=True)
    parent_message = models.ForeignKey('self', null=True, blank=True, on_delete=models.CASCADE, related_name='replies')
    
    # Message status tracking
    delivered_to = models.ManyToManyField(
        settings.AUTH_USER_MODEL, 
        related_name='delivered_messages', 
        blank=True
    )
    read_by = models.ManyToManyField(
        settings.AUTH_USER_MODEL, 
        related_name='read_messages', 
        blank=True
    )
    
    # Real-time features
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_edited = models.BooleanField(default=False)
    edit_count = models.PositiveIntegerField(default=0)
    
    # Reactions and engagement
    reaction_count = models.PositiveIntegerField(default=0)
    reply_count = models.PositiveIntegerField(default=0)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['room', '-created_at']),
            models.Index(fields=['sender', '-created_at']),
        ]
    
    def __str__(self):
        return f"{self.sender.username}: {self.content[:50]}..."
    
    def save(self, *args, **kwargs):
        is_new = self.pk is None
        super().save(*args, **kwargs)
        
        # Update room message count and last activity
        if is_new:
            self.room.increment_message_count()
    
    @property
    def is_reply(self):
        return self.parent_message is not None
    
    def mark_as_read(self, user):
        """Mark message as read by user"""
        self.read_by.add(user)
    
    def mark_as_delivered(self, user):
        """Mark message as delivered to user"""
        self.delivered_to.add(user)


class MessageReaction(models.Model):
    """Emoji reactions to messages"""
    message = models.ForeignKey(Message, on_delete=models.CASCADE, related_name='reactions')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    emoji = models.CharField(max_length=10)  # Unicode emoji
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ('message', 'user', 'emoji')
        indexes = [
            models.Index(fields=['message', 'emoji']),
        ]
    
    def __str__(self):
        return f"{self.user.username} reacted {self.emoji} to {self.message.id}"


class TypingIndicator(models.Model):
    """Track who is currently typing in each room"""
    room = models.ForeignKey(ChatRoom, on_delete=models.CASCADE, related_name='typing_users')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    started_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ('room', 'user')
        indexes = [
            models.Index(fields=['room', 'started_at']),
        ]
    
    def __str__(self):
        return f"{self.user.username} typing in {self.room.name}"
    
    @classmethod
    def cleanup_old_indicators(cls, minutes=2):
        """Remove typing indicators older than specified minutes"""
        threshold = timezone.now() - timedelta(minutes=minutes)
        cls.objects.filter(started_at__lt=threshold).delete()


class RoomMembership(models.Model):
    """Extended membership information with real-time features"""
    room = models.ForeignKey(ChatRoom, on_delete=models.CASCADE)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    joined_at = models.DateTimeField(auto_now_add=True)
    last_read_message = models.ForeignKey(
        Message, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='last_read_by'
    )
    notification_settings = models.JSONField(default=dict, blank=True)
    is_muted = models.BooleanField(default=False)
    is_pinned = models.BooleanField(default=False)
    
    # Activity tracking
    message_count = models.PositiveIntegerField(default=0)
    last_activity = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ('room', 'user')
        indexes = [
            models.Index(fields=['user', 'is_pinned', '-last_activity']),
        ]
    
    def __str__(self):
        return f"{self.user.username} in {self.room.name}"
    
    @property
    def unread_count(self):
        """Get unread message count for this membership"""
        if not self.last_read_message:
            return self.room.messages.exclude(sender=self.user).count()
        
        return self.room.messages.filter(
            created_at__gt=self.last_read_message.created_at
        ).exclude(sender=self.user).count()
    
    def mark_all_read(self):
        """Mark all messages as read up to the latest message"""
        latest_message = self.room.messages.first()
        if latest_message:
            self.last_read_message = latest_message
            self.save(update_fields=['last_read_message'])


class UserActivity(models.Model):
    """Track user activity for real-time features"""
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name='activity_tracker'
    )
    last_activity = models.DateTimeField(auto_now=True)
    last_seen = models.DateTimeField(auto_now=True)
    current_room = models.ForeignKey(
        ChatRoom, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='current_users'
    )
    
    # Status tracking
    is_online = models.BooleanField(default=False)
    status_message = models.CharField(max_length=100, blank=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['is_online']),
            models.Index(fields=['last_activity']),
        ]
        ordering = ['-last_activity']

    def __str__(self):
        return f"{self.user} - {'Online' if self.is_online else 'Offline'}"