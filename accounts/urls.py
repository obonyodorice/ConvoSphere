from django.urls import path
from . import views

app_name = 'accounts'
urlpatterns = [
    path('login/', views.LoginView.as_view(), name='login'),
    path('profile/<uuid:user_id>/', views.profile_view, name='profile'),
    path('status/update/', views.update_status, name='update_status'),
]