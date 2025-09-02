from django.urls import path, include
from . import views

app_name = 'chat'

urlpatterns = [
    # Main views
    path('', views.room_list, name='room_list'),
    path('room/<uuid:room_id>/', views.chat_room, name='room'),
    
    # Room management
    path('create-room/', views.create_room, name='create_room'),
    path('join-room/<uuid:room_id>/', views.join_room, name='join_room'),
    path('leave-room/<uuid:room_id>/', views.leave_room, name='leave_room'),
    
    # Message management
    path('send-message/<uuid:room_id>/', views.send_message, name='send_message'),
    path('mark-room-read/<uuid:room_id>/', views.mark_room_read, name='mark_room_read'),
    
    # API endpoints
    path('api/rooms/', views.api_room_list, name='api_room_list'),
    path('api/create-room/', views.api_create_room, name='api_create_room'),
    # path('api/room/<uuid:room_id>/messages/', views.api_recent_messages, name='api_recent_messages'),
    
    # Debug/admin endpoints
    path('debug/room/<uuid:room_id>/', views.debug_room_state, name='debug_room_state'),
    path('admin/cleanup/', views.cleanup_chat_data, name='cleanup_chat_data'),
]