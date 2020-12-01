from django.http import HttpResponse
from django.db import connection
from django.shortcuts import render, redirect
from .auth import auth_or_redirect
from django.urls import reverse
import re

@auth_or_redirect
def notifications_all_view(request):
    user_id = request.session.get("user_id", None)
    with connection.cursor() as cursor:
        notifications = get_follow_notifs(user_id)
        notifications.extend(get_mention_notifs(user_id))
        notifications.extend(get_retweet_notifs(user_id))
        notifications.extend(get_like_notifs(user_id))
        notifications.sort(key=lambda x: x["TIMESTAMP"], reverse=True)

        unseen_notification_count = cursor.callfunc("get_unseen_notif_count", int, [user_id])
        context = {
            "notification_count": unseen_notification_count,
            "NOTIFICATIONS": notifications,
            "all_notifs_active": True,
        }

        print(notifications)
        return render(request, "NotificationView.html", context)

    return HttpResponse("notifERROR")

@auth_or_redirect
def handle_notif_click(request):
    if request.POST:
        user_id = request.session.get("user_id", None)
        notification_id = request.POST["NOTIFICATION_ID"]
        redirect_link = request.POST["NOTIFICATION_LINK"]
        if notification_id:
            with connection.cursor() as cursor:
                result = cursor.execute('''
                    SELECT
                        COUNT(*)
                    FROM
                        NOTIFICATION_NOTIFIES_ACCOUNT
                    WHERE
                        ACCOUNT_ID = %s AND
                        NOTIFICATION_ID = %s AND
                        SEEN is NULL
                    ''',[user_id, notification_id]).fetchone()
                print(result)
                if result and int(result[0]) == 1:#need to check if the notification belongs to user
                    cursor.execute("UPDATE NOTIFICATION_NOTIFIES_ACCOUNT "
                                   "set SEEN = sysdate "
                                   "WHERE NOTIFICATION_ID = %s ", [notification_id])

            if redirect_link:
                return redirect(redirect_link)

        return redirect("INVALID GET REQUEST ON POST URL.")


def get_follow_notifs(user_id):
    follow_notifications = []
    with connection.cursor() as cursor:
        results_rows = cursor.execute('''SELECT 
                                            n.ID, n.TIMESTAMP, nna.SEEN,
                                            (SELECT ACCOUNTNAME from ACCOUNT WHERE ACCOUNT.ID = afa.ACCOUNT_ID) as FOLLOWER_NAME
                                        FROM NOTIFICATION n 
                                        JOIN NOTIFICATION_NOTIFIES_ACCOUNT nna on(nna.NOTIFICATION_ID = n.ID) 
                                        JOIN FOLLOW_NOTIFICATION fn on(n.ID = fn.NOTIFICATION_BASE_ID) 
                                        JOIN ACCOUNT_FOLLOWS_ACCOUNT afa on( 
                                            afa.F_NOTIFICATION_ID = fn.FOLLOW_NOTIFICATION_ID AND 
                                            fn.FOLLOWED_ACCOUNT_ID = %s 
                                        )
                                        ORDER BY n.TIMESTAMP DESC ''', [user_id]).fetchall()
        if results_rows is not None and len(results_rows) > 0:
            for result_row in results_rows:
                follow_notifications.append(
                    {
                        "NOTIFICATION_ID": result_row[0],
                        "TIMESTAMP": result_row[1],
                        "SEEN": result_row[2],  # null if not seen
                        "NOTIFICATION_LINK": f"/user/{result_row[3]}/",
                        "NOTIFICATION_TEXT": f"{result_row[3]} has followed you.",
                    }
                )

    return follow_notifications


@auth_or_redirect
def mention_notifications_view(request):
    user_id = request.session.get("user_id", None)
    with connection.cursor() as cursor:
        notifications = get_mention_notifs(user_id)
        unseen_notification_count = cursor.callfunc("get_unseen_notif_count", int, [user_id])
        context = {
            "notification_count": unseen_notification_count,
            "NOTIFICATIONS": notifications,
            "mentions_active": True,
        }
        return render(request, "NotificationView.html", context)

    return HttpResponse("notifERROR")

@auth_or_redirect
def retweet_notifications_view(request):
    user_id = request.session.get("user_id", None)
    with connection.cursor() as cursor:
        notifications = get_retweet_notifs(user_id)
        unseen_notification_count = cursor.callfunc("get_unseen_notif_count", int, [user_id])
        context = {
            "notification_count": unseen_notification_count,
            "NOTIFICATIONS": notifications,
            "retweets_active": True,
        }
        return render(request, "NotificationView.html", context)

    return HttpResponse("notifERROR")


@auth_or_redirect
def like_notifications_view(request):
    user_id = request.session.get("user_id", None)
    with connection.cursor() as cursor:
        notifications = get_like_notifs(user_id)
        unseen_notification_count = cursor.callfunc("get_unseen_notif_count", int, [user_id])
        context = {
            "notification_count": unseen_notification_count,
            "NOTIFICATIONS": notifications,
            "likes_active": True,
        }
        return render(request, "NotificationView.html", context)

    return HttpResponse("notifERROR")


@auth_or_redirect
def follow_notifications_view(request):
    user_id = request.session.get("user_id", None)
    with connection.cursor() as cursor:
        notifications = get_follow_notifs(user_id)
        context = {
            "notification_count": get_unseen_notif_count(user_id),
            "NOTIFICATIONS": notifications,
            "follows_active": True,
        }
        return render(request, "NotificationView.html", context)

    return HttpResponse("notifERROR")


def get_unseen_notif_count(user_id):
    with connection.cursor() as cursor:
        return cursor.callfunc("get_unseen_notif_count", int, [user_id])

def get_like_notifs(user_id):
    like_notifications = []
    with connection.cursor() as cursor:
        results_rows = cursor.execute('''
                                    SELECT  
                                        n.ID, n.TIMESTAMP, nna.SEEN, pmn.MENTIONED_POST_ID,
                                        tv.TWEET_ID, cv.COMMENT_ID, ra.ACCOUNTNAME, pmn.POST_MENTION_NOTIFICATION_ID
                                    FROM 
                                        ACCOUNT_POSTS_POST app 
                                        JOIN POST_MENTION_NOTIFICATION pmn on(
                                                pmn.MENTIONED_POST_ID = app.POST_ID
                                        ) 
                                        JOIN NOTIFICATION n on(
                                                n.ID = pmn.NOTIFICATION_BASE_ID 
                                        )
                                        JOIN NOTIFICATION_NOTIFIES_ACCOUNT nna on(
                                                nna.NOTIFICATION_ID = n.ID AND
                                                nna.ACCOUNT_ID = app.ACCOUNT_ID
                                        ) 
                                        JOIN ACCOUNT_LIKES_POST alp on( 
                                                alp.PM_NOTIFICATION_ID = pmn.POST_MENTION_NOTIFICATION_ID AND
                                                alp.POST_ID = app.POST_ID
                                        )
                                        JOIN ACCOUNT ra on(
                                                ra.ID = alp.ACCOUNT_ID
                                        ) 
                                        LEFT OUTER JOIN TWEET_VIEW tv on(
                                            tv.POST_ID = app.post_ID 
                                        )
                                        LEFT OUTER JOIN COMMENT_VIEW cv on(
                                           cv.POST_ID = app.post_ID 
                                        )
                                    WHERE 
                                        app.ACCOUNT_ID =  %s''', [user_id]).fetchall()
        if results_rows is not None:
            for result_row in results_rows:
                n = {
                    "NOTIFICATION_ID": result_row[0],
                    "TIMESTAMP": result_row[1],
                    "SEEN": result_row[2],
                    }
                if result_row[4] is not None:
                    n["NOTIFICATION_TEXT"] = f"You tweet was liked by {result_row[6]} ."
                    n["NOTIFICATION_LINK"]= reverse("detailedTweetView", kwargs={
                         "tweetID": result_row[4]
                     })
                elif result_row[5] is not None:
                    n["NOTIFICATION_TEXT"] = f"Your comment was liked by {result_row[6]} ."
                    n["NOTIFICATION_LINK"] = reverse("comment_reply_view", kwargs={
                        "commentID": result_row[5]
                    })

                like_notifications.append(n)

    return like_notifications


def get_mention_notifs(user_id):
    mention_notifications = []
    with connection.cursor() as cursor:
        results_rows = cursor.execute('''SELECT  
                                            n.ID, n.TIMESTAMP, nna.SEEN, pmn.MENTIONED_POST_ID, tv.TWEET_ID, tv.AUTHOR, cv.COMMENT_ID, cv.AUTHOR
                                        FROM 
                                            NOTIFICATION n 
                                            JOIN NOTIFICATION_NOTIFIES_ACCOUNT nna on(nna.NOTIFICATION_ID = n.ID) 
                                            JOIN POST_MENTION_NOTIFICATION pmn on(n.ID = pmn.NOTIFICATION_BASE_ID) 
                                            JOIN POST_MENTIONS_ACCOUNT pma on( 
                                                    pma.PM_NOTIFICATION_ID = pmn.POST_MENTION_NOTIFICATION_ID AND 
                                                    pma.ACCOUNT_ID = %s 
                                            ) 
                                            LEFT JOIN TWEET_VIEW tv on(
                                                tv.POST_ID = pmn.MENTIONED_POST_ID
                                            )
                                            LEFT JOIN COMMENT_VIEW cv on(
                                                cv.POST_ID = pmn.MENTIONED_POST_ID
                                            )
                                        ORDER BY 
                                            n.TIMESTAMP DESC ''', [user_id]).fetchall()
        if results_rows is not None and len(results_rows) > 0:
            for result_row in results_rows:
                n = {
                        "NOTIFICATION_ID": result_row[0],
                        "TIMESTAMP": result_row[1],
                        "SEEN": result_row[2],  # null if not seen
                    }
                if result_row[4] is not None:
                    n["NOTIFICATION_LINK"] = reverse("detailedTweetView", kwargs={"tweetID": result_row[4]})
                    n["NOTIFICATION_TEXT"] = f"You were mentioned in a tweet by {result_row[5]} ."
                elif result_row[6] is not None:
                    n["NOTIFICATION_LINK"] = reverse("comment_reply_view", kwargs={"commentID": result_row[6]})
                    n["NOTIFICATION_TEXT"] = f"You were mentioned in a comment by {result_row[7]} ."

                mention_notifications.append(n)


    return mention_notifications


def get_retweet_notifs(user_id):
    rt_notifications = [] #TODO FIX RETWEET query
    with connection.cursor() as cursor:
        results_rows = cursor.execute('''
                                        SELECT  
                                            n.ID, n.TIMESTAMP, nna.SEEN, pmn.MENTIONED_POST_ID,
                                            tv.TWEET_ID, cv.COMMENT_ID, ra.ACCOUNTNAME, pmn.POST_MENTION_NOTIFICATION_ID
                                        FROM 
                                            ACCOUNT_POSTS_POST app 
                                            JOIN POST_MENTION_NOTIFICATION pmn on(
                                                pmn.MENTIONED_POST_ID = app.POST_ID
                                            ) 
                                            JOIN NOTIFICATION n on(
                                                n.ID = pmn.NOTIFICATION_BASE_ID 
                                            )
                                            JOIN NOTIFICATION_NOTIFIES_ACCOUNT nna on(
                                                nna.NOTIFICATION_ID = n.ID AND
                                                nna.ACCOUNT_ID = app.ACCOUNT_ID
                                            ) 
                                            JOIN ACCOUNT_RETWEETS_POST arp on( 
                                                arp.PM_NOTIFICATION_ID = pmn.POST_MENTION_NOTIFICATION_ID AND
                                                arp.POST_ID = app.POST_ID
                                            )
                                            JOIN ACCOUNT ra on(
                                                ra.ID = arp.ACCOUNT_ID
                                            ) 
                                            LEFT OUTER JOIN TWEET_VIEW tv on(
                                              tv.POST_ID = app.post_ID 
                                            )
                                            LEFT OUTER JOIN COMMENT_VIEW cv on(
                                                cv.POST_ID = app.post_ID 
                                            )
                                        WHERE 
                                            app.ACCOUNT_ID =  %s''', [user_id]).fetchall()
        if results_rows is not None:
            for result_row in results_rows:
                n = {
                    "NOTIFICATION_ID": result_row[0],
                    "TIMESTAMP": result_row[1],
                    "SEEN": result_row[2],
                    "NOTIFICATION_LINK": reverse("detailed_retweet_view", kwargs={
                         "post_id": result_row[3],
                         "account_name": result_row[6],
                         "pm_notification_id": result_row[7],
                     })}
                if result_row[4] is not None:
                    n["NOTIFICATION_TEXT"] = f"You tweet was retweeted by {result_row[6]} ."
                elif result_row[5] is not None:
                    n["NOTIFICATION_TEXT"] = f"Your comment was retweeted by {result_row[6]} ."

                rt_notifications.append(n)

    return rt_notifications

def fetch_mentioned_users_from_post(post_body):
    regex = '@(\w+)'
    return re.findall(regex, post_body)


def insert_mention_notif_from_post_text(cursor, post_text, base_notif_id, pm_notif_id, post_id):
    if post_text:
        mentions = fetch_mentioned_users_from_post(post_text)
        print(f"mentions {mentions}")
        if mentions and len(mentions) > 0:
            for mention in mentions:
                # CHECK if user valid and no post_mention has already  been created for user for this post
                result = cursor.execute('''	
                                        SELECT ACCOUNTNAME
                                        FROM ACCOUNT a 
                                        WHERE a.ACCOUNTNAME = %s AND 
                                            (SELECT count(*)
                                            FROM POST_MENTIONS_ACCOUNT pma
                                            JOIN POST_MENTION_NOTIFICATION pmn ON(pmn.POST_MENTION_NOTIFICATION_ID = pma.PM_NOTIFICATION_ID)
                                            WHERE pma.ACCOUNT_ID = a.ID AND pmn.MENTIONED_POST_ID = %s) = 0
                                             ''', [mention, post_id]).fetchone()
                if result is not None:
                    cursor.execute('''
                                    INSERT INTO 
                                        POST_MENTIONS_ACCOUNT 
                                    VALUES(
                                       (SELECT ID  from ACCOUNT WHERE ACCOUNTNAME=:username), :pm_notif_id
                                       )''', {'username': mention, 'pm_notif_id': pm_notif_id})
                    cursor.execute('''
                                INSERT INTO 
                                    NOTIFICATION_NOTIFIES_ACCOUNT 
                                VALUES(
                                   (SELECT ID  from ACCOUNT WHERE ACCOUNTNAME=:username), :base_notif_id, NULL 
                                   )''',
                                   {'username': mention, 'base_notif_id': base_notif_id, })
                else:
                    print(f"{mention} mention skip { base_notif_id}  {pm_notif_id} {post_id}")

