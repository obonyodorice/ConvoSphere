# chat/apps.py
from django.apps import AppConfig


class ChatConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'chat'

    def ready(self):
        """Import signal handlers when Django is ready"""
        from .models import ready
        ready()