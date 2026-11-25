# -*- coding: utf-8 -*-


from django.contrib.auth.models import User


class EmailBackend:
    """
    Authenticate against the email field as if it were the username.

    This allows the same call to be used against either the email or
    username column since the same paramter signature is used for
    both backents.  Which means that one indexer who already uses his/her
    email address for a username could log in both ways, but that's not
    really a problem.

    NOTE: Before Django 1.2, the username field could not contain
    an @ symbol, and even now (Django 1.4) it is limited to 30 characters
    which is insufficient for a number of users.  This works around
    those limitations.
    """

    def authenticate(self, request, username=None, password=None):
        try:
            user = User.objects.get(email=username)
            if user.check_password(password):
                return user
            return None
        except (User.DoesNotExist, User.MultipleObjectsReturned):
            return None

    def get_user(self, user_id):
        """
        Return the user of a session, or None for an account that is not
        active, as Django's ModelBackend does, so that its session ends.
        """
        try:
            return User.objects.get(pk=user_id, is_active=True)
        except User.DoesNotExist:
            return None
