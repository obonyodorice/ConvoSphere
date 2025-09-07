from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth import views as auth_views
from django.http import JsonResponse
from .models import User

class LoginView(auth_views.LoginView):
    template_name = 'accounts/login.html'
    redirect_authenticated_user = True

@login_required
def profile_view(request, user_id):
    user = get_object_or_404(User, id=user_id)
    return render(request, 'accounts/profile.html', {'profile_user': user})

@login_required
def update_status(request):
    if request.method == 'POST':
        request.user.is_online = request.POST.get('is_online', False)
        request.user.save()
        return JsonResponse({'status': 'updated'})

def logout_view(request):
    return auth_views.LogoutView.as_view(next_page='accounts:login')(request)
