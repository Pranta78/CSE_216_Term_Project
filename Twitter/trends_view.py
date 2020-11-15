from django.http import HttpResponse
from django.db import connection
from django.shortcuts import render, redirect
from django.urls import reverse

from .auth import auth_or_redirect, is_user_authenticated


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
            cursor.execute('''SELECT P.ID POST_ID, P.TEXT, P.TIMESTAMP, P.MEDIA, A.PROFILE_PHOTO, A.ACCOUNTNAME AUTHOR
                              FROM HASHTAG H JOIN POST_CONTAINS_HASHTAG PCH
                              ON(H.TEXT = PCH.HASHTAG_TEXT)
                              JOIN POST P
                              ON(PCH.POST_ID = P.ID)
                              JOIN ACCOUNT_POSTS_POST APP
                              ON(P.ID = APP.POST_ID)
                              JOIN ACCOUNT A
                              ON(APP.ACCOUNT_ID = A.ID)
                              WHERE H.TEXT = :hashtag;''', {'hashtag': hashtag})

            post_list = dictfetchall(cursor)

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
               "trends_is_active": True}

    return render(request, template_name, context)


def dictfetchall(cursor):
    """Return all rows from a cursor as a dict"""
    columns = [col[0] for col in cursor.description]
    return [
        dict(zip(columns, row))
        for row in cursor.fetchall()
    ]
