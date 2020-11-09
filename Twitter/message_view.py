from django.http import HttpResponse
from django.db import connection
from django.shortcuts import render, redirect
from .auth import auth_or_redirect
from django.urls import reverse


@auth_or_redirect
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


@auth_or_redirect
def inbox(request, receiver):
    print("In view of inbox with user " + receiver)

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
            data = cursor.callproc('INSERT_MESSAGE',
                                   (username, receiver, chat, None, 'default' * 10, '01-JAN-2020', '01-JAN-2020'))
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
