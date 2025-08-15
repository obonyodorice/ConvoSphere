from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User

@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = ('username', 'email', 'role', 'is_online', 'last_seen')
    list_filter = ('role', 'is_online', 'is_staff')
    fieldsets = UserAdmin.fieldsets + (
        ('Profile', {'fields': ('role', 'avatar', 'bio', 'is_online', 'notification_settings')}),
    )
