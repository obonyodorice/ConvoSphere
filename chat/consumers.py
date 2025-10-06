import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.utils import timezone
from .models import ChatRoom, Message, RoomMembership, TypingIndicator
from accounts.models import User


class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.room_id = self.scope['url_route']['kwargs']['room_id']
        self.room_group_name = f'chat_{self.room_id}'
        self.user = self.scope['user']
        
        # Verify user is a member
        if not await self.is_room_member():
            await self.close()
            return
        
        # Join room group
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        
        await self.accept()
        
        # Notify others user joined
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'user_presence',
                'user_id': str(self.user.id),
                'username': self.user.display_name,
                'action': 'joined',
                'is_online': True
            }
        )
    
    async def disconnect(self, close_code):
        # Remove typing indicator
        await self.remove_typing_indicator()
        
        # Notify others user left
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'user_presence',
                'user_id': str(self.user.id),
                'username': self.user.display_name,
                'action': 'left',
                'is_online': False
            }
        )
        
        # Leave room group
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )
    
    async def receive(self, text_data):
        data = json.loads(text_data)
        message_type = data.get('type')
        
        if message_type == 'chat_message':
            await self.handle_chat_message(data)
        elif message_type == 'typing':
            await self.handle_typing(data)
        elif message_type == 'read_receipt':
            await self.handle_read_receipt(data)
        elif message_type == 'reaction':
            await self.handle_reaction(data)
    
    async def handle_chat_message(self, data):
        content = data.get('content', '').strip()
        reply_to_id = data.get('reply_to')
        
        if not content:
            return
        
        # Save message to database
        message = await self.save_message(content, reply_to_id)
        
        # Broadcast to room group
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'chat_message',
                'message': await self.format_message(message)
            }
        )
        
        # Send notifications to mentioned users
        mentions = await self.extract_mentions(content)
        for user_id in mentions:
            await self.send_mention_notification(user_id, message)
    
    async def handle_typing(self, data):
        is_typing = data.get('is_typing', False)
        
        if is_typing:
            await self.add_typing_indicator()
        else:
            await self.remove_typing_indicator()
        
        # Broadcast typing status
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'typing_indicator',
                'user_id': str(self.user.id),
                'username': self.user.display_name,
                'is_typing': is_typing
            }
        )
    
    async def handle_read_receipt(self, data):
        message_id = data.get('message_id')
        if message_id:
            await self.mark_message_read(message_id)
    
    async def handle_reaction(self, data):
        message_id = data.get('message_id')
        emoji = data.get('emoji')
        
        if message_id and emoji:
            reaction = await self.toggle_reaction(message_id, emoji)
            
            # Broadcast reaction update
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'message_reaction',
                    'message_id': message_id,
                    'user_id': str(self.user.id),
                    'username': self.user.display_name,
                    'emoji': emoji,
                    'action': 'added' if reaction else 'removed'
                }
            )
    
    # WebSocket event handlers
    async def chat_message(self, event):
        await self.send(text_data=json.dumps({
            'type': 'chat_message',
            'message': event['message']
        }))
    
    async def user_presence(self, event):
        await self.send(text_data=json.dumps({
            'type': 'user_presence',
            'user_id': event['user_id'],
            'username': event['username'],
            'action': event['action'],
            'is_online': event['is_online']
        }))
    
    async def typing_indicator(self, event):
        # Don't send own typing indicator back
        if event['user_id'] != str(self.user.id):
            await self.send(text_data=json.dumps({
                'type': 'typing_indicator',
                'user_id': event['user_id'],
                'username': event['username'],
                'is_typing': event['is_typing']
            }))
    
    async def message_reaction(self, event):
        await self.send(text_data=json.dumps({
            'type': 'message_reaction',
            'message_id': event['message_id'],
            'user_id': event['user_id'],
            'username': event['username'],
            'emoji': event['emoji'],
            'action': event['action']
        }))
    
    # Database operations
    @database_sync_to_async
    def is_room_member(self):
        try:
            ChatRoom.objects.get(id=self.room_id, members=self.user)
            return True
        except ChatRoom.DoesNotExist:
            return False
    
    @database_sync_to_async
    def save_message(self, content, reply_to_id=None):
        room = ChatRoom.objects.get(id=self.room_id)
        message = Message.objects.create(
            room=room,
            sender=self.user,
            content=content
        )
        
        if reply_to_id:
            try:
                message.reply_to = Message.objects.get(id=reply_to_id)
                message.save()
            except Message.DoesNotExist:
                pass
        
        # Update room timestamp
        room.updated_at = timezone.now()
        room.save()
        
        return message
    
    @database_sync_to_async
    def format_message(self, message):
        return {
            'id': str(message.id),
            'sender': {
                'id': str(message.sender.id),
                'name': message.sender.display_name,
                'avatar': message.sender.avatar.url if message.sender.avatar else None
            },
            'content': message.content,
            'message_type': message.message_type,
            'reply_to': {
                'id': str(message.reply_to.id),
                'sender': message.reply_to.sender.display_name if message.reply_to.sender else 'Unknown',
                'content': message.reply_to.content[:50]
            } if message.reply_to else None,
            'created_at': message.created_at.isoformat(),
        }
    
    @database_sync_to_async
    def extract_mentions(self, content):
        import re
        mentions = re.findall(r'@(\w+)', content)
        user_ids = []
        room = ChatRoom.objects.get(id=self.room_id)
        
        for username in mentions:
            try:
                user = User.objects.get(username=username)
                if user in room.members.all():
                    user_ids.append(str(user.id))
            except User.DoesNotExist:
                pass
        
        return user_ids
    
    @database_sync_to_async
    def add_typing_indicator(self):
        room = ChatRoom.objects.get(id=self.room_id)
        TypingIndicator.objects.update_or_create(
            room=room,
            user=self.user
        )
    
    @database_sync_to_async
    def remove_typing_indicator(self):
        TypingIndicator.objects.filter(
            room_id=self.room_id,
            user=self.user
        ).delete()
    
    @database_sync_to_async
    def mark_message_read(self, message_id):
        try:
            message = Message.objects.get(id=message_id)
            membership = RoomMembership.objects.get(
                room=message.room,
                user=self.user
            )
            membership.last_read_at = timezone.now()
            membership.save()
        except (Message.DoesNotExist, RoomMembership.DoesNotExist):
            pass
    
    @database_sync_to_async
    def toggle_reaction(self, message_id, emoji):
        from .models import MessageReaction
        try:
            message = Message.objects.get(id=message_id)
            reaction, created = MessageReaction.objects.get_or_create(
                message=message,
                user=self.user,
                emoji=emoji
            )
            
            if not created:
                reaction.delete()
                return None
            return reaction
        except Message.DoesNotExist:
            return None
    
    async def send_mention_notification(self, user_id, message):
        pass