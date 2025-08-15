from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.core.paginator import Paginator
from .models import ChatRoom, Message

@login_required
def chat_room(request, room_id):
    room = get_object_or_404(ChatRoom, id=room_id)
    if request.user not in room.members.all():
        return JsonResponse({'error': 'Access denied'}, status=403)
    
    messages = room.messages.select_related('sender').order_by('-created_at')
    paginator = Paginator(messages, 50)
    page = request.GET.get('page', 1)
    messages_page = paginator.get_page(page)
    
    return render(request, 'chat/room.html', {
        'room': room,
        'messages': messages_page
    })

@login_required
def send_message(request, room_id):
    if request.method == 'POST':
        room = get_object_or_404(ChatRoom, id=room_id)
        content = request.POST.get('content')
        
        if content and request.user in room.members.all():
            message = Message.objects.create(
                room=room,
                sender=request.user,
                content=content
            )
            return JsonResponse({
                'status': 'sent',
                'message_id': str(message.id),
                'timestamp': message.created_at.isoformat()
            })
    return JsonResponse({'error': 'Invalid request'}, status=400)

@login_required
def room_list(request):
    rooms = request.user.chat_rooms.filter(is_active=True)
    return render(request, 'chat/room_list.html', {'rooms': rooms})