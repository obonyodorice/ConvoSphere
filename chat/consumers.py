# chat/consumers.py
import json
import asyncio
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta
from .models import ChatRoom, Message, TypingIndicator, RoomMembership, UserActivity, ChatEvent, RealTimeUtils

User = get_user_model()

class ChatRoomConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.room_id = self.scope['url_route']['kwargs']['room_id']
        self.room_group_name = f'chat_{self.room_id}'
        self.user = self.scope['user']
        
        # Join room group
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        
        # Join user's personal group for notifications
        await self.channel_layer.group_add(
            f'user_{self.user.id}',
            self.channel_name
        )
        
        await self.accept()
        
        # Update user activity
        await self.update_user_activity()
        
        # Broadcast user joined to room list
        await self.broadcast_user_status_change('joined')

    async def disconnect(self, close_code):
        # Leave room group
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )
        
        # Leave user group
        await self.channel_layer.group_discard(
            f'user_{self.user.id}',
            self.channel_name
        )
        
        # Remove typing indicator
        await self.remove_typing_indicator()
        
        # Broadcast user left to room list
        await self.broadcast_user_status_change('left')

    async def receive(self, text_data):
        try:
            text_data_json = json.loads(text_data)
            message_type = text_data_json.get('type')
            
            if message_type == 'chat_message':
                await self.handle_chat_message(text_data_json)
            elif message_type == 'typing_indicator':
                await self.handle_typing_indicator(text_data_json)
            elif message_type == 'mark_read':
                await self.handle_mark_read(text_data_json)
            elif message_type == 'user_activity':
                await self.update_user_activity()
                
        except json.JSONDecodeError:
            await self.send_error('Invalid JSON format')
        except Exception as e:
            await self.send_error(f'Error processing message: {str(e)}')

    async def handle_chat_message(self, data):
        message_content = data.get('message', '').strip()
        if not message_content:
            return
        
        # Save message to database
        message = await self.save_message(message_content)
        if not message:
            return
        
        # Send message to room group
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'chat_message',
                'message': message_content,
                'username': self.user.username,
                'user_id': self.user.id,
                'message_id': str(message.id),
                'timestamp': message.created_at.isoformat(),
                'message_type': message.message_type,
            }
        )
        
        # Broadcast to room list for unread counts and recent activity
        await self.broadcast_new_message_to_room_list(message)

    async def handle_typing_indicator(self, data):
        is_typing = data.get('is_typing', False)
        
        if is_typing:
            await self.save_typing_indicator()
        else:
            await self.remove_typing_indicator()
        
        # Send typing indicator to room group
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'typing_indicator',
                'username': self.user.username,
                'user_id': self.user.id,
                'is_typing': is_typing,
            }
        )

    async def handle_mark_read(self, data):
        await self.mark_messages_as_read()
        
        # Broadcast updated unread count to room list
        await self.broadcast_read_status_update()

    async def chat_message(self, event):
        # Send message to WebSocket
        await self.send(text_data=json.dumps({
            'type': 'chat_message',
            'message': event['message'],
            'username': event['username'],
            'user_id': event['user_id'],
            'message_id': event['message_id'],
            'timestamp': event['timestamp'],
            'message_type': event.get('message_type', 'text'),
        }))

    async def typing_indicator(self, event):
        # Send typing indicator to WebSocket
        await self.send(text_data=json.dumps({
            'type': 'typing_indicator',
            'username': event['username'],
            'user_id': event['user_id'],
            'is_typing': event['is_typing'],
        }))

    async def new_message_notification(self, event):
        # Send notification for messages in other rooms
        await self.send(text_data=json.dumps({
            'type': 'new_message_notification',
            'room_id': event['room_id'],
            'message': event['message'],
            'sender': event['sender'],
            'unread_count': event['unread_count'],
            'timestamp': event['timestamp'],
        }))

    # Database operations
    @database_sync_to_async
    def save_message(self, content):
        try:
            room = ChatRoom.objects.get(id=self.room_id)
            if self.user not in room.members.all():
                return None
            
            message = Message.objects.create(
                room=room,
                sender=self.user,
                content=content,
                message_type='text'
            )
            
            # Create chat event
            ChatEvent.objects.create(
                event_type='message_sent',
                room=room,
                user=self.user,
                message=message,
                event_data={'content': content[:100]}
            )
            
            return message
        except ChatRoom.DoesNotExist:
            return None

    @database_sync_to_async
    def save_typing_indicator(self):
        try:
            room = ChatRoom.objects.get(id=self.room_id)
            TypingIndicator.objects.update_or_create(
                room=room,
                user=self.user,
                defaults={'started_at': timezone.now()}
            )
        except ChatRoom.DoesNotExist:
            pass

    @database_sync_to_async
    def remove_typing_indicator(self):
        TypingIndicator.objects.filter(
            room_id=self.room_id,
            user=self.user
        ).delete()

    @database_sync_to_async
    def mark_messages_as_read(self):
        try:
            room = ChatRoom.objects.get(id=self.room_id)
            unread_messages = room.messages.exclude(read_by=self.user).exclude(sender=self.user)
            
            for message in unread_messages:
                message.read_by.add(self.user)
            
            # Update membership
            membership, created = RoomMembership.objects.get_or_create(
                room=room, user=self.user
            )
            latest_message = room.messages.first()
            if latest_message:
                membership.last_read_message = latest_message
                membership.save()
            
            return unread_messages.count()
        except ChatRoom.DoesNotExist:
            return 0

    @database_sync_to_async
    def update_user_activity(self):
        activity, created = UserActivity.objects.get_or_create(
            user=self.user,
            defaults={'is_online': True}
        )
        activity.set_online_status(True, ChatRoom.objects.filter(id=self.room_id).first())

    @database_sync_to_async
    def get_room_members(self):
        try:
            room = ChatRoom.objects.get(id=self.room_id)
            return list(room.members.values_list('id', flat=True))
        except ChatRoom.DoesNotExist:
            return []

    async def broadcast_new_message_to_room_list(self, message):
        """Broadcast new message to room list consumers"""
        room_members = await self.get_room_members()
        
        for member_id in room_members:
            if member_id != self.user.id:  # Don't notify sender
                unread_count = await self.get_unread_count_for_user(member_id)
                
                await self.channel_layer.group_send(
                    'room_list_updates',
                    {
                        'type': 'new_message',
                        'room_id': str(self.room_id),
                        'message': {
                            'content': message.content,
                            'sender': self.user.username,
                            'created_at': message.created_at.isoformat(),
                            'message_type': message.message_type
                        },
                        'sender': {
                            'id': self.user.id,
                            'username': self.user.username,
                            'display_name': self.user.get_full_name() or self.user.username,
                        },
                        'unread_count': unread_count,
                        'for_user_id': member_id,
                    }
                )

    async def broadcast_user_status_change(self, action):
        """Broadcast user joining/leaving to room list"""
        await self.channel_layer.group_send(
            'room_list_updates',
            {
                'type': 'room_member_update',
                'room_id': str(self.room_id),
                'action': action,
                'user': {
                    'id': self.user.id,
                    'username': self.user.username,
                    'display_name': self.user.get_full_name() or self.user.username,
                }
            }
        )

    async def broadcast_read_status_update(self):
        """Broadcast read status update to room list"""
        unread_count = await self.get_unread_count_for_user(self.user.id)
        
        await self.channel_layer.group_send(
            f'user_{self.user.id}_room_list',
            {
                'type': 'read_status_update',
                'room_id': str(self.room_id),
                'unread_count': unread_count,
            }
        )

    @database_sync_to_async
    def get_unread_count_for_user(self, user_id):
        try:
            user = User.objects.get(id=user_id)
            room = ChatRoom.objects.get(id=self.room_id)
            return room.get_unread_count_for_user(user)
        except (User.DoesNotExist, ChatRoom.DoesNotExist):
            return 0

    async def send_error(self, message):
        await self.send(text_data=json.dumps({
            'type': 'error',
            'message': message
        }))


class RoomListConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.user = self.scope['user']
        self.room_list_group = 'room_list_updates'
        self.user_room_list_group = f'user_{self.user.id}_room_list'
        
        # Join room list group
        await self.channel_layer.group_add(
            self.room_list_group,
            self.channel_name
        )
        
        # Join user-specific room list group
        await self.channel_layer.group_add(
            self.user_room_list_group,
            self.channel_name
        )
        
        await self.accept()
        
        # Update user activity
        await self.update_user_activity()
        
        # Send initial data
        await self.send_initial_room_data()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(
            self.room_list_group,
            self.channel_name
        )
        
        await self.channel_layer.group_discard(
            self.user_room_list_group,
            self.channel_name
        )

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
            message_type = data.get('type')
            
            if message_type == 'request_room_data':
                await self.send_room_list_data()
            elif message_type == 'mark_room_read':
                await self.mark_room_read(data.get('room_id'))
            elif message_type == 'user_activity':
                await self.update_user_activity()
            elif message_type == 'create_room':
                await self.handle_create_room(data)
                
        except json.JSONDecodeError:
            await self.send_error('Invalid JSON')

    async def send_initial_room_data(self):
        await self.send_room_list_data()

    async def send_room_list_data(self):
        rooms_data = await self.get_user_rooms()
        online_users = await self.get_online_users()
        recent_activities = await self.get_recent_activities()
        
        await self.send(text_data=json.dumps({
            'type': 'room_list_update',
            'rooms': rooms_data,
            'online_users': online_users,
            'recent_activities': recent_activities,
        }))

    async def handle_create_room(self, data):
        """Handle room creation from WebSocket"""
        room = await self.create_room(
            name=data.get('name'),
            room_type=data.get('room_type', 'group'),
            description=data.get('description', '')
        )
        
        if room:
            # Broadcast new room to all users
            await self.channel_layer.group_send(
                'room_list_updates',
                {
                    'type': 'room_created',
                    'room': await self.serialize_room(room),
                    'creator': {
                        'id': self.user.id,
                        'username': self.user.username,
                    }
                }
            )
            
            await self.send(text_data=json.dumps({
                'type': 'room_created',
                'room_id': str(room.id),
                'status': 'success'
            }))
        else:
            await self.send_error('Failed to create room')

    # Event handlers for group messages
    async def new_message(self, event):
        """Handle new message notifications"""
        if event.get('for_user_id') == self.user.id:
            await self.send(text_data=json.dumps({
                'type': 'new_message',
                'room_id': event['room_id'],
                'message': event['message'],
                'sender': event['sender'],
                'unread_count': event['unread_count'],
            }))

    async def room_member_update(self, event):
        """Handle room membership updates"""
        await self.send(text_data=json.dumps({
            'type': 'room_member_update',
            'room_id': event['room_id'],
            'action': event['action'],
            'user': event['user'],
        }))

    async def room_created(self, event):
        """Handle new room creation"""
        await self.send(text_data=json.dumps({
            'type': 'room_created',
            'room': event['room'],
            'creator': event['creator'],
        }))

    async def read_status_update(self, event):
        """Handle read status updates"""
        await self.send(text_data=json.dumps({
            'type': 'read_status_update',
            'room_id': event['room_id'],
            'unread_count': event['unread_count'],
        }))

    async def online_users_update(self, event):
        """Handle online users updates"""
        await self.send(text_data=json.dumps({
            'type': 'online_users_update',
            'online_users': event['online_users'],
        }))

    async def activity_update(self, event):
        """Handle activity updates"""
        await self.send(text_data=json.dumps({
            'type': 'activity_update',
            'recent_activities': event['recent_activities'],
        }))

    # Database operations
    @database_sync_to_async
    def get_user_rooms(self):
        rooms = ChatRoom.objects.for_user(self.user).select_related().prefetch_related(
            'members', 'messages__sender'
        ).annotate(
            member_count=models.Count('members')
        )[:50]  # Limit for performance
        
        rooms_data = []
        for room in rooms:
            # Get last message
            last_message = room.messages.first()
            last_message_data = None
            if last_message:
                last_message_data = {
                    'content': last_message.content,
                    'sender': last_message.sender.username,
                    'created_at': last_message.created_at.isoformat(),
                    'message_type': last_message.message_type,
                }
            
            # Get other user for private chats
            other_user = None
            if room.room_type == 'private':
                other_user_obj = room.get_other_user(self.user)
                if other_user_obj:
                    other_user = {
                        'id': other_user_obj.id,
                        'username': other_user_obj.username,
                        'display_name': other_user_obj.get_full_name() or other_user_obj.username,
                        'is_online': getattr(other_user_obj, 'activity_tracker', None) and 
                                   other_user_obj.activity_tracker.is_recently_active if hasattr(other_user_obj, 'activity_tracker') else False,
                        'avatar_url': None  # Add avatar URL logic here
                    }
            
            room_data = {
                'id': str(room.id),
                'name': room.name,
                'room_type': room.room_type,
                'is_private': room.room_type == 'private',
                'description': room.description,
                'member_count': getattr(room, 'member_count', 0),
                'online_members_count': RealTimeUtils.get_room_online_count(room),
                'unread_count': room.get_unread_count_for_user(self.user),
                'has_unread': room.get_unread_count_for_user(self.user) > 0,
                'last_message': last_message_data,
                'other_user': other_user,
                'created_at': room.created_at.isoformat(),
                'last_activity': room.last_activity.isoformat(),
            }
            rooms_data.append(room_data)
        
        return rooms_data

    @database_sync_to_async
    def get_online_users(self):
        online_users = RealTimeUtils.get_online_users()
        return [{
            'id': user.id,
            'username': user.username,
            'display_name': user.get_full_name() or user.username,
            'avatar_url': None,  # Add avatar URL logic
        } for user in online_users[:20]]  # Limit for performance

    @database_sync_to_async
    def get_recent_activities(self):
        activities = RealTimeUtils.get_recent_activities(limit=10)
        return [{
            'id': str(activity.id),
            'event_type': activity.event_type,
            'user': {
                'id': activity.user.id,
                'username': activity.user.username,
                'display_name': activity.user.get_full_name() or activity.user.username,
            },
            'room': {
                'id': str(activity.room.id),
                'name': activity.room.name,
            },
            'timestamp': activity.created_at.isoformat(),
        } for activity in activities]

    @database_sync_to_async
    def create_room(self, name, room_type='group', description=''):
        if not name.strip():
            return None
        
        try:
            room = ChatRoom.objects.create(
                name=name.strip(),
                room_type=room_type,
                description=description.strip()
            )
            
            # Add creator as member and admin
            room.members.add(self.user)
            room.admins.add(self.user)
            
            # Create membership
            RoomMembership.objects.create(room=room, user=self.user)
            
            # Create chat event
            ChatEvent.objects.create(
                event_type='room_created',
                room=room,
                user=self.user,
                event_data={'name': name, 'type': room_type}
            )
            
            return room
        except Exception as e:
            print(f"Error creating room: {e}")
            return None

    @database_sync_to_async
    def serialize_room(self, room):
        return {
            'id': str(room.id),
            'name': room.name,
            'room_type': room.room_type,
            'description': room.description,
            'member_count': 1,  # Just creator initially
            'online_members_count': 1,
            'unread_count': 0,
            'has_unread': False,
            'last_message': None,
            'created_at': room.created_at.isoformat(),
            'last_activity': room.last_activity.isoformat(),
        }

    @database_sync_to_async
    def mark_room_read(self, room_id):
        if not room_id:
            return
        
        try:
            room = ChatRoom.objects.get(id=room_id)
            if self.user not in room.members.all():
                return
            
            # Mark messages as read
            unread_messages = room.messages.exclude(read_by=self.user).exclude(sender=self.user)
            for message in unread_messages:
                message.read_by.add(self.user)
            
            # Update membership
            membership, created = RoomMembership.objects.get_or_create(
                room=room, user=self.user
            )
            latest_message = room.messages.first()
            if latest_message:
                membership.last_read_message = latest_message
                membership.save()
                
        except ChatRoom.DoesNotExist:
            pass

    @database_sync_to_async
    def update_user_activity(self):
        RealTimeUtils.update_user_activity(self.user)

    async def send_error(self, message):
        await self.send(text_data=json.dumps({
            'type': 'error',
            'message': message
        }))