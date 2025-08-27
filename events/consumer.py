from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth import get_user_model
from django.utils import timezone
import json
from .models import Event, EventAgenda

User = get_user_model()

class EventConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.event_slug = self.scope['url_route']['kwargs']['event_slug']
        self.event_group_name = f'event_{self.event_slug}'
        
        # Join event group
        await self.channel_layer.group_add(
            self.event_group_name,
            self.channel_name
        )
        
        await self.accept()
        
        # Send initial event data
        event_data = await self.get_event_data()
        await self.send(text_data=json.dumps({
            'type': 'event_data',
            'data': event_data
        }))

    async def disconnect(self, close_code):
        # Leave event group
        await self.channel_layer.group_discard(
            self.event_group_name,
            self.channel_name
        )

    async def receive(self, text_data):
        text_data_json = json.loads(text_data)
        message_type = text_data_json['type']
        
        if message_type == 'join_event':
            await self.join_event()
        elif message_type == 'leave_event':
            await self.leave_event()
        elif message_type == 'request_update':
            event_data = await self.get_event_data()
            await self.send(text_data=json.dumps({
                'type': 'event_data',
                'data': event_data
            }))

    @database_sync_to_async
    def get_event_data(self):
        try:
            event = Event.objects.get(slug=self.event_slug)
            attendees_data = []
            
            for attendee in event.attendees.all()[:20]:  # Limit for performance
                attendees_data.append({
                    'id': attendee.id,
                    'username': attendee.username,
                    'avatar': attendee.avatar.url if hasattr(attendee, 'avatar') and attendee.avatar else f"https://ui-avatars.com/api/?name={attendee.username}&background=random&size=32",
                    'is_online': getattr(attendee, 'is_online', False),
                    'last_seen': str(attendee.last_login) if attendee.last_login else None
                })
            
            speakers_data = []
            for speaker in event.speakers.all():
                speakers_data.append({
                    'id': speaker.id,
                    'username': speaker.username,
                    'avatar': speaker.avatar.url if hasattr(speaker, 'avatar') and speaker.avatar else f"https://ui-avatars.com/api/?name={speaker.username}&background=random&size=32"
                })
            
            agenda_data = []
            for item in event.agenda_items.all():
                agenda_data.append({
                    'id': item.id,
                    'title': item.title,
                    'description': item.description,
                    'start_time': item.start_time.isoformat(),
                    'end_time': item.end_time.isoformat(),
                    'speaker': {
                        'username': item.speaker.username,
                        'avatar': item.speaker.avatar.url if hasattr(item.speaker, 'avatar') and item.speaker.avatar else f"https://ui-avatars.com/api/?name={item.speaker.username}&background=random&size=32"
                    } if item.speaker else None
                })
            
            return {
                'id': str(event.id),
                'title': event.title,
                'description': event.description,
                'event_type': event.event_type,
                'start_time': event.start_time.isoformat(),
                'end_time': event.end_time.isoformat(),
                'attendees_count': event.attendees.count(),
                'max_attendees': event.max_attendees,
                'speakers_count': event.speakers.count(),
                'attendees': attendees_data,
                'speakers': speakers_data,
                'agenda': agenda_data,
                'is_live': timezone.now() >= event.start_time and timezone.now() <= event.end_time,
                'time_until_start': str(event.start_time - timezone.now()) if event.start_time > timezone.now() else None,
                'created_by': event.created_by.username
            }
        except Event.DoesNotExist:
            return None

    @database_sync_to_async
    def join_event(self):
        if self.scope['user'].is_authenticated:
            event = Event.objects.get(slug=self.event_slug)
            if self.scope['user'] not in event.attendees.all():
                event.attendees.add(self.scope['user'])
                return True
        return False

    @database_sync_to_async
    def leave_event(self):
        if self.scope['user'].is_authenticated:
            event = Event.objects.get(slug=self.event_slug)
            if self.scope['user'] in event.attendees.all():
                event.attendees.remove(self.scope['user'])
                return True
        return False

    # Event update handlers
    async def event_updated(self, event):
        """Handle event updates"""
        await self.send(text_data=json.dumps({
            'type': 'event_updated',
            'data': event['data']
        }))

    async def attendee_joined(self, event):
        """Handle new attendee joining"""
        await self.send(text_data=json.dumps({
            'type': 'attendee_joined',
            'data': event['data']
        }))

    async def attendee_left(self, event):
        """Handle attendee leaving"""
        await self.send(text_data=json.dumps({
            'type': 'attendee_left',
            'data': event['data']
        }))

    async def agenda_updated(self, event):
        """Handle agenda updates"""
        await self.send(text_data=json.dumps({
            'type': 'agenda_updated',
            'data': event['data']
        }))


class EventListConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.group_name = 'event_list'
        
        # Join event list group
        await self.channel_layer.group_add(
            self.group_name,
            self.channel_name
        )
        
        await self.accept()
        
        # Send initial events data
        events_data = await self.get_events_data()
        await self.send(text_data=json.dumps({
            'type': 'events_data',
            'data': events_data
        }))

    async def disconnect(self, close_code):
        # Leave event list group
        await self.channel_layer.group_discard(
            self.group_name,
            self.channel_name
        )

    async def receive(self, text_data):
        text_data_json = json.loads(text_data)
        message_type = text_data_json['type']
        
        if message_type == 'request_update':
            events_data = await self.get_events_data()
            await self.send(text_data=json.dumps({
                'type': 'events_data',
                'data': events_data
            }))
        elif message_type == 'filter_events':
            filter_type = text_data_json.get('filter_type', 'all')
            events_data = await self.get_filtered_events_data(filter_type)
            await self.send(text_data=json.dumps({
                'type': 'filtered_events',
                'data': events_data,
                'filter': filter_type
            }))

    @database_sync_to_async
    def get_events_data(self):
        events = Event.objects.filter(start_time__gte=timezone.now()).order_by('start_time')[:50]
        events_data = []
        
        for event in events:
            events_data.append({
                'id': str(event.id),
                'title': event.title,
                'slug': event.slug,
                'description': event.description,
                'event_type': event.event_type,
                'start_time': event.start_time.isoformat(),
                'end_time': event.end_time.isoformat(),
                'attendees_count': event.attendees.count(),
                'max_attendees': event.max_attendees,
                'speakers_count': event.speakers.count(),
                'is_today': event.start_time.date() == timezone.now().date(),
                'time_until_start': str(event.start_time - timezone.now()) if event.start_time > timezone.now() else None,
                'created_by': event.created_by.username,
                'attendees_preview': [
                    {
                        'username': attendee.username,
                        'avatar': attendee.avatar.url if hasattr(attendee, 'avatar') and attendee.avatar else f"https://ui-avatars.com/api/?name={attendee.username}&background=random&size=32"
                    }
                    for attendee in event.attendees.all()[:4]
                ]
            })
        
        return events_data

    @database_sync_to_async
    def get_filtered_events_data(self, filter_type):
        query = Event.objects.filter(start_time__gte=timezone.now()).order_by('start_time')
        
        if filter_type != 'all':
            query = query.filter(event_type=filter_type)
        
        events = query[:50]
        events_data = []
        
        for event in events:
            events_data.append({
                'id': str(event.id),
                'title': event.title,
                'slug': event.slug,
                'description': event.description,
                'event_type': event.event_type,
                'start_time': event.start_time.isoformat(),
                'end_time': event.end_time.isoformat(),
                'attendees_count': event.attendees.count(),
                'max_attendees': event.max_attendees,
                'speakers_count': event.speakers.count(),
                'is_today': event.start_time.date() == timezone.now().date(),
                'time_until_start': str(event.start_time - timezone.now()) if event.start_time > timezone.now() else None,
                'created_by': event.created_by.username,
                'attendees_preview': [
                    {
                        'username': attendee.username,
                        'avatar': attendee.avatar.url if hasattr(attendee, 'avatar') and attendee.avatar else f"https://ui-avatars.com/api/?name={attendee.username}&background=random&size=32"
                    }
                    for attendee in event.attendees.all()[:4]
                ]
            })
        
        return events_data

    # Event handlers
    async def event_created(self, event):
        """Handle new event creation"""
        await self.send(text_data=json.dumps({
            'type': 'event_created',
            'data': event['data']
        }))

    async def event_updated(self, event):
        """Handle event updates"""
        await self.send(text_data=json.dumps({
            'type': 'event_updated',
            'data': event['data']
        }))

    async def event_deleted(self, event):
        """Handle event deletion"""
        await self.send(text_data=json.dumps({
            'type': 'event_deleted',
            'data': event['data']
        }))

    async def attendee_count_changed(self, event):
        """Handle attendee count changes"""
        await self.send(text_data=json.dumps({
            'type': 'attendee_count_changed',
            'data': event['data']
        }))