from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.db.models import Q, Count, Max, Prefetch, F
from django.utils import timezone
from django.core.paginator import Paginator
from .models import ChatRoom, Message, RoomMembership, MessageReaction, TypingIndicator
from accounts.models import User
import json


@login_required
def chat_home( request):

    rooms = ChatRoom.objects.filter(
        members=request.user,
        is_active=True
    ).select_related('created_by').prefetch_related(
        'members',
        Prefetch('messages', queryset=Message.objects.filter(is_deleted=False)[:1])
    ).annotate(
        unread_count=Count('messages', filter=Q(
            messages__created_at__gt=F('memberships__last_read_at'),
            memberships__user=request.user
        ))
    ).order_by('-updated_at')
  
    direct_rooms = rooms.filter(room_type='direct')
    group_rooms = rooms.filter(room_type='group')
    event_rooms = rooms.filter(room_type='event')
    
    context = {
        'direct_rooms': direct_rooms,
        'group_rooms': group_rooms,
        'event_rooms': event_rooms,
        'total_unread': sum(r.unread_count for r in rooms),
    }
    
    return render(request, 'chat/home.html', context)


@login_required
def chat_room(request, room_id):
 
    room = get_object_or_404(
        ChatRoom.objects.select_related('created_by').prefetch_related('members'),
        id=room_id,
        members=request.user
    )
 
    membership = RoomMembership.objects.get(room=room, user=request.user)
    membership.last_read_at = timezone.now()
    membership.save()
 
    messages_list = room.messages.filter(is_deleted=False).select_related(
        'sender', 'reply_to__sender'
    ).prefetch_related('reactions', 'mentions')[:50]
    
    context = {
        'room': room,
        'messages': messages_list,
        'membership': membership,
        'members': room.members.all(),
    }
    
    return render(request, 'chat/room.html', context)


@login_required
@require_http_methods(["POST"])
def create_room(request):
 
    room_type = request.POST.get('room_type', 'group')
    name = request.POST.get('name', '').strip()
    description = request.POST.get('description', '')
    member_ids = request.POST.getlist('members[]')
    
    if room_type == 'direct' and len(member_ids) != 1:
        return JsonResponse({'error': 'Direct messages require exactly one other user'}, status=400)

    if room_type == 'direct':
        other_user = get_object_or_404(User, id=member_ids[0])
        existing_dm = ChatRoom.objects.filter(
            room_type='direct',
            members=request.user
        ).filter(members=other_user).first()
        
        if existing_dm:
            return JsonResponse({
                'success': True,
                'room_id': str(existing_dm.id),
                'redirect': existing_dm.get_absolute_url()
            })

    room = ChatRoom.objects.create(
        name=name,
        room_type=room_type,
        description=description,
        created_by=request.user
    )
 
    RoomMembership.objects.create(room=room, user=request.user, role='admin')

    for user_id in member_ids:
        user = get_object_or_404(User, id=user_id)
        RoomMembership.objects.create(room=room, user=user, role='member')
    
    return JsonResponse({
        'success': True,
        'room_id': str(room.id),
        'redirect': room.get_absolute_url()
    })


@login_required
@require_http_methods(["POST"])
def send_message(request, room_id):
   
    room = get_object_or_404(ChatRoom, id=room_id, members=request.user)
    
    content = request.POST.get('content', '').strip()
    reply_to_id = request.POST.get('reply_to')
    file = request.FILES.get('file')
    
    if not content and not file:
        return JsonResponse({'error': 'Message cannot be empty'}, status=400)

    message = Message.objects.create(
        room=room,
        sender=request.user,
        content=content,
        message_type='image' if file and file.content_type.startswith('image/') else 'file' if file else 'text'
    )
    
    if file:
        message.file = file
        message.file_name = file.name
        message.file_size = file.size
        message.save()
    
    if reply_to_id:
        message.reply_to = get_object_or_404(Message, id=reply_to_id, room=room)
        message.save()
 
    import re
    mentions = re.findall(r'@(\w+)', content)
    for username in mentions:
        try:
            user = User.objects.get(username=username)
            if user in room.members.all():
                message.mentions.add(user)
        except User.DoesNotExist:
            pass
  
    room.updated_at = timezone.now()
    room.save()
    
    return JsonResponse({
        'success': True,
        'message_id': str(message.id),
        'message': {
            'id': str(message.id),
            'sender': {
                'id': str(request.user.id),
                'name': request.user.display_name,
                'avatar': request.user.avatar.url if request.user.avatar else None
            },
            'content': message.content,
            'created_at': message.created_at.isoformat(),
            'message_type': message.message_type,
        }
    })


@login_required
def get_messages(request, room_id):
 
    room = get_object_or_404(ChatRoom, id=room_id, members=request.user)
    
    before_id = request.GET.get('before')
    limit = int(request.GET.get('limit', 50))
    
    messages_query = room.messages.filter(is_deleted=False).select_related(
        'sender', 'reply_to__sender'
    ).prefetch_related('reactions__user', 'mentions')
    
    if before_id:
        before_msg = get_object_or_404(Message, id=before_id)
        messages_query = messages_query.filter(created_at__lt=before_msg.created_at)
    
    messages_list = list(messages_query[:limit])
    
    messages_data = [{
        'id': str(msg.id),
        'sender': {
            'id': str(msg.sender.id),
            'name': msg.sender.display_name,
            'avatar': msg.sender.avatar.url if msg.sender.avatar else None
        } if msg.sender else None,
        'content': msg.content,
        'message_type': msg.message_type,
        'file_url': msg.file.url if msg.file else None,
        'file_name': msg.file_name,
        'reply_to': {
            'id': str(msg.reply_to.id),
            'sender': msg.reply_to.sender.display_name if msg.reply_to.sender else 'Unknown',
            'content': msg.reply_to.content[:50]
        } if msg.reply_to else None,
        'reactions': [
            {'emoji': r.emoji, 'user_id': str(r.user.id), 'user_name': r.user.display_name}
            for r in msg.reactions.all()
        ],
        'is_edited': msg.is_edited,
        'created_at': msg.created_at.isoformat(),
    } for msg in messages_list]
    
    return JsonResponse({
        'messages': messages_data,
        'has_more': len(messages_list) == limit
    })


@login_required
@require_http_methods(["POST"])
def edit_message(request, message_id):
  
    message = get_object_or_404(Message, id=message_id, sender=request.user)
    
    content = request.POST.get('content', '').strip()
    if not content:
        return JsonResponse({'error': 'Content cannot be empty'}, status=400)
    
    message.content = content
    message.is_edited = True
    message.save()
    
    return JsonResponse({'success': True})


@login_required
@require_http_methods(["POST"])
def delete_message(request, message_id):

    message = get_object_or_404(Message, id=message_id, sender=request.user)
    
    message.is_deleted = True
    message.save()
    
    return JsonResponse({'success': True})


@login_required
@require_http_methods(["POST"])
def react_to_message(request, message_id):

    message = get_object_or_404(Message, id=message_id, room__members=request.user)
    
    emoji = request.POST.get('emoji', '').strip()
    if not emoji:
        return JsonResponse({'error': 'Emoji required'}, status=400)
    
    reaction, created = MessageReaction.objects.get_or_create(
        message=message,
        user=request.user,
        emoji=emoji
    )
    
    if not created:
        reaction.delete()
        return JsonResponse({'success': True, 'action': 'removed'})
    
    return JsonResponse({'success': True, 'action': 'added'})


@login_required
@require_http_methods(["POST"])
def update_room(request, room_id):
 
    room = get_object_or_404(ChatRoom, id=room_id)
    membership = get_object_or_404(RoomMembership, room=room, user=request.user)
    
    if membership.role not in ['admin', 'moderator']:
        return JsonResponse({'error': 'Permission denied'}, status=403)
    
    name = request.POST.get('name')
    description = request.POST.get('description')
    
    if name:
        room.name = name
    if description is not None:
        room.description = description
    
    room.save()
    return JsonResponse({'success': True})


@login_required
@require_http_methods(["POST"])
def add_members(request, room_id):

    room = get_object_or_404(ChatRoom, id=room_id)
    membership = get_object_or_404(RoomMembership, room=room, user=request.user)
    
    if room.room_type == 'direct':
        return JsonResponse({'error': 'Cannot add members to direct messages'}, status=400)
    
    if membership.role not in ['admin', 'moderator']:
        return JsonResponse({'error': 'Permission denied'}, status=403)
    
    user_ids = request.POST.getlist('user_ids[]')
    added = []
    
    for user_id in user_ids:
        user = get_object_or_404(User, id=user_id)
        _, created = RoomMembership.objects.get_or_create(
            room=room,
            user=user,
            defaults={'role': 'member'}
        )
        if created:
            added.append(user.display_name)
   
            Message.objects.create(
                room=room,
                message_type='system',
                content=f"{user.display_name} joined the room"
            )
    
    return JsonResponse({'success': True, 'added': added})


@login_required
@require_http_methods(["POST"])
def leave_room(request, room_id):
 
    room = get_object_or_404(ChatRoom, id=room_id)
    membership = get_object_or_404(RoomMembership, room=room, user=request.user)
    
    if room.room_type == 'direct':
        return JsonResponse({'error': 'Cannot leave direct messages'}, status=400)
    
    membership.delete()
    
    Message.objects.create(
        room=room,
        message_type='system',
        content=f"{request.user.display_name} left the room"
    )
    
    return JsonResponse({'success': True})


@login_required
def search_messages(request, room_id):

    room = get_object_or_404(ChatRoom, id=room_id, members=request.user)
    query = request.GET.get('q', '').strip()
    
    if not query or len(query) < 2:
        return JsonResponse({'messages': []})
    
    messages = room.messages.filter(
        content__icontains=query,
        is_deleted=False
    ).select_related('sender')[:20]
    
    results = [{
        'id': str(msg.id),
        'content': msg.content,
        'sender': msg.sender.display_name if msg.sender else 'System',
        'created_at': msg.created_at.isoformat()
    } for msg in messages]
    
    return JsonResponse({'messages': results})


@login_required
def user_search(request):

    query = request.GET.get('q', '').strip()
    exclude_room = request.GET.get('exclude_room')
    
    if not query or len(query) < 2:
        return JsonResponse({'users': []})
    
    users = User.objects.filter(
        Q(username__icontains=query) |
        Q(first_name__icontains=query) |
        Q(last_name__icontains=query) |
        Q(email__icontains=query)
    ).exclude(id=request.user.id)[:10]
    
    if exclude_room:
        room = get_object_or_404(ChatRoom, id=exclude_room)
        users = users.exclude(id__in=room.members.values_list('id', flat=True))
    
    results = [{
        'id': str(u.id),
        'username': u.username,
        'display_name': u.display_name,
        'avatar': u.avatar.url if u.avatar else None,
        'is_online': u.is_online,
    } for u in users]
    
    return JsonResponse({'users': results})


@login_required
@require_http_methods(["POST"])
def mark_room_read(request, room_id):

    room = get_object_or_404(ChatRoom, id=room_id, members=request.user)
    membership = RoomMembership.objects.get(room=room, user=request.user)
    membership.last_read_at = timezone.now()
    membership.save()
    
    return JsonResponse({'success': True})


@login_required
@require_http_methods(["POST"])
def toggle_pin_room(request, room_id):

    room = get_object_or_404(ChatRoom, id=room_id, members=request.user)
    membership = RoomMembership.objects.get(room=room, user=request.user)
    membership.is_pinned = not membership.is_pinned
    membership.save()
    
    return JsonResponse({'success': True, 'is_pinned': membership.is_pinned})


@login_required
@require_http_methods(["POST"])
def toggle_mute_room(request, room_id):
\
    room = get_object_or_404(ChatRoom, id=room_id, members=request.user)
    membership = RoomMembership.objects.get(room=room, user=request.user)
    membership.is_muted = not membership.is_muted
    membership.save()
    
    return JsonResponse({'success': True, 'is_muted': membership.is_muted})