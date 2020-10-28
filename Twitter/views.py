from django.http import HttpResponse
from django.db import connection
from django.shortcuts import render, redirect


def create_account(request):
    message = ''

    if request.POST:
        if request.POST.get('password') == request.POST.get('confirm_password'):
            with connection.cursor() as cursor:
                email = request.POST.get('email', None)
                username = request.POST.get('username', None)
                password = request.POST.get('password', None)
                birthday = request.POST.get('birthday', None)
                data = cursor.callproc('CREATE_ACCOUNT', (email, username, password, birthday, 'default'*30))
                print(data)
                print(data[4])
                if data[4] != 'OK':
                    message = data[4]
                else:
                    cursor.execute(f"SELECT ID FROM ACCOUNT WHERE ACCOUNTNAME='{username}';")
                    row = cursor.fetchall()
                    print("Printing fetch all...")
                    print(row)
                    user_id = row[0][0]
                    print("Printing ID...")
                    print(user_id)
                    request.session['user_id'] = user_id
                    request.session['username'] = username
                    return redirect("/home/")
        else:
            message = 'Password and Confirm Password field don\'t match'

    context = {"message": message}
    template_name = "create_account.html"

    return render(request, template_name, context)


def login(request):
    message = ''
    user_id = 0

    username = None
    password = None

    if request.POST:
        username = request.POST.get('username', None)
        password = request.POST.get('password', None)

        with connection.cursor() as cursor:
            data = cursor.callproc('LOGIN', (username, password, 'default'*30, user_id, 'default'*10))
            if data[2] == 'OK':
                print(data)
                print('You ARE authenticated!')
                request.session['user_id'] = data[3]
                request.session['username'] = data[4]
                return redirect("/home/")
            else:
                print('Invalid username or password!')
                message = 'Invalid username or password!'

    context = {'username': username,
               'message': message}
    template_name = "Login.html"

    return render(request, template_name, context)


def logout(request):
    print("logging you out!")
    try:
        del request.session['user_id']
        del request.session['username']
    except KeyError:
        print('Key Error in Logout!')
    return redirect("/login")


def home_page(request):
    user_id = request.session.get("user_id", None)
    username= request.session.get("username", None)

    context = {"user_id": user_id,
               "username": username}

    template_name = "home_page.html"

    return render(request, template_name, context)


def profile_edit(request):
    profile_photo = None
    header_photo = None

    if request.POST:
        print('Printing POST request...')
        print(request.POST)

    if request.FILES:
        print('Printing files...')
        print(request.FILES)
        profile_photo = request.FILES.get("profile_photo", None)
        header_photo = request.FILES.get("header_photo", None)

    template_name = "image-upload.html"
    context = {"profile_photo": profile_photo,
               "header_photo": header_photo}

    return render(request, template_name, context)


def test(request):
    img_path = 'file:///D:/twitter/download.png'
    context = {"img_path": img_path}
    template_name = "test.html"
    return render(request, template_name, context)
