from .models import Notification, Message, Profile
from django.db.models import Q


def hub(request):
    """Adds navbar data to every template: unread counts and the profile picture / name for the avatar menu."""
    if request.user.is_authenticated:
        user = request.user
        unread_messages = Message.objects.filter(is_read=False).filter(
            Q(conversation__starter=user) | Q(conversation__other=user)).exclude(sender=user).count()
        profile = Profile.objects.filter(user=user).first()
        full_name = user.get_full_name().strip()
        return {'unread_count': Notification.objects.filter(user=user, is_read=False).count(),
                'unread_messages': unread_messages,
                'nav_avatar': profile.avatar_url if profile else '',
                'nav_name': full_name or user.username,
                'nav_initial': (full_name or user.username)[:1]}
    return {}
