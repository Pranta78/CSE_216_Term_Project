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
    img_path = 'https://www.facebook.com/images/groups/groups-default-cover-photo-2x.png'

    context = {"img_path": img_path,
               "username": "bla",
               "user_id": 123,
               "Test_is_active": True}

    template_name = "test.html"
    return render(request, template_name, context)


def navbar(request):
    user_id = request.session.get("user_id", None)
    username = request.session.get("username", None)

    context = {"user_id": user_id,
               "username": username}

    template_name = "navbar.html"
    return render(request, template_name, context)


def profile(request):
    user_id = request.session.get("user_id", None)
    username = request.session.get("username", None)

    context = {"user_id": user_id,
               "username": username}

    template_name = "profile.html"
    return render(request, template_name, context)


def skeleton(request):
    user_id = request.session.get("user_id", None)
    username = request.session.get("username", None)

    context = {"user_id": user_id,
               "username": username}

    template_name = "skeleton.html"
    return render(request, template_name, context)


def message(request):
    user_id = request.session.get("user_id", None)
    username = request.session.get("username", None)

    # This will list all users, and hyperlink to the inbox and chat history to all users

    with connection.cursor() as cursor:
        cursor.execute("SELECT ACCOUNTNAME FROM ACCOUNT;")
        row = cursor.fetchall()
        print("Printing User names...")
        print(row)
        userlist = [col[0] for col in row]
        print("Printing User names pretty print...")
        print(userlist)

    context = {"user_id": user_id,
               "username": username,
               "userlist": userlist}

    template_name = "message.html"
    return render(request, template_name, context)


def inbox(request, receiver):
    print("In view of inbox with user "+receiver)

    messagelist = None

    user_id = request.session.get("user_id", None)
    username = request.session.get("username", None)
    message = None

    # This will list all messages with a particular user

    with connection.cursor() as cursor:
        # Retrieving receiver id
        cursor.execute(f"SELECT ID FROM ACCOUNT WHERE ACCOUNTNAME='{receiver}';")
        receiver_id = cursor.fetchone()[0]
        print(receiver_id)
        cursor.execute(f'''SELECT M.TEXT, M.TIMESTAMP, M.SEEN,
                        (SELECT ACCOUNTNAME FROM ACCOUNT A WHERE A.ID=ASM.ACCOUNT_ID) NAME
                        FROM ACCOUNT_SENDS_MESSAGE ASM JOIN ACCOUNT_RECEIVES_MESSAGE ARM
                        ON(ASM.MESSAGE_ID = ARM.MESSAGE_ID)
                        JOIN MESSAGE M
                        ON(ARM.MESSAGE_ID = M.ID)
                        WHERE 
                        (ASM.ACCOUNT_ID={user_id} AND ARM.ACCOUNT_ID={receiver_id})
                        OR
                        (ARM.ACCOUNT_ID={user_id} AND ASM.ACCOUNT_ID={receiver_id})
                        
                        ORDER BY TIMESTAMP ASC;''')

        # row = cursor.fetchall()
        messagelist = dictfetchall(cursor)
        # print(row)
        # userlist = [col[0] for col in row]

    if request.POST:
        chat = request.POST.get('chatbox', None)

        with connection.cursor() as cursor:
            data = cursor.callproc('INSERT_MESSAGE', (username, receiver, chat, None, 'default'*10, '01-JAN-2020', '01-JAN-2020'))
            if data[4] == 'OK':
                print(data)
                print('Message sent!')
                newchat = {'NAME': username,
                           'TEXT': chat,
                           'TIMESTAMP': data[5],
                           'SEEN': data[6]}
                messagelist.append(newchat)
            else:
                print(data[4])
                message = data[4]

    context = {"user_id": user_id,
               "username": username,
               "receiver": receiver,
               "messagelist": messagelist}

    template_name = "inbox.html"
    return render(request, template_name, context)


def dictfetchall(cursor):
    """Return all rows from a cursor as a dict"""
    columns = [col[0] for col in cursor.description]
    return [
        dict(zip(columns, row))
        for row in cursor.fetchall()
    ]
