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

    def authenticate(self, username=None, password=None):
        try:
            user = User.objects.get(email=username)
            if user.check_password(password):
                return user
            return None
        except (User.DoesNotExist, User.MultipleObjectsReturned):
            return None

    def get_user(self, user_id):
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return None
