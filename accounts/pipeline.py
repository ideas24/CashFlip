"""
Social Auth Pipeline - creates PlayerProfile after social login
"""


def create_player_profile(backend, user, response, *args, **kwargs):
    from accounts.models import PlayerProfile
    PlayerProfile.objects.get_or_create(player=user)
