from django.http import HttpResponse
from django.db import connection
from django.shortcuts import render, redirect
from .auth import auth_or_redirect
from django.urls import reverse

@auth_or_redirect
def notifications_all_view(request):
    user_id = request.session.get("user_id", None)
    with connection.cursor() as cursor:
        results_rows = cursor.execute("SELECT n.ID, n.TIMESTAMP, nna.SEEN,"
                                      "(SELECT ACCOUNTNAME from ACCOUNT WHERE ACCOUNT.ID = afa.ACCOUNT_ID) as FOLLOWER_NAME,"
                                      "pmn.MENTIONED_POST_ID, ma.ACCOUNTNAME "
                                      "FROM NOTIFICATION n "
                                      "JOIN NOTIFICATION_NOTIFIES_ACCOUNT nna on(nna.NOTIFICATION_ID = n.ID) "
                                      "LEFT OUTER JOIN FOLLOW_NOTIFICATION fn on(n.ID = fn.NOTIFICATION_BASE_ID) "
                                      "LEFT OUTER JOIN ACCOUNT_FOLLOWS_ACCOUNT afa on( "
                                      "afa.F_NOTIFICATION_ID = fn.FOLLOW_NOTIFICATION_ID AND "
                                      "fn.FOLLOWED_ACCOUNT_ID = %s "
                                      ") "
                                      "LEFT OUTER JOIN POST_MENTION_NOTIFICATION pmn on(n.ID = pmn.NOTIFICATION_BASE_ID) "
                                      "LEFT OUTER JOIN POST_MENTIONS_ACCOUNT pma on( "
                                      "pma.PM_NOTIFICATION_ID = pmn.POST_MENTION_NOTIFICATION_ID AND "
                                      "pma.ACCOUNT_ID = %s "
                                      ") "
                                      "LEFT OUTER JOIN ACCOUNT_POSTS_POST mapp on(mapp.POST_ID = pmn.MENTIONED_POST_ID) "
                                      "LEFT OUTER JOIN ACCOUNT ma on(mapp.ACCOUNT_ID = ma.ID) "
                                      "ORDER BY n.TIMESTAMP DESC "
                                      , [user_id, user_id]).fetchall()
        print(f"notifs {results_rows}")
        notifications = []
        if results_rows is not None and len(results_rows) > 0:
            for result_row in results_rows:
                if result_row[3] is not None:# follow notif
                    notifications.append(
                        {
                            "TIMESTAMP": result_row[1],
                            "SEEN": result_row[2] is not None,  # null if not seen
                            "NOTIFICATION_LINK":  f"/user/{result_row[3]}/",
                            "NOTIFICATION_TEXT": f"{result_row[3]} has followed you.",
                        }
                    )
                elif result_row[4] is not None:#this will actually pull nothing until mentions are implemented
                    notifications.append(
                        {
                            "TIMESTAMP": result_row[0],
                            "SEEN": result_row[2] is not None,  # null if not seen
                            "NOTIFICATION_LINK": f"/tweet/{result_row[4]}/",
                            "NOTIFICATION_TEXT": f"You were mentioned in a post by {result_row[5]} .",
                        }
                    )
                #had some problems with executemany.
                #as the inserts only occur for newly seen notifs, running separate queries should not be a problem.
                if result_row[2] is None:
                    cursor.execute("UPDATE NOTIFICATION_NOTIFIES_ACCOUNT "
                                    "set SEEN = sysdate "
                                    "WHERE NOTIFICATION_ID = %s ", [result_row[0]])

                notification_count = cursor.callfunc("get_unseen_notif_count", int, [user_id])

                context = {
                    "notification_count": notification_count,
                    "NOTIFICATIONS": notifications,
                }
                return render(request, "NotificationView.html", context)

    return HttpResponse("notifERROR")
