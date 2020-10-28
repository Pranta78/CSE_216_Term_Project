from django.http import HttpResponse
from django.db import connection
from django.shortcuts import render, redirect


def create_account(request):
    message = None
    context = {"message": message}
    template_name = "create_account.html"

    print(request.POST)
    print(type(request.POST.get("birthday", None)))

    return render(request, template_name, context)


def login(request):
    message = ''

    with connection.cursor() as cursor:
        data = 'data'
        username = request.POST.get('uname', None)
        password = request.POST.get('pname', None)
        if username and password:
            data = cursor.callproc('auth', (username, password, data))
            if data[2] == 'OK':
                print('You ARE authenticated!')
                message = 'You ARE authenticated!'
                request.session['username'] = username
                return redirect("/home/")
            else:
                print('Invalid username or password!')
                message = 'Invalid username or password!'

    context = {'username': username,
               'message': message}

    return render(request, "login.html", context)
