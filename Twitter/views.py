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
    user_id = request.session.get("user_id", None)
    username = request.session.get("username", None)

    # All tweets from all people the user follows will be shown in reverse chronological order
    tweetlist = None

    with connection.cursor() as cursor:
        cursor.execute(f'''SELECT T.TWEET_ID ID, P.TEXT, P.MEDIA, P.TIMESTAMP, P.ID POST_ID,
                    (SELECT ACCOUNTNAME FROM ACCOUNT A WHERE A.ID=APP.ACCOUNT_ID) AUTHOR,
                    (SELECT PROFILE_PHOTO FROM ACCOUNT A WHERE A.ID=APP.ACCOUNT_ID) PROFILE_PHOTO
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
                cursor.execute(f"SELECT COUNT(*) FROM ACCOUNT_LIKES_POST WHERE ACCOUNT_ID={user_id} AND POST_ID={tweet['POST_ID']};")
                count = cursor.fetchone()[0]

                if count == 1:
                    tweet["LIKED"] = True

                cursor.execute(f"SELECT COUNT(*) FROM ACCOUNT_BOOKMARKS_POST WHERE ACCOUNT_ID={user_id} AND POST_ID={tweet['POST_ID']};")
                count = cursor.fetchone()[0]

                if count == 1:
                    tweet["BOOKMARKED"] = True

        print("Printing tweetlist: ")
        print(tweetlist)

    if request.POST.get("like", None):
        # We need to fetch post id
        tweetID = int(request.POST.get("postID", None))
        index = int(request.POST.get("indexID", None))

        with connection.cursor() as cursor:
            cursor.execute('''SELECT POST_ID FROM TWEET
                              WHERE TWEET_ID = :tweet_id''', {'tweet_id': tweetID})

            post_id = cursor.fetchone()

            if post_id is None:
                return HttpResponse("No post id found for given tweet id")
            else:
                post_id = post_id[0]

        print("\t Like was called for post ID "+str(post_id)+", index= "+str(index))
        # got user input, now update the database
        with connection.cursor() as cursor:
            # if liked, then unlike, if not liked, then add to like list
            if tweetlist[index].get("LIKED", None):
                cursor.execute(f"DELETE FROM ACCOUNT_LIKES_POST WHERE ACCOUNT_ID={user_id} AND POST_ID={post_id};")
                connection.commit()
                tweetlist[index]["LIKED"] = None

            else:
                cursor.execute(f"INSERT INTO ACCOUNT_LIKES_POST VALUES({user_id}, {post_id});")
                connection.commit()
                tweetlist[index]["LIKED"] = True

    if request.POST.get("bookmark", None):
        tweetID = int(request.POST.get("postID", None))
        index = int(request.POST.get("indexID", None))

        with connection.cursor() as cursor:
            cursor.execute('''SELECT POST_ID FROM TWEET
                              WHERE TWEET_ID = :tweet_id''', {'tweet_id': tweetID})

            post_id = cursor.fetchone()

            if post_id is None:
                return HttpResponse("No post id found for given tweet id")
            else:
                post_id = post_id[0]

        print("\t Bookmark was called for tweet ID " + str(post_id) + ", index= " + str(index))
        # got user input, now update the database
        with connection.cursor() as cursor:
            # if liked, then unlike, if not liked, then add to like list
            if tweetlist[index].get("BOOKMARKED", None):
                cursor.execute(f"DELETE FROM ACCOUNT_BOOKMARKS_POST WHERE ACCOUNT_ID={user_id} AND POST_ID={post_id};")
                connection.commit()
                tweetlist[index]["BOOKMARKED"] = None

            else:
                cursor.execute(f"INSERT INTO ACCOUNT_BOOKMARKS_POST VALUES({user_id}, {post_id});")
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


@auth_or_redirect
def bookmark(request):
    user_id = request.session.get("user_id")
    username = request.session.get("username")

    with connection.cursor() as cursor:
        cursor.execute('''SELECT P.ID POST_ID, P.TIMESTAMP, P.TEXT, P.MEDIA, A.PROFILE_PHOTO, A.ACCOUNTNAME AUTHOR
                           FROM ACCOUNT_BOOKMARKS_POST ALP JOIN POST P
                           ON(ALP.POST_ID = P.ID)
                           JOIN ACCOUNT_POSTS_POST APP
                           ON(P.ID = APP.POST_ID)
                           JOIN ACCOUNT A
                           ON(APP.ACCOUNT_ID = A.ID)
                           WHERE ALP.ACCOUNT_ID = :user_id;''', {'user_id': user_id})

        post_list = dictfetchall(cursor)
        print("Printing bookmarked post for user: " + username)
        print(post_list)

        for post in post_list:
            post["BOOKMARKED"] = True

            cursor.execute(f'''SELECT COUNT(*)
                               FROM ACCOUNT_LIKES_POST
                               WHERE ACCOUNT_ID = :user_id
                               AND POST_ID = :postID;''', {'user_id': user_id, 'postID': post["POST_ID"]})

            count = cursor.fetchone()[0]

            if count == 1:
                post["LIKED"] = True

    template_name = "bookmark.html"
    context = {"post_list": post_list,
               "profile_name": username,
               "bookmark_is_active": True}

    print("Printing overall context! ")
    print(context)

    return render(request, template_name, context)


@auth_or_redirect
def like_bookmark_handler(request):

    print("\tInside like_bookmark_handler!")

    user_id = request.session.get("user_id")

    from django.http import JsonResponse, HttpResponse

    if request.GET:
        like = request.GET.get("like", None)
        bookmark = request.GET.get("bookmark", None)
        post_id = request.GET.get("post_id", None)

        print((like, bookmark, post_id))

        data = {}

        if like and post_id:
            # got user input, now update the database
            with connection.cursor() as cursor:
                # if liked, then unlike, if not liked, then add to like list
                if like == 'like':
                    cursor.execute(f"DELETE FROM ACCOUNT_LIKES_POST WHERE ACCOUNT_ID={user_id} AND POST_ID={post_id};")
                    connection.commit()
                    data['like'] = 'unlike'

                else:
                    cursor.execute(f"INSERT INTO ACCOUNT_LIKES_POST VALUES({user_id}, {post_id});")
                    connection.commit()
                    data['like'] = 'like'

            return JsonResponse(data)

        elif bookmark and post_id:
            # got user input, now update the database
            with connection.cursor() as cursor:
                # if bookmarked, then unbookmark, if not bookmarked, then add to bookmark list
                if bookmark == 'bookmark':
                    cursor.execute(f"DELETE FROM ACCOUNT_BOOKMARKS_POST WHERE ACCOUNT_ID={user_id} AND POST_ID={post_id};")
                    connection.commit()
                    data['bookmark'] = 'unbookmark'

                else:
                    cursor.execute(f"INSERT INTO ACCOUNT_BOOKMARKS_POST VALUES({user_id}, {post_id});")
                    connection.commit()
                    data['bookmark'] = 'bookmark'

            return JsonResponse(data)

        else:
            return HttpResponse("No like or bookmark was handled!")

    return HttpResponse("Invalid URL!")


def dictfetchall(cursor):
    """Return all rows from a cursor as a dict"""
    columns = [col[0] for col in cursor.description]
    return [
        dict(zip(columns, row))
        for row in cursor.fetchall()
    ]
