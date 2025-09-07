from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from .models import Notification

@login_required
def notification_list(request):
    notifications = request.user.notifications.filter(is_read=False)
    return render(request, 'notifications/list.html', {'notifications': notifications})

@login_required
def mark_read(request, notification_id):
    try:
        notification = request.user.notifications.get(id=notification_id)
        notification.is_read = True
        notification.save()
        return JsonResponse({'status': 'marked_read'})
    except Notification.DoesNotExist:
        return JsonResponse({'error': 'Notification not found'}, status=404)

@login_required
def mark_all_read(request):
    request.user.notifications.filter(is_read=False).update(is_read=True)
    return JsonResponse({'status': 'all_marked_read'})