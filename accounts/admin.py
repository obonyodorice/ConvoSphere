from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from .models import User, UserActivity, UserConnection

@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = [
        'email', 'username', 'display_name', 'role', 'is_online_status',
        'profile_completed', 'reputation_score', 'date_joined'
    ]
    
    list_filter = [
        'role', 'is_online', 'profile_completed', 'email_verified',
        'is_staff', 'is_active', 'date_joined'
    ]
    
    search_fields = ['email', 'username', 'first_name', 'last_name']
    
    ordering = ['-date_joined']

    fieldsets = (
        ('Authentication', {
            'fields': ('username', 'email', 'password')
        }),
        ('Personal Info', {
            'fields': ('first_name', 'last_name', 'avatar', 'bio', 'location', 'website')
        }),
        ('Community Settings', {
            'fields': ('role', 'reputation_score', 'notification_settings'),
            'classes': ('collapse',)
        }),
        ('Status', {
            'fields': (
                'is_online', 'last_seen', 'profile_completed', 
                'email_verified', 'is_active', 'is_staff', 'is_superuser'
            )
        }),
        ('Statistics', {
            'fields': ('total_posts', 'total_events_attended'),
            'classes': ('collapse',)
        }),
        ('Important dates', {
            'fields': ('last_login', 'date_joined')
        }),
    )

    add_fieldsets = (
        ('Required Information', {
            'classes': ('wide',),
            'fields': ('username', 'email', 'first_name', 'last_name', 'password1', 'password2'),
        }),
        ('Optional Information', {
            'classes': ('wide', 'collapse'),
            'fields': ('role', 'bio', 'location'),
        }),
    )
    
    readonly_fields = ['id', 'date_joined', 'last_login', 'last_seen']

    def display_name(self, obj):
        return obj.display_name
    display_name.short_description = 'Display Name'
    
    def is_online_status(self, obj):
        if obj.is_online:
            return format_html(
                '<span style="color: green;">●</span> Online'
            )
        return format_html(
            '<span style="color: gray;">●</span> Offline'
        )
    is_online_status.short_description = 'Status'

    actions = ['mark_as_verified', 'mark_as_unverified', 'reset_reputation']
    
    def mark_as_verified(self, request, queryset):
        updated = queryset.update(email_verified=True)
        self.message_user(request, f'{updated} users marked as verified.')
    mark_as_verified.short_description = "Mark selected users as verified"
    
    def mark_as_unverified(self, request, queryset):
        updated = queryset.update(email_verified=False)
        self.message_user(request, f'{updated} users marked as unverified.')
    mark_as_unverified.short_description = "Mark selected users as unverified"
    
    def reset_reputation(self, request, queryset):
        updated = queryset.update(reputation_score=0)
        self.message_user(request, f'Reset reputation for {updated} users.')
    reset_reputation.short_description = "Reset reputation score"


@admin.register(UserActivity)
class UserActivityAdmin(admin.ModelAdmin):
    """Admin interface for user activities"""
    
    list_display = [
        'user', 'activity_type', 'description_short', 'timestamp', 'ip_address'
    ]
    
    list_filter = ['activity_type', 'timestamp']
    
    search_fields = ['user__email', 'user__username', 'description']
    
    ordering = ['-timestamp']
    
    readonly_fields = ['user', 'activity_type', 'timestamp', 'ip_address', 'user_agent']

    def description_short(self, obj):
        if len(obj.description) > 50:
            return obj.description[:50] + '...'
        return obj.description
    description_short.short_description = 'Description'
    def has_add_permission(self, request):
        return False
    def has_change_permission(self, request, obj=None):
        return False


@admin.register(UserConnection)
class UserConnectionAdmin(admin.ModelAdmin):
    
    list_display = ['follower', 'following', 'created_at']
    
    list_filter = ['created_at']
    
    search_fields = [
        'follower__username', 'follower__email',
        'following__username', 'following__email'
    ]
    
    ordering = ['-created_at']
    actions = ['remove_connections']
    
    def remove_connections(self, request, queryset):
        count = queryset.count()
        queryset.delete()
        self.message_user(request, f'Removed {count} connections.')
    remove_connections.short_description = "Remove selected connections"

admin.site.site_header = "Community Platform Admin"
admin.site.site_title = "Community Admin"
admin.site.index_title = "Welcome to Community Platform Administration"
admin.site.register(admin.models.LogEntry, admin.ModelAdmin)