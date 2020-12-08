from django.http import HttpResponse
from django.db import connection
from django.shortcuts import render, redirect
from .auth import auth_or_redirect
from django.urls import reverse

from .notification_view import get_unseen_notif_count


def create_account(request):
    message = ''

    if request.POST:
        if request.POST.get('password') == request.POST.get('confirm_password'):
            with connection.cursor() as cursor:
                email = request.POST.get('email', None)
                username = request.POST.get('username', None)
                password = request.POST.get('password', None)
                birthday = request.POST.get('birthday', None)
                data = cursor.callproc('CREATE_ACCOUNT', [email, username, password, birthday, 'default'*30])
                print(data)
                print(data[4])
                if data[4] != 'OK':
                    message = data[4]
                else:
                    cursor.execute(f"SELECT ID FROM ACCOUNT WHERE ACCOUNTNAME=:username;", {'username': username})
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
            data = cursor.callproc('LOGIN', [username, password, 'default'*30, user_id, 'default'*10])
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
    notification_count = 0
    with connection.cursor() as cursor:
        cursor.execute(f'''SELECT TV.POST_ID, TIMESTAMP, TEXT, MEDIA, PROFILE_PHOTO, AUTHOR, COMMENTLINK
                           FROM TWEET_VIEW TV
                           JOIN FOLLOW_NOTIFICATION FN
                           ON (TV.ACCOUNT_ID = FN.FOLLOWED_ACCOUNT_ID)
                           JOIN ACCOUNT_FOLLOWS_ACCOUNT AFA
                           ON (FN.FOLLOW_NOTIFICATION_ID = AFA.F_NOTIFICATION_ID)
                           WHERE AFA.ACCOUNT_ID = :user_id
                           ORDER BY TV.TIMESTAMP DESC;''', {'user_id': user_id})

        tweetlist = dictfetchall(cursor)

        notification_count = cursor.callfunc("get_unseen_notif_count", int, [user_id])

        for tweet in tweetlist:
            with connection.cursor() as cursor:
                cursor.execute(f"SELECT COUNT(*) FROM ACCOUNT_LIKES_POST WHERE ACCOUNT_ID={user_id} AND POST_ID={tweet['POST_ID']};")
                count = cursor.fetchone()[0]

                if int(count) == 1:
                    tweet["LIKED"] = True

                cursor.execute(f"SELECT COUNT(*) FROM ACCOUNT_BOOKMARKS_POST WHERE ACCOUNT_ID={user_id} AND POST_ID={tweet['POST_ID']};")
                count = cursor.fetchone()[0]

                if int(count) == 1:
                    tweet["BOOKMARKED"] = True

        print("Printing tweetlist: ")
        print(tweetlist)

    context = {"user_id": user_id,
               "username": username,
               "tweet_list": tweetlist,
               "notification_count": notification_count,
               "home_is_active": True,
               "suggestions": fetch_suggested_profile(username)}

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
        cursor.execute('''SELECT TV.POST_ID, TIMESTAMP, TEXT, MEDIA, PROFILE_PHOTO, AUTHOR,
                          COMMENTLINK
                          FROM ACCOUNT_BOOKMARKS_POST ALP JOIN TWEET_VIEW TV
                          ON(ALP.POST_ID = TV.POST_ID)
                          WHERE ALP.ACCOUNT_ID = :user_id;''',
                       {'user_id': user_id})

        tweet_list = dictfetchall(cursor)

        cursor.execute('''SELECT CV.POST_ID, TIMESTAMP, TEXT, MEDIA, PROFILE_PHOTO, AUTHOR,
                          COMMENTLINK, PARENT_COMMENT_LINK, PARENT_TWEET_LINK, "replied_to"
                          FROM ACCOUNT_BOOKMARKS_POST ALP JOIN COMMENT_VIEW CV
                          ON(ALP.POST_ID = CV.POST_ID)
                          WHERE ALP.ACCOUNT_ID = :user_id;''',
                       {'user_id': user_id})

        comment_list = dictfetchall(cursor)

        post_list = tweet_list + comment_list

        print("Printing bookmarked post for user: " + username)
        print(post_list)

        for post in post_list:
            post["BOOKMARKED"] = True

            cursor.execute(f'''SELECT COUNT(*)
                               FROM ACCOUNT_LIKES_POST
                               WHERE ACCOUNT_ID = :user_id
                               AND POST_ID = :postID;''', {'user_id': user_id, 'postID': post["POST_ID"]})

            count = cursor.fetchone()[0]

            if int(count) == 1:
                post["LIKED"] = True

    template_name = "bookmark.html"
    context = {"post_list": post_list,
               "profile_name": username,
               "notification_count": get_unseen_notif_count(user_id),
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
                    #unlike the else branch, this can always be executed as deleting is safe
                    # cursor.execute(f'''
                    #                 DELETE FROM POST_MENTION_NOTIFICATION WHERE POST_MENTION_NOTIFICATION_ID = (
                    #                     SELECT PM_NOTIFICATION_ID FROM ACCOUNT_LIKES_POST WHERE ACCOUNT_ID={user_id} AND POST_ID={post_id}
                    #                 )
                    #                 ''')

                    result = cursor.execute('''
                        SELECT 
                            NOTIFICATION_BASE_ID
                        FROM 
                            POST_MENTION_NOTIFICATION pmn 
                            JOIN ACCOUNT_LIKES_POST alp on(alp.PM_NOTIFICATION_ID = pmn.POST_MENTION_NOTIFICATION_ID)
                        WHERE 
                            alp.POST_ID = %s AND
                            alp.ACCOUNT_ID = %s
                    ''', [post_id, user_id]).fetchone()

                    if result is not None:
                        cursor.execute('''DELETE FROM ACCOUNT_LIKES_POST
                                        WHERE 
                                            POST_ID = %s  AND
                                            ACCOUNT_ID = %s ''', [post_id, user_id])
                        base_notif_id = result[0]
                        cursor.execute("DELETE FROM NOTIFICATION WHERE ID = %s", [base_notif_id])
                        connection.commit()

                    data['like'] = 'unlike'
                    print(f"newly unlike {data}")
                else:
                    #It was still possible to mess with this by logging into the same account on two browsers
                    #the state of the button is unreliable.
                    #pull state from database, attempt to delete post, if one exists.
                    cursor.execute(f"SELECT COUNT(*) FROM ACCOUNT_LIKES_POST WHERE ACCOUNT_ID={user_id} AND POST_ID={post_id};")
                    count = cursor.fetchone()[0]

                    if int(count) == 0:
                        #cursor.execute(f"INSERT INTO ACCOUNT_LIKES_POST VALUES({user_id}, {post_id});")
                        cursor.callproc("INSERT_LIKE_AND_NOTIF", [user_id, post_id])
                        connection.commit()

                    data['like'] = 'like'
                    print(f"newly like {data}")

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

                    cursor.execute(f"SELECT COUNT(*) FROM ACCOUNT_BOOKMARKS_POST WHERE ACCOUNT_ID={user_id} AND POST_ID={post_id};")
                    count = cursor.fetchone()[0]

                    if int(count) == 0:
                        cursor.execute(f"INSERT INTO ACCOUNT_BOOKMARKS_POST VALUES({user_id}, {post_id});")
                        connection.commit()

                    data['bookmark'] = 'bookmark'

            return JsonResponse(data)

        else:
            return HttpResponse("No like or bookmark was handled!")

    return HttpResponse("Invalid URL!")


@auth_or_redirect
def search(request):
    user_id = request.session.get("user_id", None)
    username = request.session.get("username")
    post_list = []
    searchWord = None

    if request.GET.get('q', None):
        searchWord = request.GET.get('q').strip()

        if searchWord:
            search_word = '%' + searchWord + '%'

            with connection.cursor() as cursor:
                cursor.execute('''SELECT TV.POST_ID, TIMESTAMP, TEXT, MEDIA, PROFILE_PHOTO, AUTHOR, COMMENTLINK
                                  FROM TWEET_VIEW TV
                                  WHERE TEXT LIKE :search_word
                                  AND IS_USER_AUDIENCE(:username, TV.POST_ID) = 1
                                  ORDER BY TV.TIMESTAMP DESC;''',
                               {'search_word': search_word, 'username': username})
                tweet_list = dictfetchall(cursor)

                cursor.execute('''SELECT CV.POST_ID, TIMESTAMP, TEXT, MEDIA, PROFILE_PHOTO, AUTHOR,
                                  COMMENTLINK, PARENT_COMMENT_LINK, PARENT_TWEET_LINK, "replied_to"
                                  FROM COMMENT_VIEW CV
                                  WHERE TEXT LIKE :search_word
                                  AND IS_USER_AUDIENCE(:username, CV.POST_ID) = 1
                                  ORDER BY CV.TIMESTAMP DESC;''',
                               {'search_word': search_word, 'username': username})
                comment_list = dictfetchall(cursor)

                post_list = tweet_list + comment_list

                for post in post_list:
                    cursor.execute('''SELECT COUNT(*) FROM ACCOUNT_LIKES_POST
                                      WHERE ACCOUNT_ID=:user_id
                                      AND POST_ID=:post_id;''', {'user_id': user_id, 'post_id': post["POST_ID"]})
                    count = cursor.fetchone()[0]

                    # FOR whatever reason count was a STRING. #BlameOracle
                    if int(count) > 0:
                        post["LIKED"] = True

                    cursor.execute(f'''SELECT COUNT(*) 
                                       FROM ACCOUNT_BOOKMARKS_POST 
                                       WHERE ACCOUNT_ID=:user_id
                                       AND POST_ID=:postID;''', {'user_id': user_id, 'postID': post['POST_ID']})
                    count = cursor.fetchone()[0]

                    if int(count) > 0:
                        post["BOOKMARKED"] = True

                print("Printing posts containing search word: "+searchWord)
                print(post_list)

    template_name = "search.html"
    context = {
        'search_is_active': True,
        'post_list': post_list,
        'search_word': searchWord,
        "notification_count": get_unseen_notif_count(user_id),
    }

    return render(request, template_name, context)


def fetch_suggested_profile(username):
    suggestions = []

    with connection.cursor() as cursor:
        # Suggest the profile of people followed by the user's following people
        # Avoid suggesting the profile of current user, and people he already follows
        cursor.execute('''SELECT A.ACCOUNTNAME, A.PROFILE_PHOTO, F1.FOLLOWER
                          FROM ACCOUNT A JOIN FOLLOWER F1
                          ON (F1.FOLLOWED = A.ACCOUNTNAME)
                          JOIN FOLLOWER F2
                          ON (F1.FOLLOWER = F2.FOLLOWED)
                          WHERE F2.FOLLOWER = :username
                          AND F1.FOLLOWED <> :username
                          AND F1.FOLLOWED NOT IN
                            (SELECT FOLLOWED
                            FROM FOLLOWER
                            WHERE FOLLOWER = :username
                            );''',
                       {'username': username})

        suggestions = dictfetchall(cursor)

        # Suggest profiles of people with the most followers
        # Avoid suggesting the profile of current user, and people he already follows
        cursor.execute('''SELECT A.ACCOUNTNAME, A.PROFILE_PHOTO
                          FROM ACCOUNT A JOIN FOLLOWER F
                          ON(A.ACCOUNTNAME = F.FOLLOWED)
                          WHERE F.FOLLOWED <> :username
                          AND F.FOLLOWED NOT IN
                            (SELECT FOLLOWED
                            FROM FOLLOWER
                            WHERE FOLLOWER = :username
                            )
                          GROUP BY F.FOLLOWED, A.ACCOUNTNAME, A.PROFILE_PHOTO
                          ORDER BY COUNT(F.FOLLOWER) DESC;''',
                       {'username': username})

        temp = dictfetchall(cursor)

        # check for duplicate user names
        for temp_suggestion in temp:
            if temp_suggestion["ACCOUNTNAME"] not in [suggestion["ACCOUNTNAME"] for suggestion in suggestions]:
                suggestions.append(temp_suggestion)

        # Suggest profiles of people who follow the current user
        # Avoid suggesting the profile of current user, and people he already follows
        cursor.execute('''SELECT A.ACCOUNTNAME, A.PROFILE_PHOTO, F.FOLLOWER FOLLOWS
                          FROM ACCOUNT A JOIN FOLLOWER F
                          ON (A.ACCOUNTNAME = F.FOLLOWER)
                          WHERE F.FOLLOWED = :username
                          AND F.FOLLOWER <> :username
                          AND F.FOLLOWER NOT IN
                              (SELECT FOLLOWED
                              FROM FOLLOWER
                              WHERE FOLLOWER = :username);''',
                       {'username': username})

        temp = dictfetchall(cursor)

        for temp_suggestion in temp:
            if temp_suggestion["ACCOUNTNAME"] not in [suggestion["ACCOUNTNAME"] for suggestion in suggestions]:
                suggestions.append(temp_suggestion)

        # Suggest profiles of people with no followers
        # Avoid suggesting the profile of current user, and people he already follows
        cursor.execute('''SELECT A.ACCOUNTNAME, A.PROFILE_PHOTO
                          FROM ACCOUNT A 
                          WHERE A.ACCOUNTNAME <> :username
                          AND A.ACCOUNTNAME NOT IN
                              (SELECT FOLLOWED
                              FROM FOLLOWER
                              WHERE FOLLOWER = :username
                              );''',
                       {'username': username})

        temp = dictfetchall(cursor)

        for temp_suggestion in temp:
            if temp_suggestion["ACCOUNTNAME"] not in [suggestion["ACCOUNTNAME"] for suggestion in suggestions]:
                suggestions.append(temp_suggestion)

        print("Printing suggestions for user: "+username)
        print(suggestions)

    return suggestions


def dictfetchall(cursor):
    """Return all rows from a cursor as a dict"""
    columns = [col[0] for col in cursor.description]
    return [
        dict(zip(columns, row))
        for row in cursor.fetchall()
    ]
