# utility class for authentication, provides a simple function for quick login redirect
# just put the decorator auth_or_redirect on top of view functions that require auth
# cleaner and doesn't involve templates
# and doesn't work against post requests that require authentication

# I also recommend moving login logout logic here. But that's on you.

from django.http import HttpResponse
from django.db import connection
from django.shortcuts import render, redirect
from django.urls import reverse


def is_user_authenticated(request):
    return request.session.get("user_id", None) is not None


def auth_or_redirect(func):
    def auth_wrapper(request, *args, **kwargs):
        # can't use the is_user_authenticated function here due to circular dependency issue
        if request.session.get("user_id", None) is None:
            return redirect(reverse('login'))
        return func(request, *args, **kwargs)

    return auth_wrapper

@auth_or_redirect
def deco_test(request):
    return HttpResponse("logged in")




