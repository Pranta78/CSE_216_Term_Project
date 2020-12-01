from django.http import HttpResponse
from django.db import connection
from django.shortcuts import render, redirect
from .auth import auth_or_redirect, is_user_authenticated
from django.urls import reverse

from .notification_view import get_unseen_notif_count


@auth_or_redirect
def profile_edit(request):
    user_id = request.session.get("user_id")
    username = request.session.get("username")

    with connection.cursor() as cursor:
        cursor.execute('''SELECT DATE_OF_BIRTH, BIO, PROFILE_PHOTO, HEADER_PHOTO
                           FROM ACCOUNT WHERE ID = :user_id;''', {'user_id': user_id})

        (current_dob, current_bio, current_profile_photo, current_header_photo) = cursor.fetchone()

        print("Printing bio, pp and hp")
        print((current_dob, current_bio, current_profile_photo, current_header_photo))

    from django.core.files.storage import FileSystemStorage

    (dob, bio, profile_photo, header_photo) = (current_dob, current_bio, current_profile_photo, current_header_photo)
    message = None
    redirection_confirm = True

    if request.POST:
        currentpassword = request.POST.get("currentPassword", None)
        newPassword = request.POST.get("newPassword", None)
        confirmPassword = request.POST.get("confirmPassword", None)

        print("Printing pass values")
        print((currentpassword, newPassword, confirmPassword))

        dob = request.POST.get('birthday', None)
        bio = request.POST.get("bio", None)
        profile_photo = request.FILES.get("profile_photo", None)
        header_photo = request.FILES.get("header_photo", None)

        fs = FileSystemStorage()

        if currentpassword:
            with connection.cursor() as cursor:
                data = cursor.callproc('LOGIN', (username, currentpassword, 'default' * 30, 999, 'default' * 10))
                if data[2] != 'OK':
                    message = 'Password is incorrect!'
                    redirection_confirm = None
                else:
                    if newPassword and confirmPassword:
                        if newPassword != confirmPassword:
                            message = 'New password and Confirm password don\'t match'
                            redirection_confirm = None
                        else:
                            cursor.execute("SELECT EMAIL FROM ACCOUNT WHERE ACCOUNTNAME=:username", {'username': username})
                            email = cursor.fetchone()[0]
                            cursor.execute('''UPDATE ACCOUNT
                                              SET PASSWORD = HASH_PASSWORD(:email, :username, :newPassword)
                                              WHERE ACCOUNTNAME = :username;''',
                                           {'email': email, 'username': username, 'newPassword': newPassword})
                    else:
                        message = 'Password cannot be empty!'
                        redirection_confirm = None

        if redirection_confirm:
            if bio is None:
                bio = current_bio

            if dob is None:
                dob = current_dob

            if profile_photo:
                profile_photo_name = fs.save(profile_photo.name, profile_photo)
                profile_photo = fs.url(profile_photo_name)
            else:
                profile_photo = current_profile_photo

            if header_photo:
                header_photo_name = fs.save(header_photo.name, header_photo)
                header_photo = fs.url(header_photo_name)
            else:
                header_photo = current_header_photo

            print("Updating bio, pp, hp for following data")
            print((bio, profile_photo, header_photo, user_id))

            with connection.cursor() as cursor:
                named_params = {'dob': dob, 'bio': bio, 'profile_photo': profile_photo, 'header_photo': header_photo, 'user_id': user_id}

                cursor.execute('''UPDATE ACCOUNT
                                SET BIO = :bio,
                                    DATE_OF_BIRTH = :dob,
                                    PROFILE_PHOTO = :profile_photo,
                                    HEADER_PHOTO = :header_photo
                                WHERE ID = :user_id;''', named_params)
                connection.commit()

            return redirect(reverse('user_profile', args=[username]))

    template_name = "profile_edit.html"
    context = {'bio': bio,
               'profile_photo': profile_photo,
               'header_photo': header_photo,
               "profile_is_active": True,
               "notification_count": get_unseen_notif_count(user_id),
               "message": message}

    return render(request, template_name, context)


@auth_or_redirect
def profile(request):
    user_id = request.session.get("user_id", None)
    username = request.session.get("username", None)

    return redirect(reverse('user_profile', args=[username]))


@auth_or_redirect
def user_profile(request, profilename):
    # shows profile for any particular user
    user_id = request.session.get("user_id", None)
    username = request.session.get("username", None)

    context = populateProfile(profilename, username, user_id)

    if request.POST.get("follow", None):
        context["follows_user"] = follow_handler(request.POST.get("follow"), username, profilename, user_id, context["profile_id"])
        context["follower_count"], context["following_count"] = populateFollowInfo(profilename)

    template_name = "profile.html"
    return render(request, template_name, context)


def populateProfile(profilename, username, user_id):
    "Returns all context variables a profile should have"

    if profilename != username:
        # will be used to replace follow button with profile edit one
        self_profile = None

        with connection.cursor() as cursor:
            cursor.execute("SELECT ID FROM ACCOUNT WHERE ACCOUNTNAME = :profilename;", {"profilename": profilename})
            row = cursor.fetchone()

            if len(row) == 0:
                return HttpResponse("<h2>Invalid User profile!</h2>")
            else:
                profile_id = row[0]

        # The follow button will be disabled if the profile user is followed by the logged in user!
        follows_user = None

        with connection.cursor() as cursor:
            cursor.execute('''SELECT COUNT(*)
                                FROM ACCOUNT_FOLLOWS_ACCOUNT
                                WHERE ACCOUNT_ID = :user_id
                                AND 
                                F_NOTIFICATION_ID = 
                                    (SELECT FOLLOW_NOTIFICATION_ID
                                    FROM FOLLOW_NOTIFICATION
                                    WHERE FOLLOWED_ACCOUNT_ID = :profile_id);''', {'user_id': user_id, 'profile_id': profile_id})
            row = cursor.fetchone()

            # if user is visiting his own profile
            if int(row[0]) != 0 or (username == profilename):
                follows_user = True

    # user is visiting his own profile
    else:
        follows_user = True
        profile_id = user_id
        self_profile = True

    # fetch bio, profile photo and header photo
    profile_photo = ''
    header_photo = ''
    bio = ''

    with connection.cursor() as cursor:
        cursor.execute('''SELECT BIO, PROFILE_PHOTO, HEADER_PHOTO
                           FROM ACCOUNT WHERE ID = :profile_id;''', {'profile_id': profile_id})

        (bio, profile_photo, header_photo) = cursor.fetchone()

        follower_count, following_count = populateFollowInfo(profilename)

        print("Printing bio, pp and hp")
        print((bio, profile_photo, header_photo))

    context = {"user_id": user_id,
               "username": username,
               "profile_id": profile_id,
               "profile_name": profilename,
               "follows_user": follows_user,
               'bio': bio,
               'profile_photo': profile_photo,
               'header_photo': header_photo,
               'self_profile': self_profile,
               "profile_is_active": True,
               "follower_count": follower_count,
               "notification_count": get_unseen_notif_count(user_id),
               "following_count": following_count}

    return context


def populateFollowInfo(profilename):
    with connection.cursor() as cursor:
        cursor.execute('''SELECT COUNT(FOLLOWER) FROM FOLLOWER
                                 WHERE FOLLOWED = :followed_name;''', {'followed_name': profilename})

        follower_count = cursor.fetchone()[0]

        cursor.execute('''SELECT COUNT(FOLLOWED) FROM FOLLOWER
                                         WHERE FOLLOWER = :follower_name;''', {'follower_name': profilename})

        following_count = cursor.fetchone()[0]

    return follower_count, following_count


@auth_or_redirect
def viewLikedPosts(request, profilename):
    """
    This will fetch all posts' info which were liked by the given user name
    :param username: a user name
    :return: a list of dictionaries with key id, time, text, media, author's profile picture
            containing containing all posts which were liked by the user
    """
    user_id = request.session.get("user_id")
    username = request.session.get("username")

    parent_context = populateProfile(profilename, username, user_id)

    with connection.cursor() as cursor:
        cursor.execute("SELECT ID FROM ACCOUNT WHERE ACCOUNTNAME= :profilename;", {'profilename': profilename})

        profile_id = cursor.fetchone()

        if profile_id is None:
            return HttpResponse("User not found!")

        profile_id = profile_id[0]

        # IS_USER_AUDIENCE function is called to check whether the visitor (with username as user name)
        # has sufficient permission to see the post

        # cursor.execute('''SELECT P.ID POST_ID, P.TIMESTAMP, P.TEXT, P.MEDIA, A.PROFILE_PHOTO, A.ACCOUNTNAME AUTHOR
        #                    FROM ACCOUNT_LIKES_POST ALP JOIN POST P
        #                    ON(ALP.POST_ID = P.ID)
        #                    JOIN ACCOUNT_POSTS_POST APP
        #                    ON(P.ID = APP.POST_ID)
        #                    JOIN ACCOUNT A
        #                    ON(APP.ACCOUNT_ID = A.ID)
        #                    WHERE ALP.ACCOUNT_ID = :profile_id
        #                    AND IS_USER_AUDIENCE(:username, P.ID) = 1;''', {'profile_id': profile_id, 'username': username})

        cursor.execute('''SELECT TV.POST_ID, TIMESTAMP, TEXT, MEDIA, PROFILE_PHOTO, AUTHOR,
                          COMMENTLINK
                          FROM ACCOUNT_LIKES_POST ALP JOIN TWEET_VIEW TV
                          ON(ALP.POST_ID = TV.POST_ID)
                          WHERE ALP.ACCOUNT_ID = :profile_id
                          AND IS_USER_AUDIENCE(:username, TV.POST_ID) = 1;''',
                       {'profile_id': profile_id, 'username': username})

        tweet_list = dictfetchall(cursor)

        cursor.execute('''SELECT CV.POST_ID, TIMESTAMP, TEXT, MEDIA, PROFILE_PHOTO, AUTHOR,
                          COMMENTLINK, PARENT_COMMENT_LINK, PARENT_TWEET_LINK, "replied_to"
                          FROM ACCOUNT_LIKES_POST ALP JOIN COMMENT_VIEW CV
                          ON(ALP.POST_ID = CV.POST_ID)
                          WHERE ALP.ACCOUNT_ID = :profile_id
                          AND IS_USER_AUDIENCE(:username, CV.POST_ID) = 1;''',
                       {'profile_id': profile_id, 'username': username})

        comment_list = dictfetchall(cursor)

        post_list = tweet_list + comment_list

        print("Printing liked post for user: " + profilename)
        print(post_list)

        for post in post_list:
            cursor.execute(f'''SELECT COUNT(*)
                               FROM ACCOUNT_LIKES_POST
                               WHERE ACCOUNT_ID = :user_id
                               AND POST_ID = :postID;''',
                           {'user_id': user_id, 'postID': post["POST_ID"]})

            count = cursor.fetchone()[0]

            if int(count) == 1:
                post["LIKED"] = True

            cursor.execute(f'''SELECT COUNT(*)
                               FROM ACCOUNT_BOOKMARKS_POST
                               WHERE ACCOUNT_ID = :user_id
                               AND POST_ID = :postID;''',
                           {'user_id': user_id, 'postID': post["POST_ID"]})

            count = cursor.fetchone()[0]

            if int(count) == 1:
                post["BOOKMARKED"] = True

    template_name = "tweets.html"
    child_context = {"post_list": post_list,
                     "likes_is_active": True,
                     "profile_name": profilename}

    context = {**parent_context, **child_context}

    if request.POST.get("follow", None):
        context["follows_user"] = follow_handler(request.POST.get("follow"), username, profilename, user_id, profile_id)
        context["follower_count"], context["following_count"] = populateFollowInfo(profilename)

    print("Printing overall context! ")
    print(context)

    return render(request, template_name, context)


@auth_or_redirect
def viewPostedTweets(request, profilename):
    # loads all tweets posted by the user
    user_id = request.session.get("user_id")
    username = request.session.get("username")

    parent_context = populateProfile(profilename, username, user_id)

    with connection.cursor() as cursor:
        cursor.execute("SELECT ID FROM ACCOUNT WHERE ACCOUNTNAME=:profilename;", {'profilename': profilename})

        profile_id = cursor.fetchone()

        if profile_id is None:
            return HttpResponse("User not found!")

        profile_id = profile_id[0]

        # cursor.execute('''SELECT T.TWEET_ID ID, P.ID POST_ID, P.TIMESTAMP, P.TEXT, P.MEDIA, A.PROFILE_PHOTO, A.ACCOUNTNAME AUTHOR
        #                   FROM TWEET T JOIN POST P
        #                   ON(T.POST_ID = P.ID)
        #                   JOIN ACCOUNT_POSTS_POST APP
        #                   ON(P.ID = APP.POST_ID)
        #                   JOIN ACCOUNT A
        #                   ON(APP.ACCOUNT_ID = A.ID)
        #                   WHERE APP.ACCOUNT_ID = :profile_id
        #                   AND IS_USER_AUDIENCE(:username, P.ID) = 1
        #                   ORDER BY P.TIMESTAMP DESC;''', {'profile_id': profile_id, 'username': username})

        cursor.execute('''SELECT TV.POST_ID, TIMESTAMP, TEXT, MEDIA, PROFILE_PHOTO, AUTHOR, COMMENTLINK
                          FROM TWEET_VIEW TV
                          WHERE ACCOUNT_ID = :profile_id
                          AND IS_USER_AUDIENCE(:username, TV.POST_ID) = 1
                          ORDER BY TV.TIMESTAMP DESC;''',
                       {'profile_id': profile_id, 'username': username})

        post_list = dictfetchall(cursor)
        print("Printing posted tweets for user: " + profilename)
        print(post_list)

        for post in post_list:
            cursor.execute('''SELECT COUNT(*) FROM ACCOUNT_LIKES_POST
                              WHERE ACCOUNT_ID=:user_id
                              AND POST_ID=:post_id;''', {'user_id': user_id, 'post_id': post["POST_ID"]})
            count = cursor.fetchone()[0]

            if int(count) == 1:
                post["LIKED"] = True

            cursor.execute(f'''SELECT COUNT(*) 
                               FROM ACCOUNT_BOOKMARKS_POST 
                               WHERE ACCOUNT_ID=:user_id
                               AND POST_ID=:postID;''', {'user_id': user_id, 'postID': post['POST_ID']})
            count = cursor.fetchone()[0]

            if int(count) == 1:
                post["BOOKMARKED"] = True

    template_name = "tweets.html"
    child_context = {"post_list": post_list,
                     "tweet_is_active": True,
                     "profile_name": profilename}

    context = {**parent_context, **child_context}

    if request.POST.get("follow", None):
        context["follows_user"] = follow_handler(request.POST.get("follow"), username, profilename, user_id, profile_id)
        context["follower_count"], context["following_count"] = populateFollowInfo(profilename)

    print("Printing overall context! ")
    print(context)

    return render(request, template_name, context)


@auth_or_redirect
def viewTweetMedia(request, profilename):
    # loads all posts containing media posted by the user
    user_id = request.session.get("user_id")
    username = request.session.get("username")

    parent_context = populateProfile(profilename, username, user_id)

    with connection.cursor() as cursor:
        cursor.execute("SELECT ID FROM ACCOUNT WHERE ACCOUNTNAME=:profilename;", {'profilename': profilename})

        profile_id = cursor.fetchone()

        if profile_id is None:
            return HttpResponse("User not found!")

        profile_id = profile_id[0]

        # cursor.execute('''SELECT P.ID POST_ID, P.TIMESTAMP, P.TEXT, P.MEDIA, A.PROFILE_PHOTO, A.ACCOUNTNAME AUTHOR
        #                   FROM POST P JOIN ACCOUNT_POSTS_POST APP
        #                   ON(P.ID = APP.POST_ID)
        #                   JOIN ACCOUNT A
        #                   ON(APP.ACCOUNT_ID = A.ID)
        #                   WHERE APP.ACCOUNT_ID = :profile_id
        #                   AND P.MEDIA IS NOT NULL
        #                   AND IS_USER_AUDIENCE(:username, P.ID) = 1
        #                   ORDER BY P.TIMESTAMP DESC;''', {'profile_id': profile_id, 'username': username})

        cursor.execute('''SELECT TV.POST_ID, TIMESTAMP, TEXT, MEDIA, PROFILE_PHOTO, AUTHOR, COMMENTLINK
                          FROM TWEET_VIEW TV
                          WHERE ACCOUNT_ID = :profile_id
                          AND TV.MEDIA IS NOT NULL
                          AND IS_USER_AUDIENCE(:username, TV.POST_ID) = 1
                          ORDER BY TV.TIMESTAMP DESC;''',
                       {'profile_id': profile_id, 'username': username})

        tweet_list = dictfetchall(cursor)

        cursor.execute('''SELECT CV.POST_ID, TIMESTAMP, TEXT, MEDIA, PROFILE_PHOTO, AUTHOR,
                          COMMENTLINK, PARENT_COMMENT_LINK, PARENT_TWEET_LINK, "replied_to"
                          FROM COMMENT_VIEW CV
                          WHERE ACCOUNT_ID = :profile_id
                          AND CV.MEDIA IS NOT NULL
                          AND IS_USER_AUDIENCE(:username, CV.POST_ID) = 1
                          ORDER BY CV.TIMESTAMP DESC;''',
                       {'profile_id': profile_id, 'username': username})

        comment_list = dictfetchall(cursor)

        post_list = tweet_list + comment_list

        print("Printing posted MEDIA posts for user: " + profilename)
        print(post_list)

        for post in post_list:
            cursor.execute('''SELECT COUNT(*) FROM ACCOUNT_LIKES_POST
                              WHERE ACCOUNT_ID=:user_id
                              AND POST_ID=:post_id;''', {'user_id': user_id, 'post_id': post["POST_ID"]})
            count = cursor.fetchone()[0]

            if int(count) == 1:
                post["LIKED"] = True

            cursor.execute(f'''SELECT COUNT(*) 
                               FROM ACCOUNT_BOOKMARKS_POST 
                               WHERE ACCOUNT_ID=:user_id
                               AND POST_ID=:postID;''', {'user_id': user_id, 'postID': post['POST_ID']})
            count = cursor.fetchone()[0]

            if int(count) == 1:
                post["BOOKMARKED"] = True

    template_name = "tweets.html"
    child_context = {"post_list": post_list,
                     "media_is_active": True,
                     "profile_name": profilename}

    context = {**parent_context, **child_context}

    if request.POST.get("follow", None):
        context["follows_user"] = follow_handler(request.POST.get("follow"), username, profilename, user_id, profile_id)
        context["follower_count"], context["following_count"] = populateFollowInfo(profilename)

    print("Printing overall context of media tab")
    print(context)

    return render(request, template_name, context)


@auth_or_redirect
def viewTweetReply(request, profilename):
    # loads all posts(including tweets and comments) posted by the user
    user_id = request.session.get("user_id")
    username = request.session.get("username")

    parent_context = populateProfile(profilename, username, user_id)

    with connection.cursor() as cursor:
        cursor.execute("SELECT ID FROM ACCOUNT WHERE ACCOUNTNAME=:profilename;", {'profilename': profilename})

        profile_id = cursor.fetchone()

        if profile_id is None:
            return HttpResponse("User not found!")

        profile_id = profile_id[0]

        cursor.execute('''SELECT TV.POST_ID, TIMESTAMP, TEXT, MEDIA, PROFILE_PHOTO, AUTHOR, COMMENTLINK
                          FROM TWEET_VIEW TV
                          WHERE ACCOUNT_ID = :profile_id
                          AND IS_USER_AUDIENCE(:username, TV.POST_ID) = 1
                          ORDER BY TV.TIMESTAMP DESC;''',
                       {'profile_id': profile_id, 'username': username})

        tweet_list = dictfetchall(cursor)

        cursor.execute('''SELECT CV.POST_ID, TIMESTAMP, TEXT, MEDIA, PROFILE_PHOTO, AUTHOR,
                          COMMENTLINK, PARENT_COMMENT_LINK, PARENT_TWEET_LINK, "replied_to"
                          FROM COMMENT_VIEW CV
                          WHERE ACCOUNT_ID = :profile_id
                          AND IS_USER_AUDIENCE(:username, CV.POST_ID) = 1
                          ORDER BY CV.TIMESTAMP DESC;''',
                       {'profile_id': profile_id, 'username': username})

        comment_list = dictfetchall(cursor)

        post_list = tweet_list + comment_list

        print("Printing posted MEDIA posts for user: " + profilename)
        print(post_list)

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

            print(f"uid{user_id}, {post['POST_ID']} {post}")

    template_name = "tweets.html"
    child_context = {"post_list": post_list,
                     "tweet_and_replies_is_active": True,
                     "profile_name": profilename}

    context = {**parent_context, **child_context}

    if request.POST.get("follow", None):
        context["follows_user"] = follow_handler(request.POST.get("follow"), username, profilename, user_id, profile_id)
        context["follower_count"], context["following_count"] = populateFollowInfo(profilename)

    print("Printing overall context of media tab")
    print(context)

    return render(request, template_name, context)


def follower(request, profilename):
    """
    Receives a profile name and shows corresponding follower list
    :param request:
    :param profilename:
    :return:
    """
    with connection.cursor() as cursor:
        cursor.execute('''SELECT F.FOLLOWER NAME, A.PROFILE_PHOTO, A.BIO
                           FROM FOLLOWER F JOIN ACCOUNT A
                           ON(F.FOLLOWER = A.ACCOUNTNAME)
                           WHERE F.FOLLOWED = :profilename;''', {'profilename': profilename})

        dict = dictfetchall(cursor)
        print("Printing follower list for user: " + profilename)
        print(dict)

    template_name = "follower_following_list.html"
    context = {'follower': True,
               'user': profilename,
               'profilelist': dict}

    if is_user_authenticated(request):
        context["notification_count"] = get_unseen_notif_count(request.session.get("user_id"))

    return render(request, template_name, context)


def following(request, profilename):
    """
    Receives a profile name and shows users followed by given profile
    :param request:
    :param profilename:
    :return:
    """
    with connection.cursor() as cursor:
        cursor.execute('''SELECT F.FOLLOWED NAME, A.PROFILE_PHOTO, A.BIO
                           FROM FOLLOWER F JOIN ACCOUNT A
                           ON(F.FOLLOWED = A.ACCOUNTNAME)
                           WHERE F.FOLLOWER = :profilename;''', {'profilename': profilename})

        dict = dictfetchall(cursor)
        print("Printing followed list for user: " + profilename)
        print(dict)

    template_name = "follower_following_list.html"
    context = {'user': profilename,
               'profilelist': dict}

    if is_user_authenticated(request):
        context["notification_count"] = get_unseen_notif_count(request.session.get("user_id"))

    return render(request, template_name, context)


def follow_handler(action, username, profilename, user_id, profile_id):
    # Toggle between follow and unfollow
    print("Value of follow action = ")
    print(action)

    with connection.cursor() as cursor:
        # Follow the user
        if action == "follow":
            data = cursor.callproc('INSERT_FOLLOW_NOTIF', (username, profilename, 'default' * 30))

            if data[2] == 'OK':
                print("Follow successful!")
                return True
            else:
                print("ERROR FOLLOWING USER!")
                print(data[2])
        # alse need to delete from notifications and notification_notifies_account
        # Delete the corresponding follow entry
        elif action == "unfollow":
            cursor.execute('''DELETE FROM ACCOUNT_FOLLOWS_ACCOUNT
                              WHERE ACCOUNT_ID = :follower_id
                              AND F_NOTIFICATION_ID =
                              (SELECT FOLLOW_NOTIFICATION_ID
                              FROM FOLLOW_NOTIFICATION
                              WHERE FOLLOWED_ACCOUNT_ID = :followed_id 
                              )''', {'follower_id': user_id, 'followed_id': profile_id})
            connection.commit()
            print("Follow notif Deletion performed!")
            return None

        else:
            print("\tINVALID FOLLOW OR UNFOLLOW")

def dictfetchall(cursor):
    """Return all rows from a cursor as a dict"""
    columns = [col[0] for col in cursor.description]
    return [
        dict(zip(columns, row))
        for row in cursor.fetchall()
    ]
