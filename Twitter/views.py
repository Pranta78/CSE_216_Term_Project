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
               "tweet_list": tweetlist}

    template_name = "home.html"

    return render(request, template_name, context)


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

def test(request):
    img_path = 'https://www.facebook.com/images/groups/groups-default-cover-photo-2x.png'
    #comment for testing commit
    #Just download the uploaded images in the templates folder no need for static path.
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