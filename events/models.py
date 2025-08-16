from django.db import models

# Create your models here.
from django.db import models
from django.conf import settings
import uuid

class Event(models.Model):
    EVENT_TYPES = (
        ('webinar', 'Webinar'),
        ('conference', 'Conference'),
        ('workshop', 'Workshop'),
        ('meetup', 'Meetup'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=200)
    slug = models.SlugField(unique=True)
    description = models.TextField()
    event_type = models.CharField(max_length=20, choices=EVENT_TYPES)
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    max_attendees = models.PositiveIntegerField(null=True, blank=True)
    is_public = models.BooleanField(default=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    speakers = models.ManyToManyField(settings.AUTH_USER_MODEL, related_name='speaking_events', blank=True)
    attendees = models.ManyToManyField(settings.AUTH_USER_MODEL, related_name='attending_events', blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return self.title

class EventAgenda(models.Model):
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='agenda_items')
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    speaker = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True)
    
    class Meta:
        ordering = ['start_time']