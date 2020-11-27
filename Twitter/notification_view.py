from django.http import HttpResponse
from django.db import connection
from django.shortcuts import render, redirect
from .auth import auth_or_redirect
from django.urls import reverse

@auth_or_redirect
def notifications_all_view(request):
    user_id = request.session.get("user_id", None)
    with connection.cursor() as cursor:
        notifications = get_follow_notifs(user_id)
        notifications.extend(get_mention_notifs(user_id))
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


def get_mention_notifs(user_id):
    mention_notifications = []
    with connection.cursor() as cursor:
        results_rows = cursor.execute('''SELECT  
                                            n.ID, n.TIMESTAMP, nna.SEEN, pmn.MENTIONED_POST_ID, tv.TWEET_ID, tv.AUTHOR 
                                        FROM 
                                            NOTIFICATION n 
                                            JOIN NOTIFICATION_NOTIFIES_ACCOUNT nna on(nna.NOTIFICATION_ID = n.ID) 
                                            JOIN POST_MENTION_NOTIFICATION pmn on(n.ID = pmn.NOTIFICATION_BASE_ID) 
                                            JOIN POST_MENTIONS_ACCOUNT pma on( 
                                                pma.PM_NOTIFICATION_ID = pmn.POST_MENTION_NOTIFICATION_ID AND 
                                                pma.ACCOUNT_ID = %s 
                                            ) 
                                            JOIN TWEET_VIEW tv on(tv.ACCOUNT_ID = pma.ACCOUNT_ID AND tv.POST_ID = pmn.MENTIONED_POST_ID)
                                        ORDER BY 
                                            n.TIMESTAMP DESC ''', [user_id]).fetchall()
        if results_rows is not None and len(results_rows) > 0:
            for result_row in results_rows:
                mention_notifications.append(
                    {
                        "NOTIFICATION_ID": result_row[0],
                        "TIMESTAMP": result_row[1],
                        "SEEN": result_row[2],  # null if not seen
                        "NOTIFICATION_LINK": f"/tweet/{result_row[4]}/",
                        "NOTIFICATION_TEXT": f"You were mentioned in a post by {result_row[5]} .",
                    }
                )

    return mention_notifications

