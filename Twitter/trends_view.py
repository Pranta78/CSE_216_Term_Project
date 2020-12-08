from django.http import HttpResponse
from django.db import connection
from django.shortcuts import render, redirect
from django.urls import reverse

from .auth import auth_or_redirect, is_user_authenticated
from .notification_view import get_unseen_notif_count


@auth_or_redirect
def trend(request):
    user_id = request.session.get("user_id")
    username = request.session.get("username")

    # sorts hashtags by the number of times used and provides a hyperlink
    with connection.cursor() as cursor:
        cursor.execute('''SELECT COUNT(*) TOTAL, H.TEXT
                          FROM HASHTAG H JOIN POST_CONTAINS_HASHTAG PCH
                          ON(H.TEXT = PCH.HASHTAG_TEXT)
                          GROUP BY H.TEXT
                          ORDER BY TOTAL DESC;''')

        hashtag_list = dictfetchall(cursor)

        print("Printing hashtag_list : ")
        print(hashtag_list)

    template_name = "trend.html"
    context = {
        "hashtag_list": hashtag_list,
        "notification_count": get_unseen_notif_count(user_id),
        "trends_is_active": True
    }

    return render(request, template_name, context)


@auth_or_redirect
def show_hashtag(request, hashtag):
    user_id = request.session.get("user_id")
    username = request.session.get("username")

    with connection.cursor() as cursor:
        cursor.execute('''SELECT COUNT(*)
                          FROM HASHTAG
                          WHERE TEXT = :hashtag''', {'hashtag': hashtag})

        count = cursor.fetchone()[0]

        if count == 0:
            return HttpResponse("No posts were found for given hashtag")
        else:
            cursor.execute('''SELECT TV.POST_ID, TIMESTAMP, TV.TEXT, MEDIA, PROFILE_PHOTO, AUTHOR,
                              COMMENTLINK
                              FROM HASHTAG H JOIN POST_CONTAINS_HASHTAG PCH
                              ON(H.TEXT = PCH.HASHTAG_TEXT)
                              JOIN TWEET_VIEW TV
                              ON(PCH.POST_ID = TV.POST_ID)
                              WHERE H.TEXT = :hashtag
                              AND IS_USER_AUDIENCE(:username, TV.POST_ID) = 1;''',
                           {'hashtag': hashtag, 'username': username})

            tweet_list = dictfetchall(cursor)

            cursor.execute('''SELECT CV.POST_ID, TIMESTAMP, CV.TEXT, MEDIA, PROFILE_PHOTO, AUTHOR,
                              COMMENTLINK, PARENT_COMMENT_LINK, PARENT_TWEET_LINK, "replied_to"
                              FROM HASHTAG H JOIN POST_CONTAINS_HASHTAG PCH
                              ON(H.TEXT = PCH.HASHTAG_TEXT)
                              JOIN COMMENT_VIEW CV
                              ON(PCH.POST_ID = CV.POST_ID)
                              WHERE H.TEXT = :hashtag
                              AND IS_USER_AUDIENCE(:username, CV.POST_ID) = 1;''',
                           {'hashtag': hashtag, 'username': username})

            comment_list = dictfetchall(cursor)

            post_list = tweet_list + comment_list

            for post in post_list:
                with connection.cursor() as cursor:
                    cursor.execute('''SELECT COUNT(*) FROM ACCOUNT_LIKES_POST
                                      WHERE ACCOUNT_ID=:user_id AND POST_ID=:post_id;''',
                                   {'user_id': user_id, 'post_id': post['POST_ID']})

                    count = cursor.fetchone()[0]

                    if count == 1:
                        post["LIKED"] = True

                    cursor.execute('''SELECT COUNT(*) FROM ACCOUNT_BOOKMARKS_POST
                                      WHERE ACCOUNT_ID=:user_id AND POST_ID=:post_id;''',
                                   {'user_id': user_id, 'post_id': post['POST_ID']})
                    count = cursor.fetchone()[0]

                    if count == 1:
                        post["BOOKMARKED"] = True

            print("Printing postlist containing hashtag: "+hashtag)
            print(post_list)

    template_name = "hashtag.html"
    context = {"post_list": post_list,
               "hashtag": hashtag,
               "notification_count": get_unseen_notif_count(user_id),
               "trends_is_active": True}

    return render(request, template_name, context)


def dictfetchall(cursor):
    """Return all rows from a cursor as a dict"""
    columns = [col[0] for col in cursor.description]
    return [
        dict(zip(columns, row))
        for row in cursor.fetchall()
    ]
