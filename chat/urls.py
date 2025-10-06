from django.urls import path
from . import views

app_name = 'chat'

urlpatterns = [
    # Main chat pages
    path('', views.chat_home, name='home'),
    path('<uuid:room_id>/', views.chat_room, name='room'),

    # Room management
    path('create/', views.create_room, name='create_room'),
    path('<uuid:room_id>/update/', views.update_room, name='update_room'),
    path('<uuid:room_id>/add-members/', views.add_members, name='add_members'),
    path('<uuid:room_id>/leave/', views.leave_room, name='leave_room'),
    path('<uuid:room_id>/mark-read/', views.mark_room_read, name='mark_room_read'),
    path('<uuid:room_id>/pin-toggle/', views.toggle_pin_room, name='toggle_pin_room'),
    path('<uuid:room_id>/mute-toggle/', views.toggle_mute_room, name='toggle_mute_room'),

    # Message handling
    path('<uuid:room_id>/send/', views.send_message, name='send_message'),
    path('<uuid:room_id>/messages/', views.get_messages, name='get_messages'),
    path('message/<uuid:message_id>/edit/', views.edit_message, name='edit_message'),
    path('message/<uuid:message_id>/delete/', views.delete_message, name='delete_message'),
    path('message/<uuid:message_id>/react/', views.react_to_message, name='react_to_message'),

    # Search
    path('<uuid:room_id>/search/', views.search_messages, name='search_messages'),
    path('user-search/', views.user_search, name='user_search'),
]
