from django.http import HttpResponse
from django.db import connection
from django.shortcuts import render, redirect
from .auth import auth_or_redirect
from django.urls import reverse


@auth_or_redirect
def message(request):
    user_id = request.session.get("user_id", None)
    username = request.session.get("username", None)

    # This will list all users, and unseen message count
    # and hyperlink to the inbox and chat history to all users
    with connection.cursor() as cursor:
        cursor.execute("SELECT ID, ACCOUNTNAME FROM ACCOUNT WHERE ID <> :user_id;", {'user_id': user_id})
        receiver_list = dictfetchall(cursor)
        print("Printing Receiver list pretty print...")
        print(receiver_list)

        receiver_data = []

        # gets the number of unseen messages for each receiver (users other than the logged in user)
        for receiver in receiver_list:
            receiver_id = receiver['ID']

            cursor.execute('''SELECT COUNT(M.ID)
                             FROM ACCOUNT_SENDS_MESSAGE ASM JOIN ACCOUNT_RECEIVES_MESSAGE ARM
                             ON(ASM.MESSAGE_ID = ARM.MESSAGE_ID)
                             JOIN MESSAGE M
                             ON(ARM.MESSAGE_ID = M.ID)
                             WHERE
                             (ARM.ACCOUNT_ID=:user_id AND ASM.ACCOUNT_ID=:receiver_id)
                             AND M.SEEN IS NULL;''', {'receiver_id': receiver_id, 'user_id': user_id})

            UNSEEN_MSG_COUNT = cursor.fetchone()[0]

            receiver_data.append({
                'NAME': receiver['ACCOUNTNAME'],
                'UNSEEN_MSG_COUNT': UNSEEN_MSG_COUNT
            })

        # receiver_data = dictfetchall(cursor)
        print(receiver_data)

    context = {"user_id": user_id,
               "username": username,
               "receiver_data": receiver_data,
               "messages_is_active": True}

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

        # Mark all messages sent from the receiver as seen
        import datetime
        current_time = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        cursor.execute('''UPDATE MESSAGE
                          SET SEEN = :current_time
                          WHERE ID IN 
                          (SELECT M.ID
                          FROM ACCOUNT_SENDS_MESSAGE ASM JOIN ACCOUNT_RECEIVES_MESSAGE ARM
                          ON(ASM.MESSAGE_ID = ARM.MESSAGE_ID)
                          JOIN MESSAGE M
                          ON(ARM.MESSAGE_ID = M.ID)
                          WHERE ASM.ACCOUNT_ID =:receiver_id AND ARM.ACCOUNT_ID =:user_id
                          AND M.SEEN IS NULL);''',
                       {'receiver_id': receiver_id, 'user_id': user_id, 'current_time': current_time})
        connection.commit()

        cursor.execute(f'''SELECT M.TEXT, M.MEDIA, M.TIMESTAMP, M.SEEN,
                        (SELECT ACCOUNTNAME FROM ACCOUNT A WHERE A.ID=ASM.ACCOUNT_ID) NAME,
                        (SELECT PROFILE_PHOTO FROM ACCOUNT A WHERE A.ID=ASM.ACCOUNT_ID) PROFILE_PHOTO
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
        media = request.FILES.get("file", None)

        if media:
            from django.core.files.storage import FileSystemStorage
            fs = FileSystemStorage()
            media_name = fs.save(media.name, media)
            media = fs.url(media_name)

        with connection.cursor() as cursor:
            data = cursor.callproc('INSERT_MESSAGE',
                                   [username, receiver, chat, media, 'default' * 10, '01-JAN-2020', '01-JAN-2020'])
            if data[4] == 'OK':
                print(data)
                print('Message sent!')
                cursor.execute(f"SELECT PROFILE_PHOTO FROM ACCOUNT WHERE ID={user_id};")
                profile_photo = cursor.fetchone()[0]
                newchat = {'NAME': username,
                           'TEXT': chat,
                           'MEDIA': media,
                           'TIMESTAMP': data[5],
                           'SEEN': data[6],
                           'PROFILE_PHOTO': profile_photo}
                messagelist.append(newchat)
            else:
                print(data[4])
                message = data[4]

    context = {"user_id": user_id,
               "username": username,
               "receiver": receiver,
               "messagelist": messagelist,
               "messages_is_active": True}

    template_name = "inbox.html"
    return render(request, template_name, context)


def dictfetchall(cursor):
    """Return all rows from a cursor as a dict"""
    columns = [col[0] for col in cursor.description]
    return [
        dict(zip(columns, row))
        for row in cursor.fetchall()
    ]
