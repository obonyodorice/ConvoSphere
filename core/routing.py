from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    re_path(r'ws/room-list/$', consumers.RoomListConsumer.as_asgi()),
    re_path(r'ws/chat/(?P<room_id>[0-9a-f-]+)/$', consumers.ChatRoomConsumer.as_asgi()),
]