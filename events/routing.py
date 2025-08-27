# events/routing.py
from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    re_path(r'ws/events/$', consumers.EventListConsumer.as_asgi()),
    re_path(r'ws/events/(?P<event_slug>\w+)/$', consumers.EventConsumer.as_asgi()),
]

# main_project/routing.py (update your existing routing.py)
from django.urls import path, include
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack

websocket_urlpatterns = [
    path('ws/events/', include('events.routing')),
    # Add other app routing here
]