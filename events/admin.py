from django.contrib import admin
from .models import Event, EventAgenda

@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ('title', 'event_type', 'start_time', 'created_by')
    list_filter = ('event_type', 'start_time', 'is_public')
    prepopulated_fields = {'slug': ('title',)}
    filter_horizontal = ('speakers', 'attendees')

@admin.register(EventAgenda)
class EventAgendaAdmin(admin.ModelAdmin):
    list_display = ('title', 'event', 'start_time', 'speaker')
    list_filter = ('event', 'start_time')