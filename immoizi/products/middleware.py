from django.contrib.auth import get_user_model
from django.core import signing

TOKEN_SALT = 'immoizi-auth'
TOKEN_MAX_AGE = 60 * 60 * 24 * 7  # 7 days


def issue_token(user):
    return signing.dumps({'user_id': user.pk}, salt=TOKEN_SALT)


class BearerTokenAuthenticationMiddleware:
    """Authenticates requests carrying an 'Authorization: Bearer <token>' header.

    Tokens are signed user-id payloads issued by the tokenAuth GraphQL mutation,
    letting mobile clients authenticate without cookies/CSRF.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        auth_header = request.headers.get('Authorization', '')
        if auth_header.startswith('Bearer '):
            user = self._authenticate(auth_header[len('Bearer '):].strip())
            if user is not None:
                request.user = user
        return self.get_response(request)

    def _authenticate(self, token):
        try:
            payload = signing.loads(token, salt=TOKEN_SALT, max_age=TOKEN_MAX_AGE)
        except signing.BadSignature:
            return None
        User = get_user_model()
        try:
            return User.objects.get(pk=payload['user_id'], is_active=True)
        except User.DoesNotExist:
            return None
