from django.urls import path, include
from django.contrib.auth import views as auth_views
from . import views

app_name = 'accounts'

urlpatterns = [
    path('', views.home_view, name='home'),
    path('signup/', views.signup_view, name='signup'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),

    path('password-reset/', views.password_reset_view, name='password_reset'),
    path('password-reset/done/', 
         auth_views.PasswordResetDoneView.as_view(
             template_name='accounts/password_reset_done.html'
         ), name='password_reset_done'),
    path('reset/<uidb64>/<token>/',
         auth_views.PasswordResetConfirmView.as_view(
             template_name='accounts/password_reset_confirm.html',
             success_url='/accounts/login/?reset=success'
         ), name='password_reset_confirm'),

    path('dashboard/', views.dashboard_view, name='dashboard'),
    path('profile/', views.profile_view, name='profile'),
    path('profile/<uuid:pk>/', views.profile_view, name='user_profile'),
    path('profile/edit/', views.edit_profile_view, name='edit_profile'),
    path('settings/', views.settings_view, name='settings'),

    path('api/home-stats/', views.home_stats_api, name='home_stats_api'),
    path('api/activity-feed/', views.activity_feed_api, name='activity_feed_api'),
    path('api/online-users/', views.online_users_api, name='online_users_api'),
    path('api/quick-post/', views.quick_post_api, name='quick_post_api'),
    path('api/trending-topics/', views.trending_topics_api, name='trending_topics_api'),
    path('api/user-stats/', views.user_stats_api, name='user_stats_api'),
    path('api/notification-count/', views.update_online_status, name='notification_count_api'),
 
    path('api/follow/<uuid:user_id>/', views.toggle_follow_view, name='toggle_follow'),
    path('api/online-status/', views.update_online_status, name='update_online_status'),
    
    path('password-change/', 
         auth_views.PasswordChangeView.as_view(
             template_name='accounts/password_change.html',
             success_url='/accounts/dashboard/?changed=success'
         ), name='password_change'),
]