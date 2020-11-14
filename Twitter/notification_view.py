from django.http import HttpResponse
from django.db import connection
from django.shortcuts import render, redirect
from .auth import auth_or_redirect
from django.urls import reverse

@auth_or_redirect
def notifications_all_view(request):
    user_id = request.session.get("user_id", None)
    #WIP


