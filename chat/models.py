from django.db import models
from django.conf import settings
from django.urls import reverse
import uuid

class ChatRoom(models.Model):
    ROOM_TYPES = [
        ('direct', 'Direct Message'),
        ('group', 'Group Chat'),
        ('event', 'Event Chat'),
        ('forum', 'Forum Discussion'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255, blank=True)
    room_type = models.CharField(max_length=20, choices=ROOM_TYPES, default='group')
    description = models.TextField(blank=True)
    avatar = models.ImageField(upload_to='chat/rooms/', null=True, blank=True)
    
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, 
                                   null=True, related_name='created_rooms')
    members = models.ManyToManyField(settings.AUTH_USER_MODEL, through='RoomMembership', 
                                     related_name='chat_rooms')
    # event = models.ForeignKey('events.Event', on_delete=models.CASCADE, 
    #                          null=True, blank=True, related_name='chat_room')
    # forum_topic = models.ForeignKey('forums.Topic', on_delete=models.CASCADE, 
    #                                null=True, blank=True, related_name='chat_room')
    
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-updated_at']
        indexes = [
            models.Index(fields=['room_type', '-updated_at']),
            models.Index(fields=['created_by', '-created_at']),
        ]
    
    def __str__(self):
        return self.name or f"{self.get_room_type_display()} - {self.id}"
    
    def get_absolute_url(self):
        return reverse('chat:room', kwargs={'room_id': self.id})
    
    @property
    def display_name(self):
        if self.name:
            return self.name
        if self.room_type == 'direct':
            return "Direct Message"
        return f"{self.get_room_type_display()}"
    
    def get_last_message(self):
        return self.messages.filter(is_deleted=False).first()
    
    def get_unread_count(self, user):
        last_read = RoomMembership.objects.filter(
            room=self, user=user
        ).first()
        
        if not last_read or not last_read.last_read_at:
            return self.messages.filter(is_deleted=False).count()
        
        return self.messages.filter(
            created_at__gt=last_read.last_read_at,
            is_deleted=False
        ).exclude(sender=user).count()


class RoomMembership(models.Model):
    ROLES = [
        ('admin', 'Admin'),
        ('moderator', 'Moderator'),
        ('member', 'Member'),
    ]
    
    room = models.ForeignKey(ChatRoom, on_delete=models.CASCADE, related_name='memberships')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, 
                            related_name='room_memberships')
    role = models.CharField(max_length=20, choices=ROLES, default='member')
    
    is_muted = models.BooleanField(default=False)
    is_pinned = models.BooleanField(default=False)
    last_read_at = models.DateTimeField(null=True, blank=True)
    joined_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ('room', 'user')
        ordering = ['-joined_at']
    
    def __str__(self):
        return f"{self.user.username} in {self.room.display_name}"


class Message(models.Model):
    MESSAGE_TYPES = [
        ('text', 'Text'),
        ('image', 'Image'),
        ('file', 'File'),
        ('system', 'System'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    room = models.ForeignKey(ChatRoom, on_delete=models.CASCADE, related_name='messages')
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, 
                              null=True, related_name='sent_messages')
    
    message_type = models.CharField(max_length=20, choices=MESSAGE_TYPES, default='text')
    content = models.TextField()

    file = models.FileField(upload_to='chat/files/%Y/%m/', null=True, blank=True)
    file_name = models.CharField(max_length=255, blank=True)
    file_size = models.IntegerField(null=True, blank=True)
   
    reply_to = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, 
                                 blank=True, related_name='replies')
   
    mentions = models.ManyToManyField(settings.AUTH_USER_MODEL, 
                                     related_name='mentioned_in', blank=True)
    
    is_edited = models.BooleanField(default=False)
    is_deleted = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['room', '-created_at']),
            models.Index(fields=['sender', '-created_at']),
        ]
    
    def __str__(self):
        return f"{self.sender.username if self.sender else 'System'}: {self.content[:50]}"
    
    def mark_as_read(self, user):
        MessageRead.objects.get_or_create(message=self, user=user)


class MessageRead(models.Model):
    message = models.ForeignKey(Message, on_delete=models.CASCADE, related_name='reads')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    read_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ('message', 'user')
        indexes = [models.Index(fields=['message', 'user'])]


class MessageReaction(models.Model):
    message = models.ForeignKey(Message, on_delete=models.CASCADE, related_name='reactions')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    emoji = models.CharField(max_length=10)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ('message', 'user', 'emoji')


class TypingIndicator(models.Model):
    room = models.ForeignKey(ChatRoom, on_delete=models.CASCADE, related_name='typing_users')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    started_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ('room', 'user')
        indexes = [models.Index(fields=['room', 'started_at'])]