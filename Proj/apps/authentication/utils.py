import re
from decouple import config
from rest_framework_simplejwt.tokens import RefreshToken
from ..main.utils import *


class GenerateKey:
    @staticmethod
    def returnValue(phone):
        return str(phone) + config('OTP_SECRET_KEY')


def is_valid_phone(phone):
    return phone and re.compile('^09[0-9]{9,9}$').match(phone)


def get_tokens_for_user(user):
    refresh = RefreshToken.for_user(user)

    return {
        'refresh': str(refresh),
        'access': str(refresh.access_token),
    }
