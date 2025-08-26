# chat/views.py
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.core.paginator import Paginator
from django.db.models import Count, Q, Prefetch
from django.utils import timezone
from django.views.decorators.http import require_http_methods
from django.contrib import messages
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from datetime import timedelta
import json

from .models import (
    ChatRoom, Message, RoomMembership, UserActivity, 
    ChatEvent, RealTimeUtils, TypingIndicator
)

@login_required
def room_list(request):
    """Enhanced room list view with real-time data preparation"""
    
    # Update user activity
    RealTimeUtils.update_user_activity(request.user)
    
    # Get user's rooms with optimized queries
    user_rooms = ChatRoom.objects.for_user(request.user).with_last_messages().annotate(
        member_count=Count('members'),
        online_members_count=Count(
            'members',
            filter=Q(members__activity_tracker__last_activity__gte=timezone.now() - timedelta(minutes=10))
        )
    ).select_related().prefetch_related(
        'members',
        Prefetch('messages', queryset=Message.objects.select_related('sender')[:1])
    ).order_by('-last_activity')
    
    # Get unread counts for each room
    user_unread_counts = RealTimeUtils.get_user_unread_counts(request.user)
    
    # Get room type counts for filters
    room_type_counts = {
        'group': user_rooms.filter(room_type='group').count(),
        'private': user_rooms.filter(room_type='private').count(),
        'forum': user_rooms.filter(room_type='forum').count(),
        'event': user_rooms.filter(room_type='event').count(),
    }
    
    # Get online users
    online_users = RealTimeUtils.get_online_users()
    
    # Get recent activities
    recent_activities = RealTimeUtils.get_recent_activities(limit=15)
    
    # Prepare room data with enhanced information
    rooms_with_data = []
    for room in user_rooms:
        # Get last message info
        last_message = room.latest_messages[0] if hasattr(room, 'latest_messages') and room.latest_messages else None
        
        # Get other user for private chats
        other_user = None
        if room.room_type == 'private':
            other_user = room.get_other_user(request.user)
        
        room_data = {
            'room': room,
            'unread_count': user_unread_counts.get(str(room.id), 0),
            'last_message': last_message,
            'other_user': other_user,
            'online_members_count': getattr(room, 'online_members_count', 0),
            'member_count': getattr(room, 'member_count', 0),
        }
        rooms_with_data.append(room_data)
    
    context = {
        'rooms': user_rooms,
        'rooms_with_data': rooms_with_data,
        'room_type_counts': room_type_counts,
        'online_users': online_users,
        'recent_activities': recent_activities,
        'total_unread': sum(user_unread_counts.values()),
        'user_activity': getattr(request.user, 'activity_tracker', None),
    }
    
    return render(request, 'chat/room_list.html', context)


@login_required
def chat_room(request, room_id):
    """Enhanced chat room view with real-time preparation"""
    
    room = get_object_or_404(ChatRoom, id=room_id)
    
    # Check if user has access
    if request.user not in room.members.all():
        messages.error(request, "You don't have access to this room.")
        return redirect('chat:room_list')
    
    # Update user activity and current room
    RealTimeUtils.update_user_activity(request.user, room)
    
    # Get messages with pagination
    messages_queryset = room.messages.select_related('sender').prefetch_related(
        'reactions', 'replies', 'read_by', 'delivered_to'
    ).order_by('-created_at')
    
    paginator = Paginator(messages_queryset, 50)
    page = request.GET.get('page', 1)
    messages_page = paginator.get_page(page)
    
    # Mark messages as read
    mark_messages_as_read(request.user, room)
    
    # Get room statistics
    room_stats = {
        'total_messages': room.message_count,
        'member_count': room.members.count(),
        'online_count': RealTimeUtils.get_room_online_count(room),
        'created_at': room.created_at,
        'last_activity': room.last_activity,
    }
    
    # Get typing indicators
    typing_users = TypingIndicator.objects.filter(
        room=room,
        started_at__gte=timezone.now() - timedelta(minutes=2)
    ).exclude(user=request.user).select_related('user')
    
    context = {
        'room': room,
        'messages': messages_page,
        'room_stats': room_stats,
        'typing_users': typing_users,
        'is_room_admin': request.user in room.admins.all(),
        'other_user': room.get_other_user(request.user) if room.room_type == 'private' else None,
    }
    
    return render(request, 'chat/room.html', context)


@login_required
@require_http_methods(["POST"])
def send_message(request, room_id):
    """Enhanced message sending with real-time broadcasting"""
    
    room = get_object_or_404(ChatRoom, id=room_id)
    
    # Check access
    if request.user not in room.members.all():
        return JsonResponse({'error': 'Access denied'}, status=403)
    
    content = request.POST.get('content', '').strip()
    message_type = request.POST.get('message_type', 'text')
    parent_message_id = request.POST.get('parent_message')
    
    if not content and message_type == 'text':
        return JsonResponse({'error': 'Message content required'}, status=400)
    
    # Create message
    message_data = {
        'room': room,
        'sender': request.user,
        'content': content,
        'message_type': message_type,
    }
    
    # Handle file uploads
    if 'file' in request.FILES:
        message_data['file_attachment'] = request.FILES['file']
        if not content:
            message_data['content'] = f"Shared a file: {request.FILES['file'].name}"
    
    # Handle replies
    if parent_message_id:
        try:
            parent = Message.objects.get(id=parent_message_id, room=room)
            message_data['parent_message'] = parent
        except Message.DoesNotExist:
            pass
    
    message = Message.objects.create(**message_data)
    
    # Create chat event
    ChatEvent.objects.create(
        event_type='message_sent',
        room=room,
        user=request.user,
        message=message,
        event_data={'content': content[:100]}
    )
    
    # Broadcast to WebSocket consumers
    broadcast_new_message(room, message, request.user)
    
    # Update user activity
    RealTimeUtils.update_user_activity(request.user, room)
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({
            'status': 'sent',
            'message_id': str(message.id),
            'timestamp': message.created_at.isoformat(),
            'content': message.content,
            'sender': request.user.username,
        })
    
    return redirect('chat:room', room_id=room_id)


@login_required
def mark_room_read(request, room_id):
    """Mark all messages in a room as read"""
    
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)
    
    room = get_object_or_404(ChatRoom, id=room_id)
    
    if request.user not in room.members.all():
        return JsonResponse({'error': 'Access denied'}, status=403)
    
    marked_count = mark_messages_as_read(request.user, room)
    
    return JsonResponse({
        'status': 'success',
        'marked_count': marked_count
    })


@login_required
def get_room_data(request, room_id):
    """Get room data for real-time updates"""
    
    room = get_object_or_404(ChatRoom, id=room_id)
    
    if request.user not in room.members.all():
        return JsonResponse({'error': 'Access denied'}, status=403)
    
    # Get recent messages
    recent_messages = room.messages.select_related('sender').order_by('-created_at')[:20]
    
    messages_data = []
    for msg in reversed(recent_messages):
        messages_data.append({
            'id': str(msg.id),
            'content': msg.content,
            'sender': {
                'id': msg.sender.id,
                'username': msg.sender.username,
                'display_name': msg.sender.get_full_name() or msg.sender.username,
            },
            'message_type': msg.message_type,
            'created_at': msg.created_at.isoformat(),
            'is_read': request.user in msg.read_by.all(),
            'is_delivered': request.user in msg.delivered_to.all(),
        })
    
    room_data = {
        'id': str(room.id),
        'name': room.name,
        'room_type': room.room_type,
        'member_count': room.members.count(),
        'online_count': RealTimeUtils.get_room_online_count(room),
        'messages': messages_data,
        'unread_count': room.get_unread_count_for_user(request.user),
    }
    
    return JsonResponse(room_data)


@login_required
def update_typing_status(request, room_id):
    """Update typing indicator status"""
    
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)
    
    room = get_object_or_404(ChatRoom, id=room_id)
    
    if request.user not in room.members.all():
        return JsonResponse({'error': 'Access denied'}, status=403)
    
    is_typing = request.POST.get('is_typing', 'false').lower() == 'true'
    
    if is_typing:
        # Create or update typing indicator
        typing_indicator, created = TypingIndicator.objects.get_or_create(
            room=room,
            user=request.user
        )
    else:
        # Remove typing indicator
        TypingIndicator.objects.filter(room=room, user=request.user).delete()
    
    # Broadcast typing status
    broadcast_typing_status(room, request.user, is_typing)
    
    return JsonResponse({'status': 'success'})


@login_required
def create_room(request):
    """Create a new chat room"""
    
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        room_type = request.POST.get('room_type', 'group')
        description = request.POST.get('description', '').strip()
        
        if not name:
            return JsonResponse({'error': 'Room name required'}, status=400)
        
        if room_type not in dict(ChatRoom.ROOM_TYPES):
            return JsonResponse({'error': 'Invalid room type'}, status=400)
        
        # Create room
        room = ChatRoom.objects.create(
            name=name,
            room_type=room_type,
            description=description
        )
        
        # Add creator as member and admin
        room.members.add(request.user)
        room.admins.add(request.user)
        
        # Create membership record
        RoomMembership.objects.create(room=room, user=request.user)
        
        # Create chat event
        ChatEvent.objects.create(
            event_type='room_created',
            room=room,
            user=request.user,
            event_data={'name': name, 'type': room_type}
        )
        
        # Broadcast room creation
        broadcast_room_update('room_created', room, request.user)
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'status': 'created',
                'room_id': str(room.id),
                'redirect_url': f'/chat/room/{room.id}/'
            })
        
        messages.success(request, f'Room "{name}" created successfully!')
        return redirect('chat:room', room_id=room.id)
    
    return render(request, 'chat/create_room.html')


@login_required
def join_room(request, room_id):
    """Join a chat room"""
    
    room = get_object_or_404(ChatRoom, id=room_id, is_active=True)
    
    if request.user in room.members.all():
        return redirect('chat:room', room_id=room.id)
    
    # Add user to room
    room.members.add(request.user)
    
    # Create membership record
    RoomMembership.objects.create(room=room, user=request.user)
    
    # Create chat event
    ChatEvent.objects.create(
        event_type='user_joined',
        room=room,
        user=request.user
    )
    
    # Broadcast user joined
    broadcast_room_update('user_joined', room, request.user)
    
    messages.success(request, f'You joined "{room.name}"!')
    return redirect('chat:room', room_id=room.id)


@login_required
def leave_room(request, room_id):
    """Leave a chat room"""
    
    room = get_object_or_404(ChatRoom, id=room_id)
    
    if request.user not in room.members.all():
        return redirect('chat:room_list')
    
    # Remove user from room
    room.members.remove(request.user)
    room.admins.remove(request.user)  # Also remove from admins if applicable
    
    # Delete membership record
    RoomMembership.objects.filter(room=room, user=request.user).delete()
    
    # Create chat event
    ChatEvent.objects.create(
        event_type='user_left',
        room=room,
        user=request.user
    )
    
    # Broadcast user left
    broadcast_room_update('user_left', room, request.user)
    
    messages.info(request, f'You left "{room.name}".')
    return redirect('chat:room_list')


# Real-time broadcasting functions
def broadcast_new_message(room, message, sender):
    """Broadcast new message to WebSocket consumers"""
    channel_layer = get_channel_layer()
    
    # Broadcast to room
    async_to_sync(channel_layer.group_send)(
        f'chat_{room.id}',
        {
            'type': 'chat_message',
            'message': message.content,
            'username': sender.username,
            'user_id': sender.id,
            'message_id': str(message.id),
            'message_type': message.message_type,
            'timestamp': message.created_at.isoformat(),
        }
    )
    
    # Broadcast to room list consumers (for unread counts)
    for member in room.members.all():
        if member != sender:  # Don't notify sender
            unread_count = room.get_unread_count_for_user(member)
            
            async_to_sync(channel_layer.group_send)(
                f'user_{member.id}',
                {
                    'type': 'new_message_notification',
                    'room_id': str(room.id),
                    'message': {
                        'content': message.content[:100],
                        'sender': sender.username,
                        'message_type': message.message_type
                    },
                    'sender': {
                        'id': sender.id,
                        'username': sender.username
                    },
                    'unread_count': unread_count,
                    'timestamp': message.created_at.isoformat()
                }
            )


def broadcast_typing_status(room, user, is_typing):
    """Broadcast typing status to room members"""
    channel_layer = get_channel_layer()
    
    async_to_sync(channel_layer.group_send)(
        f'chat_{room.id}',
        {
            'type': 'typing_indicator',
            'username': user.username,
            'user_id': user.id,
            'is_typing': is_typing
        }
    )


def broadcast_room_update(action, room, user):
    """Broadcast room updates to all users"""
    channel_layer = get_channel_layer()
    
    async_to_sync(channel_layer.group_send)(
        'room_list_updates',
        {
            'type': 'room_member_update',
            'room_id': str(room.id),
            'member_count': room.members.count(),
            'online_count': RealTimeUtils.get_room_online_count(room),
            'action': action,
            'user': {
                'id': user.id,
                'username': user.username
            }
        }
    )


def mark_messages_as_read(user, room):
    """Mark all unread messages in a room as read for a user"""
    unread_messages = room.messages.exclude(read_by=user).exclude(sender=user)
    count = 0
    
    for message in unread_messages:
        message.read_by.add(user)
        count += 1
    
    # Update membership last read message
    try:
        membership = RoomMembership.objects.get(room=room, user=user)
        latest_message = room.messages.first()
        if latest_message:
            membership.last_read_message = latest_message
            membership.save(update_fields=['last_read_message'])
    except RoomMembership.DoesNotExist:
        pass
    
    return count


# API endpoints for mobile/external clients
@login_required
def api_room_list(request):
    """API endpoint for room list data"""
    rooms = ChatRoom.objects.for_user(request.user).with_last_messages()
    
    rooms_data = []
    for room in rooms:
        last_message = room.latest_messages[0] if hasattr(room, 'latest_messages') and room.latest_messages else None
        
        rooms_data.append({
            'id': str(room.id),
            'name': room.name,
            'room_type': room.room_type,
            'description': room.description,
            'member_count': room.members.count(),
            'online_count': RealTimeUtils.get_room_online_count(room),
            'unread_count': room.get_unread_count_for_user(request.user),
            'last_message': {
                'content': last_message.content if last_message else None,
                'sender': last_message.sender.username if last_message else None,
                'created_at': last_message.created_at.isoformat() if last_message else None,
            } if last_message else None,
            'last_activity': room.last_activity.isoformat(),
            'created_at': room.created_at.isoformat(),
        })
    
    return JsonResponse({
        'rooms': rooms_data,
        'total_count': len(rooms_data),
        'online_users_count': RealTimeUtils.get_online_users().count(),
    })


@login_required
def api_recent_messages(request, room_id):
    """API endpoint for recent messages in a room"""
    room = get_object_or_404(ChatRoom, id=room_id)
    
    if request.user not in room.members.all():
        return JsonResponse({'error': 'Access denied'}, status=403)
    
    limit = min(int(request.GET.get('limit', 20)), 100)  # Max 100 messages
    before_id = request.GET.get('before')
    
    messages_queryset = room.messages.select_related('sender')
    
    if before_id:
        try:
            before_message = Message.objects.get(id=before_id)
            messages_queryset = messages_queryset.filter(created_at__lt=before_message.created_at)
        except Message.DoesNotExist:
            pass
    
    messages = messages_queryset.order_by('-created_at')[:limit]
    
    messages_data = []
    for msg in reversed(messages):
        messages_data.append({
            'id': str(msg.id),
            'content': msg.content,
            'sender': {
                'id': msg.sender.id,
                'username': msg.sender.username,
                'display_name': msg.sender.get_full_name() or msg.sender.username,
            },
            'message_type': msg.message_type,
            'created_at': msg.created_at.isoformat(),
            'is_edited': msg.is_edited,
            'reply_count': msg.reply_count,
        })
    
    return JsonResponse({
        'messages': messages_data,
        'has_more': len(messages) == limit,
    })


# Cleanup task (can be run as a management command or periodic task)
@login_required
def cleanup_chat_data(request):
    """Cleanup old chat data (admin only)"""
    if not request.user.is_staff:
        return JsonResponse({'error': 'Admin access required'}, status=403)
    
    if request.method == 'POST':
        RealTimeUtils.cleanup_old_data()
        return JsonResponse({'status': 'Cleanup completed'})
    
    return JsonResponse({'error': 'POST required'}, status=405)