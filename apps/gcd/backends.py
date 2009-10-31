from django.contrib.auth.models import User, check_password

class EmailBackend:
    """
    Authenticate against the email field as if it were the username.

    This allows the same call to be used against either the email or
    username column since the same paramter signature is used for
    both backents.  Which means that one indexer who already uses his/her
    email address for a username could log in both ways, but that's not
    really a problem.
    """

    def authenticate(self, username=None, password=None):
        try:
            user = User.objects.get(email=username)
            if check_password(password, user.password):
                return user
            return None
        except (User.DoesNotExist, User.MultipleObjectsReturned):
            return None

    def get_user(self, user_id):
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return None

