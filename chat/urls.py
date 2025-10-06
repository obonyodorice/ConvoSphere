from django.urls import path
from . import views

app_name = 'chat'

urlpatterns = [
    # Main views
    path('', views.chat_home, name='home'),
    path('room/<uuid:room_id>/', views.chat_room, name='room'),
    
    # Room API
    path('api/room/create/', views.create_room, name='create_room'),
    path('api/room/<uuid:room_id>/update/', views.update_room, name='update_room'),
    path('api/room/<uuid:room_id>/members/add/', views.add_members, name='add_members'),
    path('api/room/<uuid:room_id>/leave/', views.leave_room, name='leave_room'),
    path('api/room/<uuid:room_id>/pin/', views.toggle_pin_room, name='toggle_pin'),
    path('api/room/<uuid:room_id>/mute/', views.toggle_mute_room, name='toggle_mute'),
    path('api/room/<uuid:room_id>/mark-read/', views.mark_room_read, name='mark_read'),
    
    # Message API
    path('api/room/<uuid:room_id>/messages/', views.get_messages, name='get_messages'),
    path('api/room/<uuid:room_id>/send/', views.send_message, name='send_message'),
    path('api/room/<uuid:room_id>/search/', views.search_messages, name='search_messages'),
    path('api/message/<uuid:message_id>/edit/', views.edit_message, name='edit_message'),
    path('api/message/<uuid:message_id>/delete/', views.delete_message, name='delete_message'),
    path('api/message/<uuid:message_id>/react/', views.react_to_message, name='react_message'),
    
    # User search
    path('api/users/search/', views.user_search, name='user_search'),
]