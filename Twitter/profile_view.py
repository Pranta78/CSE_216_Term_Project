from django.http import HttpResponse
from django.db import connection
from django.shortcuts import render, redirect
from .auth import auth_or_redirect
from django.urls import reverse


@auth_or_redirect
def profile_edit(request):
    user_id = request.session.get("user_id", None)
    username = request.session.get("username", None)

    with connection.cursor() as cursor:
        cursor.execute(f'''SELECT BIO, PROFILE_PHOTO, HEADER_PHOTO
                           FROM ACCOUNT WHERE ID = {user_id};''')

        (current_bio, current_profile_photo, current_header_photo) = cursor.fetchone()

        print("Printing bio, pp and hp")
        print((current_bio, current_profile_photo, current_header_photo))

    from django.core.files.storage import FileSystemStorage

    (bio, profile_photo, header_photo) = (current_bio, current_profile_photo, current_header_photo)

    if request.POST:
        bio = request.POST.get("bio", '')
        profile_photo = request.FILES.get("profile_photo", '')
        header_photo = request.FILES.get("header_photo", '')

        fs = FileSystemStorage()

        if bio is None:
            bio = current_bio

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
            cursor.execute(f'''UPDATE ACCOUNT
                            SET BIO = '{bio}',
                                PROFILE_PHOTO = '{profile_photo}',
                                HEADER_PHOTO = '{header_photo}'
                            WHERE ID = {user_id};''')
            connection.commit()

        return redirect(reverse('user_profile', args=[username]))

    template_name = "profile_edit.html"
    context = {'bio': bio,
               'profile_photo': profile_photo,
               'header_photo': header_photo}

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

    if profilename != username:
        # will be used to replace follow button with profile edit one
        self_profile = None

        with connection.cursor() as cursor:
            cursor.execute(f"SELECT ID FROM ACCOUNT WHERE ACCOUNTNAME = '{profilename}';")
            row = cursor.fetchone()

            if len(row) == 0:
                return HttpResponse("<h2>Invalid User profile!</h2>")
            else:
                profile_id = row[0]

        # The follow button will be disabled if the profile user is followed by the logged in user!
        follows_user = None

        with connection.cursor() as cursor:
            cursor.execute(f'''SELECT COUNT(*)
                            FROM ACCOUNT_FOLLOWS_ACCOUNT
                            WHERE ACCOUNT_ID = {user_id}
                            AND 
                            F_NOTIFICATION_ID = 
                                (SELECT FOLLOW_NOTIFICATION_ID
                                FROM FOLLOW_NOTIFICATION
                                WHERE FOLLOWED_ACCOUNT_ID = {profile_id});''')
            row = cursor.fetchone()

            # if user is visiting his own profile
            if row[0] != 0 or (username == profilename):
                follows_user = True

        if request.POST:
            with connection.cursor() as cursor:
                data = cursor.callproc('INSERT_FOLLOW_NOTIF', (username, profilename, 'default'*30))

                if data[2] == 'OK':
                    print("Follow successful!")
                    follows_user = True
                else:
                    print("ERROR FOLLOWING USER!")
                    print(data[2])

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
        cursor.execute(f'''SELECT BIO, PROFILE_PHOTO, HEADER_PHOTO
                               FROM ACCOUNT WHERE ID = {profile_id};''')

        (bio, profile_photo, header_photo) = cursor.fetchone()

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
               'self_profile': self_profile}

    template_name = "profile.html"
    return render(request, template_name, context)


def fetchLikedPosts(userID):
    """
    This will fetch all posts' ID liked by the given user id and return a dictionary of ID's
    :param userID: a user id
    :return: a list of integers containing containing all post id's which were liked by the user
    """
    with connection.cursor() as cursor:
        cursor.execute(f'''SELECT POST_ID ID
                           FROM ACCOUNT_LIKES_POST
                           WHERE ACCOUNT_ID = {userID};''')

        row = cursor.fetchall()
        print("Printing liked post for user: " + userID)
        print(row)
        return [col[0] for col in row]


def fetchBookmarkedPosts(userID):
    """
    This will fetch all posts' ID bookmarked by the given user id and return a dictionary of ID's
    :param userID: a user id
    :return: a list of integers containing all post id's which were bookmarked by the user
    """
    with connection.cursor() as cursor:
        cursor.execute(f'''SELECT POST_ID ID
                           FROM ACCOUNT_BOOKMARKS_POST
                           WHERE ACCOUNT_ID = {userID};''')

        row = cursor.fetchall()
        print("Printing bookmarked post for user: " + userID)
        print(row)
        return [col[0] for col in row]


def fetchFollwers(username):
    """
    This will fetch all users' name who follow the user with given user Name
    :param username: a user name
    :return: a list of string containing all user name's who follow the user user with given user ID
    """
    with connection.cursor() as cursor:
        cursor.execute(f'''SELECT FOLLOWER NAME
                           FROM FOLLOWER
                           WHERE FOLLOWED = '{username}';''')

        row = cursor.fetchall()
        print("Printing follower list for user: " + username)
        print(row)
        return [col[0] for col in row]


def fetchFollwedList(username):
    """
    This will fetch all users' name who are followed by the user with given user Name
    :param username: a user name
    :return: a list of string containing all user name's who are followed by the user with given user Name
    """
    with connection.cursor() as cursor:
        cursor.execute(f'''SELECT FOLLOWED NAME
                           FROM FOLLOWER
                           WHERE FOLLOWER = '{username}';''')

        row = cursor.fetchall()
        print("Printing followed list for user: "+username)
        print(row)
        return [col[0] for col in row]


def dictfetchall(cursor):
    """Return all rows from a cursor as a dict"""
    columns = [col[0] for col in cursor.description]
    return [
        dict(zip(columns, row))
        for row in cursor.fetchall()
    ]
