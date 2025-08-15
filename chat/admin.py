from django.contrib import admin
from .models import ChatRoom, Message, TypingIndicator

@admin.register(ChatRoom)
class ChatRoomAdmin(admin.ModelAdmin):
    list_display = ('name', 'room_type', 'is_active', 'created_at')
    list_filter = ('room_type', 'is_active')
    filter_horizontal = ('members', 'admins')

@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ('room', 'sender', 'message_type', 'created_at', 'is_edited')
    list_filter = ('message_type', 'created_at', 'is_edited')
    readonly_fields = ('created_at', 'updated_at')