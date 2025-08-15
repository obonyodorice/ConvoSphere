from django.urls import path
from . import views

app_name = 'chat'
urlpatterns = [
    path('', views.room_list, name='room_list'),
    path('room/<uuid:room_id>/', views.chat_room, name='room'),
    path('room/<uuid:room_id>/send/', views.send_message, name='send_message'),
]