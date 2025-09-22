from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordResetForm
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.core.paginator import Paginator
from django.db.models import Q
from .models import User, UserActivity
from .forms import SignUpForm, ProfileForm, LoginForm
import json


def signup_view(request):
    if request.user.is_authenticated:
        return redirect('accounts:dashboard')
    
    if request.method == 'POST':
        form = SignUpForm(request.POST)
        if form.is_valid():
            user = form.save()
            UserActivity.objects.create(
                user=user,
                activity_type='login',
                description='User registered and logged in',
                ip_address=request.META.get('REMOTE_ADDR')
            )
            login(request, user)
            messages.success(request, 'Welcome! Your account has been created.')
            return redirect('accounts:dashboard')
    else:
        form = SignUpForm()
    
    return render(request, 'accounts/signup.html', {'form': form})


def login_view(request):

    if request.user.is_authenticated:
        return redirect('accounts:dashboard')
    
    if request.method == 'POST':
        form = LoginForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data['email']
            password = form.cleaned_data['password']
            user = authenticate(request, username=email, password=password)
            
            if user:
                login(request, user)
                user.is_online = True
                user.save()
 
                UserActivity.objects.create(
                    user=user,
                    activity_type='login',
                    ip_address=request.META.get('REMOTE_ADDR'),
                    user_agent=request.META.get('HTTP_USER_AGENT', '')
                )
                
                messages.success(request, f'Welcome back, {user.display_name}!')
                next_url = request.GET.get('next', 'accounts:dashboard')
                return redirect(next_url)
            else:
                messages.error(request, 'Invalid email or password.')
    else:
        form = LoginForm()
    
    return render(request, 'accounts/login.html', {'form': form})


def logout_view(request):
    if request.user.is_authenticated:

        request.user.is_online = False
        request.user.save()

        UserActivity.objects.create(
            user=request.user,
            activity_type='logout',
            ip_address=request.META.get('REMOTE_ADDR')
        )
    
    logout(request)
    messages.info(request, 'You have been logged out.')
    return redirect('accounts:login')


@login_required
def dashboard_view(request):

    user = request.user
    recent_activities = user.activities.all()[:10]

    stats = {
        'total_posts': user.total_posts,
        'events_attended': user.total_events_attended,
        'reputation': user.reputation_score,
        'followers_count': user.followers.count(),
        'following_count': user.following.count(),
    }
    
    context = {
        'user': user,
        'stats': stats,
        'recent_activities': recent_activities,
        'profile_completion': calculate_profile_completion(user),
    }
    
    return render(request, 'accounts/dashboard.html', context)


@login_required
def profile_view(request, pk=None):

    if pk:
        user = get_object_or_404(User, pk=pk)
        is_own_profile = user == request.user
    else:
        user = request.user
        is_own_profile = True

    activities = user.activities.filter(
        activity_type__in=['forum_post', 'event_join']
    )[:10]
    
    context = {
        'profile_user': user,
        'is_own_profile': is_own_profile,
        'activities': activities,
        'can_follow': not is_own_profile and request.user.is_authenticated,
    }
    
    return render(request, 'accounts/profile.html', context)


@login_required
def edit_profile_view(request):

    if request.method == 'POST':
        form = ProfileForm(request.POST, request.FILES, instance=request.user)
        if form.is_valid():
            form.save()

            UserActivity.objects.create(
                user=request.user,
                activity_type='profile_update',
                description='Profile updated'
            )
            
            messages.success(request, 'Your profile has been updated!')
            return redirect('accounts:profile')
    else:
        form = ProfileForm(instance=request.user)
    
    return render(request, 'accounts/edit_profile.html', {'form': form})


@login_required
def settings_view(request):
    if request.method == 'POST':

        notification_settings = {}
        for key in request.user.get_default_notification_settings().keys():
            notification_settings[key] = key in request.POST
        
        request.user.notification_settings = notification_settings
        request.user.save()
        
        messages.success(request, 'Settings updated successfully!')
        return redirect('accounts:settings')
    
    return render(request, 'accounts/settings.html', {
        'notification_settings': request.user.notification_settings
    })


def password_reset_view(request):

    if request.method == 'POST':
        form = PasswordResetForm(request.POST)
        if form.is_valid():
            form.save(
                request=request,
                email_template_name='accounts/password_reset_email.html',
                subject_template_name='accounts/password_reset_subject.txt'
            )
            messages.success(request, 'Password reset email has been sent!')
            return redirect('accounts:login')
    else:
        form = PasswordResetForm()
    
    return render(request, 'accounts/password_reset.html', {'form': form})

@login_required
@require_http_methods(["POST"])
def toggle_follow_view(request, user_id):
 
    target_user = get_object_or_404(User, pk=user_id)
    
    if target_user == request.user:
        return JsonResponse({'error': 'Cannot follow yourself'}, status=400)
    
    from .models import UserConnection
    connection, created = UserConnection.objects.get_or_create(
        follower=request.user,
        following=target_user
    )
    
    if not created:
        connection.delete()
        following = False
    else:
        following = True
    
    return JsonResponse({
        'following': following,
        'followers_count': target_user.followers.count()
    })


@login_required
def update_online_status(request):

    request.user.is_online = True
    request.user.save()
    return JsonResponse({'status': 'online'})


def calculate_profile_completion(user):

    fields = ['first_name', 'last_name', 'bio', 'avatar', 'location']
    completed = sum(1 for field in fields if getattr(user, field))
    return int((completed / len(fields)) * 100)