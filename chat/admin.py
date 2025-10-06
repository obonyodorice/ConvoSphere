from django.contrib import admin
from .models import ChatRoom, RoomMembership, Message, MessageReaction, TypingIndicator


class RoomMembershipInline(admin.TabularInline):
    model = RoomMembership
    extra = 0
    fields = ('user', 'role', 'is_muted', 'is_pinned')


@admin.register(ChatRoom)
class ChatRoomAdmin(admin.ModelAdmin):
    list_display = ('display_name', 'room_type', 'member_count', 'message_count', 'is_active', 'created_at')
    list_filter = ('room_type', 'is_active', 'created_at')
    search_fields = ('name', 'description', 'created_by__username')
    readonly_fields = ('id', 'created_at', 'updated_at')
    inlines = [RoomMembershipInline]
    
    def member_count(self, obj):
        return obj.members.count()
    
    def message_count(self, obj):
        return obj.messages.filter(is_deleted=False).count()


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ('short_content', 'sender', 'room', 'message_type', 'created_at')
    list_filter = ('message_type', 'is_edited', 'is_deleted', 'created_at')
    search_fields = ('content', 'sender__username', 'room__name')
    readonly_fields = ('id', 'created_at', 'updated_at')
    date_hierarchy = 'created_at'
    
    def short_content(self, obj):
        return obj.content[:50] + '...' if len(obj.content) > 50 else obj.content


@admin.register(MessageReaction)
class MessageReactionAdmin(admin.ModelAdmin):
    list_display = ('emoji', 'user', 'message_preview', 'created_at')
    list_filter = ('emoji', 'created_at')
    
    def message_preview(self, obj):
        return obj.message.content[:30]


admin.site.register(RoomMembership)
admin.site.register(TypingIndicator)