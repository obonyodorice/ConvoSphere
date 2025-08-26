import json
import asyncio
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth.models import AnonymousUser
from django.utils import timezone
from datetime import timedelta
from .models import ChatRoom, Message, TypingIndicator
from django.contrib.auth import get_user_model

User = get_user_model()

class RoomListConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.user = self.scope["user"]
        if self.user == AnonymousUser():
            await self.close()
            return
            
        # Join user-specific group for personalized updates
        self.user_group = f"user_{self.user.id}"
        await self.channel_layer.group_add(
            self.user_group,
            self.channel_name
        )
        
        # Join general room list updates group
        await self.channel_layer.group_add(
            "room_list_updates",
            self.channel_name
        )
        
        await self.accept()
        
        # Send initial data
        await self.send_room_list_data()
        
        # Start periodic tasks
        await self.start_periodic_updates()

    async def disconnect(self, close_code):
        # Leave groups
        await self.channel_layer.group_discard(
            self.user_group,
            self.channel_name
        )
        await self.channel_layer.group_discard(
            "room_list_updates",
            self.channel_name
        )
        
        # Update user status to offline
        await self.update_user_status(False)

    async def receive(self, text_data):
        data = json.loads(text_data)
        message_type = data.get('type')
        
        if message_type == 'request_room_data':
            await self.send_room_list_data()
        elif message_type == 'mark_room_read':
            room_id = data.get('room_id')
            await self.mark_room_as_read(room_id)
        elif message_type == 'user_activity':
            await self.update_user_activity()

    async def send_room_list_data(self):
        """Send comprehensive room list data"""
        rooms_data = await self.get_user_rooms_data()
        online_users = await self.get_online_users()
        recent_activities = await self.get_recent_activities()
        
        await self.send(text_data=json.dumps({
            'type': 'room_list_update',
            'rooms': rooms_data,
            'online_users': online_users,
            'recent_activities': recent_activities,
            'timestamp': timezone.now().isoformat()
        }))

    async def start_periodic_updates(self):
        """Start background tasks for periodic updates"""
        asyncio.create_task(self.periodic_status_update())
        asyncio.create_task(self.periodic_activity_update())

    async def periodic_status_update(self):
        """Update user status every 30 seconds"""
        while True:
            try:
                await asyncio.sleep(30)
                await self.update_user_activity()
                
                # Send updated online users count
                online_users = await self.get_online_users()
                await self.send(text_data=json.dumps({
                    'type': 'online_users_update',
                    'online_users': online_users
                }))
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"Error in periodic status update: {e}")

    async def periodic_activity_update(self):
        """Send activity updates every 10 seconds"""
        while True:
            try:
                await asyncio.sleep(10)
                recent_activities = await self.get_recent_activities()
                await self.send(text_data=json.dumps({
                    'type': 'activity_update',
                    'recent_activities': recent_activities
                }))
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"Error in periodic activity update: {e}")

    # WebSocket event handlers
    async def new_message_notification(self, event):
        """Handle new message notifications"""
        await self.send(text_data=json.dumps({
            'type': 'new_message',
            'room_id': event['room_id'],
            'message': event['message'],
            'sender': event['sender'],
            'unread_count': event['unread_count'],
            'timestamp': event['timestamp']
        }))

    async def room_member_update(self, event):
        """Handle room member changes"""
        await self.send(text_data=json.dumps({
            'type': 'room_member_update',
            'room_id': event['room_id'],
            'member_count': event['member_count'],
            'online_count': event['online_count'],
            'action': event['action'],  # 'joined' or 'left'
            'user': event['user']
        }))

    async def typing_indicator_update(self, event):
        """Handle typing indicators"""
        await self.send(text_data=json.dumps({
            'type': 'typing_update',
            'room_id': event['room_id'],
            'user': event['user'],
            'is_typing': event['is_typing']
        }))

    async def user_status_change(self, event):
        """Handle user online/offline status changes"""
        await self.send(text_data=json.dumps({
            'type': 'user_status_change',
            'user_id': event['user_id'],
            'username': event['username'],
            'is_online': event['is_online'],
            'last_seen': event.get('last_seen')
        }))

    # Database operations
    @database_sync_to_async
    def get_user_rooms_data(self):
        """Get detailed room data for the user"""
        rooms = self.user.chat_rooms.filter(is_active=True).select_related().prefetch_related(
            'members', 'messages', 'messages__sender'
        ).order_by('-messages__created_at')
        
        rooms_data = []
        for room in rooms:
            # Get last message
            last_message = room.messages.first()
            
            # Calculate unread count
            unread_count = room.messages.exclude(
                read_by=self.user
            ).exclude(sender=self.user).count()
            
            # Get online members count
            online_members = room.members.filter(
                last_activity__gte=timezone.now() - timedelta(minutes=10)
            ).count()
            
            # Get other user for private chats
            other_user = None
            if room.room_type == 'private':
                other_user = room.members.exclude(id=self.user.id).first()
            
            room_data = {
                'id': str(room.id),
                'name': room.name,
                'room_type': room.room_type,
                'member_count': room.members.count(),
                'online_members_count': online_members,
                'unread_count': unread_count,
                'has_unread': unread_count > 0,
                'last_message': {
                    'content': last_message.content[:100] if last_message else None,
                    'sender': last_message.sender.username if last_message else None,
                    'created_at': last_message.created_at.isoformat() if last_message else None,
                    'message_type': last_message.message_type if last_message else 'text'
                } if last_message else None,
                'other_user': {
                    'id': other_user.id,
                    'username': other_user.username,
                    'display_name': other_user.get_full_name() or other_user.username,
                    'is_online': hasattr(other_user, 'last_activity') and 
                               other_user.last_activity >= timezone.now() - timedelta(minutes=10),
                    'avatar_url': other_user.avatar.url if hasattr(other_user, 'avatar') and other_user.avatar else None
                } if other_user else None,
                'created_at': room.created_at.isoformat(),
                'is_private': room.room_type == 'private'
            }
            rooms_data.append(room_data)
        
        return rooms_data

    @database_sync_to_async
    def get_online_users(self):
        """Get list of currently online users"""
        online_threshold = timezone.now() - timedelta(minutes=10)
        online_users = User.objects.filter(
            last_activity__gte=online_threshold
        ).values('id', 'username', 'first_name', 'last_name')
        
        return [
            {
                'id': user['id'],
                'username': user['username'],
                'display_name': f"{user['first_name']} {user['last_name']}".strip() or user['username']
            }
            for user in online_users
        ]

    @database_sync_to_async
    def get_recent_activities(self):
        """Get recent community activities"""
        recent_messages = Message.objects.filter(
            created_at__gte=timezone.now() - timedelta(hours=24)
        ).select_related('sender', 'room').order_by('-created_at')[:10]
        
        activities = []
        for message in recent_messages:
            # Skip if user doesn't have access to this room
            if self.user not in message.room.members.all():
                continue
                
            activities.append({
                'id': str(message.id),
                'type': 'message',
                'user': {
                    'username': message.sender.username,
                    'display_name': message.sender.get_full_name() or message.sender.username
                },
                'room': {
                    'id': str(message.room.id),
                    'name': message.room.name,
                    'room_type': message.room.room_type
                },
                'content': message.content[:100],
                'timestamp': message.created_at.isoformat()
            })
        
        return activities

    @database_sync_to_async
    def mark_room_as_read(self, room_id):
        """Mark all messages in room as read by user"""
        try:
            room = ChatRoom.objects.get(id=room_id)
            if self.user in room.members.all():
                # Mark all unread messages as read
                unread_messages = room.messages.exclude(read_by=self.user)
                for message in unread_messages:
                    message.read_by.add(self.user)
                return True
        except ChatRoom.DoesNotExist:
            pass
        return False

    @database_sync_to_async
    def update_user_activity(self):
        """Update user's last activity timestamp"""
        User.objects.filter(id=self.user.id).update(
            last_activity=timezone.now()
        )

    @database_sync_to_async
    def update_user_status(self, is_online):
        """Update user online status"""
        if not is_online:
            User.objects.filter(id=self.user.id).update(
                last_seen=timezone.now()
            )


class ChatRoomConsumer(AsyncWebsocketConsumer):
    """Enhanced chat room consumer with real-time features"""
    
    async def connect(self):
        self.room_id = self.scope['url_route']['kwargs']['room_id']
        self.room_group_name = f'chat_{self.room_id}'
        self.user = self.scope["user"]
        
        if self.user == AnonymousUser():
            await self.close()
            return
        
        # Check if user has access to room
        has_access = await self.check_room_access()
        if not has_access:
            await self.close()
            return
        
        # Join room group
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        
        await self.accept()
        
        # Notify room list about user joining
        await self.notify_room_list_update('user_joined')
        
        # Send initial room data
        await self.send_room_data()

    async def disconnect(self, close_code):
        # Stop typing indicator
        await self.handle_typing(False)
        
        # Leave room group
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )
        
        # Notify room list about user leaving
        await self.notify_room_list_update('user_left')

    async def receive(self, text_data):
        data = json.loads(text_data)
        message_type = data.get('type')
        
        if message_type == 'chat_message':
            await self.handle_chat_message(data)
        elif message_type == 'typing_indicator':
            await self.handle_typing(data.get('is_typing', False))
        elif message_type == 'mark_read':
            await self.mark_messages_read()

    async def handle_chat_message(self, data):
        """Handle new chat message"""
        message = await self.save_message(data['message'])
        
        if message:
            # Send to room group
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'chat_message',
                    'message': data['message'],
                    'username': self.user.username,
                    'user_id': self.user.id,
                    'message_id': str(message.id),
                    'timestamp': message.created_at.isoformat()
                }
            )
            
            # Notify room list about new message
            await self.notify_room_list_new_message(message)

    async def handle_typing(self, is_typing):
        """Handle typing indicator"""
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'typing_indicator',
                'username': self.user.username,
                'user_id': self.user.id,
                'is_typing': is_typing
            }
        )

    async def notify_room_list_update(self, action):
        """Notify room list about member changes"""
        room = await self.get_room()
        member_count = await self.get_member_count()
        online_count = await self.get_online_member_count()
        
        await self.channel_layer.group_send(
            "room_list_updates",
            {
                'type': 'room_member_update',
                'room_id': self.room_id,
                'member_count': member_count,
                'online_count': online_count,
                'action': action,
                'user': {
                    'id': self.user.id,
                    'username': self.user.username
                }
            }
        )

    async def notify_room_list_new_message(self, message):
        """Notify room list about new message"""
        room = await self.get_room()
        
        # Get unread count for each room member
        for member in await self.get_room_members():
            if member.id != self.user.id:  # Don't notify sender
                unread_count = await self.get_unread_count_for_user(member.id)
                
                await self.channel_layer.group_send(
                    f"user_{member.id}",
                    {
                        'type': 'new_message_notification',
                        'room_id': self.room_id,
                        'message': {
                            'content': message.content[:100],
                            'sender': self.user.username,
                            'message_type': message.message_type
                        },
                        'sender': {
                            'id': self.user.id,
                            'username': self.user.username
                        },
                        'unread_count': unread_count,
                        'timestamp': message.created_at.isoformat()
                    }
                )

    # WebSocket event handlers
    async def chat_message(self, event):
        await self.send(text_data=json.dumps(event))

    async def typing_indicator(self, event):
        # Don't send typing indicator to the typing user
        if event['user_id'] != self.user.id:
            await self.send(text_data=json.dumps(event))

    # Database operations
    @database_sync_to_async
    def check_room_access(self):
        try:
            room = ChatRoom.objects.get(id=self.room_id)
            return self.user in room.members.all()
        except ChatRoom.DoesNotExist:
            return False

    @database_sync_to_async
    def save_message(self, content):
        try:
            room = ChatRoom.objects.get(id=self.room_id)
            message = Message.objects.create(
                room=room,
                sender=self.user,
                content=content
            )
            return message
        except ChatRoom.DoesNotExist:
            return None

    @database_sync_to_async
    def get_room(self):
        return ChatRoom.objects.get(id=self.room_id)

    @database_sync_to_async
    def get_member_count(self):
        room = ChatRoom.objects.get(id=self.room_id)
        return room.members.count()

    @database_sync_to_async
    def get_online_member_count(self):
        room = ChatRoom.objects.get(id=self.room_id)
        online_threshold = timezone.now() - timedelta(minutes=10)
        return room.members.filter(last_activity__gte=online_threshold).count()

    @database_sync_to_async
    def get_room_members(self):
        room = ChatRoom.objects.get(id=self.room_id)
        return list(room.members.all())

    @database_sync_to_async
    def get_unread_count_for_user(self, user_id):
        room = ChatRoom.objects.get(id=self.room_id)
        return room.messages.exclude(read_by__id=user_id).exclude(sender__id=user_id).count()

    @database_sync_to_async
    def mark_messages_read(self):
        room = ChatRoom.objects.get(id=self.room_id)
        unread_messages = room.messages.exclude(read_by=self.user)
        for message in unread_messages:
            message.read_by.add(self.user)