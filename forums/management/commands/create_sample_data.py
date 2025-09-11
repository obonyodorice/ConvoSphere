from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from forums.models import Category, Topic, Post
from events.models import Event
from chat.models import ChatRoom

User = get_user_model()

class Command(BaseCommand):
    help = 'Create sample data for the platform'
    
    def handle(self, *args, **options):
        # Create users
        admin = User.objects.create_superuser('admin', 'admin@example.com', 'admin123')
        moderator = User.objects.create_user('moderator', 'mod@example.com', 'mod123', role='moderator')
        speaker = User.objects.create_user('speaker', 'speaker@example.com', 'speaker123', role='speaker')
        
        # Create forum categories
        tech_cat = Category.objects.create(name='Technology', slug='technology')
        general_cat = Category.objects.create(name='General Discussion', slug='general')
        
        # Create sample topics and posts
        topic = Topic.objects.create(title='Welcome to our platform!', slug='welcome', 
                                   category=general_cat, author=admin)
        Post.objects.create(topic=topic, author=admin, content='Welcome everyone!')
        
        # Create sample event
        from django.utils import timezone
        from datetime import timedelta
        
        event = Event.objects.create(
            title='Tech Meetup 2025',
            slug='tech-meetup-2025',
            description='Annual technology meetup',
            event_type='meetup',
            start_time=timezone.now() + timedelta(days=7),
            end_time=timezone.now() + timedelta(days=7, hours=3),
            created_by=admin
        )
        event.speakers.add(speaker)
        
        # Create chat rooms
        ChatRoom.objects.create(name='General Chat', room_type='group')
        
        self.stdout.write(self.style.SUCCESS('Sample data created successfully!'))