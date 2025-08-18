from django.urls import path
from . import views

app_name = 'forums'
urlpatterns = [
    path('', views.forum_home, name='home'),
    path('<slug:slug>/', views.category_detail, name='category_detail'),
    path('<slug:category_slug>/<slug:topic_slug>/', views.topic_detail, name='topic_detail'),
    path('<slug:category_slug>/<slug:topic_slug>/post/', views.create_post, name='create_post'),
]