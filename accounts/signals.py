from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth.signals import user_logged_in, user_logged_out
from .models import User, UserActivity

@receiver(post_save, sender=User)
def create_user_profile_activity(sender, instance, created, **kwargs):
    if created:
        UserActivity.objects.create(
            user=instance,
            activity_type='profile_update',
            description='User account created'
        )

@receiver(user_logged_in)
def log_user_login(sender, request, user, **kwargs):
    user.is_online = True
    user.save(update_fields=['is_online'])

@receiver(user_logged_out)
def log_user_logout(sender, request, user, **kwargs):
    if user:
        user.is_online = False
        user.save(update_fields=['is_online'])