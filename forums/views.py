from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import Category, Topic, Post

def forum_home(request):
    categories = Category.objects.prefetch_related('topics').all()
    return render(request, 'forums/../home.html', {'categories': categories})

def category_detail(request, slug):
    category = get_object_or_404(Category, slug=slug)
    topics = category.topics.select_related('author').order_by('-is_pinned', '-updated_at')
    return render(request, 'forums/category.html', {'category': category, 'topics': topics})

def topic_detail(request, category_slug, topic_slug):
    topic = get_object_or_404(Topic, slug=topic_slug, category__slug=category_slug)
    posts = topic.posts.select_related('author').order_by('created_at')
    return render(request, 'forums/topic.html', {'topic': topic, 'posts': posts})

@login_required
def create_post(request, category_slug, topic_slug):
    topic = get_object_or_404(Topic, slug=topic_slug, category__slug=category_slug)
    if request.method == 'POST':
        content = request.POST.get('content')
        if content:
            Post.objects.create(topic=topic, author=request.user, content=content)
            messages.success(request, 'Post created successfully!')
    return redirect('forums:topic_detail', category_slug, topic_slug)