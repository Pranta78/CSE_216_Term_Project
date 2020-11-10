from django.http import HttpResponse
from django.db import connection
from django.shortcuts import render, redirect
from .auth import auth_or_redirect
from django.urls import reverse


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


@auth_or_redirect
def logout(request):
    print("logging you out!")
    try:
        del request.session['user_id']
        del request.session['username']
    except KeyError:
        print('Key Error in Logout!')
    return redirect("/login")


@auth_or_redirect
def home_page(request):
    # user_id = request.session.get("user_id", None)
    # username= request.session.get("username", None)
    #
    # context = {"user_id": user_id,
    #            "username": username}
    #
    # template_name = "home_page.html"

    user_id = request.session.get("user_id", None)
    username = request.session.get("username", None)

    # All tweets from all people the user follows will be shown in reverse chronological order
    tweetlist = None

    with connection.cursor() as cursor:
        cursor.execute(f'''SELECT P.ID, P.TEXT, P.TIMESTAMP,
                    (SELECT ACCOUNTNAME FROM ACCOUNT A WHERE A.ID=APP.ACCOUNT_ID) AUTHOR
                    FROM POST P JOIN TWEET T
                    ON (P.ID = T.POST_ID)
                    JOIN ACCOUNT_POSTS_POST	APP
                    ON (T.POST_ID = APP.POST_ID)
                    JOIN FOLLOW_NOTIFICATION FN
                    ON (APP.ACCOUNT_ID = FN.FOLLOWED_ACCOUNT_ID)
                    JOIN ACCOUNT_FOLLOWS_ACCOUNT AFA
                    ON (FN.FOLLOW_NOTIFICATION_ID = AFA.F_NOTIFICATION_ID)
                    WHERE AFA.ACCOUNT_ID = {user_id}
                    ORDER BY P.TIMESTAMP DESC;''')

        tweetlist = dictfetchall(cursor)
        for tweet in tweetlist:
            with connection.cursor() as cursor:
                cursor.execute(f"SELECT COUNT(*) FROM ACCOUNT_LIKES_POST WHERE ACCOUNT_ID={user_id} AND POST_ID={tweet['ID']};")
                count = cursor.fetchone()[0]

                if count == 1:
                    tweet["LIKED"] = True

                cursor.execute(f"SELECT COUNT(*) FROM ACCOUNT_BOOKMARKS_POST WHERE ACCOUNT_ID={user_id} AND POST_ID={tweet['ID']};")
                count = cursor.fetchone()[0]

                if count == 1:
                    tweet["BOOKMARKED"] = True

        print("Printing tweetlist: ")
        print(tweetlist)

    if request.POST.get("like", None):
        tweetID = int(request.POST.get("postID", None))
        index = int(request.POST.get("indexID", None))
        print("\t Like was called for tweet ID "+str(tweetID)+", index= "+str(index))
        # got user input, now update the database
        with connection.cursor() as cursor:
            # if liked, then unlike, if not liked, then add to like list
            if tweetlist[index].get("LIKED", None):
                cursor.execute(f"DELETE FROM ACCOUNT_LIKES_POST WHERE ACCOUNT_ID={user_id} AND POST_ID={tweetID};")
                connection.commit()
                tweetlist[index]["LIKED"] = None

            else:
                cursor.execute(f"INSERT INTO ACCOUNT_LIKES_POST VALUES({user_id}, {tweetID});")
                connection.commit()
                tweetlist[index]["LIKED"] = True

    if request.POST.get("bookmark", None):
        tweetID = int(request.POST.get("postID", None))
        index = int(request.POST.get("indexID", None))
        print("\t Bookmark was called for tweet ID " + str(tweetID) + ", index= " + str(index))
        # got user input, now update the database
        with connection.cursor() as cursor:
            # if liked, then unlike, if not liked, then add to like list
            if tweetlist[index].get("BOOKMARKED", None):
                cursor.execute(f"DELETE FROM ACCOUNT_BOOKMARKS_POST WHERE ACCOUNT_ID={user_id} AND POST_ID={tweetID};")
                connection.commit()
                tweetlist[index]["BOOKMARKED"] = None

            else:
                cursor.execute(f"INSERT INTO ACCOUNT_BOOKMARKS_POST VALUES({user_id}, {tweetID});")
                connection.commit()
                tweetlist[index]["BOOKMARKED"] = True

    context = {"user_id": user_id,
               "username": username,
               "tweet_list": tweetlist,
               "home_is_active": True}

    template_name = "home.html"

    return render(request, template_name, context)


def skeleton(request):
    user_id = request.session.get("user_id", None)
    username = request.session.get("username", None)

    context = {"user_id": user_id,
               "username": username}

    template_name = "skeleton.html"
    return render(request, template_name, context)


def dictfetchall(cursor):
    """Return all rows from a cursor as a dict"""
    columns = [col[0] for col in cursor.description]
    return [
        dict(zip(columns, row))
        for row in cursor.fetchall()
    ]
