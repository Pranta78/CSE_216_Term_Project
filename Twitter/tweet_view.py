from django.http import HttpResponse
from django.db import connection
from django.shortcuts import render, redirect
from django.urls import reverse
from django.core.files.storage import FileSystemStorage
from .auth import auth_or_redirect, is_user_authenticated
from .comment_view import get_tweet_comment_chains,get_comment_chain
from .notification_view import insert_mention_notif_from_post_text, get_unseen_notif_count


@auth_or_redirect
def create_retweet(request, post_id):
    #TODO do sanity check that post_id is valid
    user_id = request.session['user_id']
    if request.POST:
        text = ""
        if user_id and post_id:
            with connection.cursor() as cursor:
                msg = ''
                pm_notification_id = 0
                retweeted_author_id = 0
                result = cursor.callproc("RETWEET_POST", [text,  post_id, user_id, retweeted_author_id, pm_notification_id])
                retweeted_author_id = result[3]
                pm_notification_id = result[4]
                retweeted_author_name = cursor.execute('''SELECT ACCOUNTNAME FROM ACCOUNT WHERE ID = %s;''', [user_id]).fetchone()[0]

                connection.commit()
                return redirect(reverse('detailed_retweet_view', kwargs={
                    "account_name": retweeted_author_name,
                    "post_id": int(post_id),
                    "pm_notification_id": int(pm_notification_id)
                }))
        else:
            return HttpResponse(f"invalid (account_id, post_ID)={user_id},{post_id},  for create retweet link POST request")
    else:
        with connection.cursor() as cursor:
            result = cursor.execute('''SELECT ACCOUNTNAME FROM ACCOUNT WHERE ID = %s''', [user_id]).fetchone()
            account_name = result[0]

            context = {
                "AUTHOR": account_name,
                "USERLOGGEDIN": is_user_authenticated(request),
                "notification_count": get_unseen_notif_count(user_id),
            }

            result = cursor.execute('''
            SELECT
                POST_ID, TIMESTAMP, TEXT, MEDIA,AUTHOR, PROFILE_PHOTO, TWEET_ID
            FROM 
                TWEET_VIEW 
            WHERE 
                POST_ID = %s  
            ''', [post_id]).fetchone()

            if result is not None:
                comment_chains = get_tweet_comment_chains(cursor, result[6])
                mark_comment_chain_like_bookmark(cursor, comment_chains, user_id)
                context["POST"] = {
                    "AUTHOR": result[4],
                    "PROFILE_PHOTO": result[5],
                    "TEXT": result[2],
                    "MEDIA": result[3],
                    "TIMESTAMP": result[1],
                    "POST_ID": result[0],
                    "COMMENTLINK": reverse("detailedTweetView", kwargs={"tweetID": result[6]}) + "#tweet-reply-box",
                    "COMMENTCHAINS": comment_chains
                }
                mark_post_like_bookmark(cursor, user_id, context["POST"])
            else:
                result = cursor.execute('''
                                SELECT
                                    POST_ID, TIMESTAMP, TEXT, MEDIA,AUTHOR, PROFILE_PHOTO, COMMENT_ID,PARENT_COMMENT_ID, "replied_to", TWEET_ID
                                FROM 
                                    COMMENT_VIEW 
                                WHERE 
                                    POST_ID =  %s           
                                ''', [post_id]).fetchone()

                if result is None:
                    return HttpResponse("invalid (account_name, post_ID, pm_notification_ID) for create retweet link")
                else:
                    comment = {
                        "AUTHOR": result[4],
                        "PROFILE_PHOTO": result[5],
                        "TEXT": result[2],
                        "MEDIA": result[3],
                        "TIMESTAMP": result[1],
                        "POST_ID": result[0],
                        "COMMENT_ID": result[6],
                        "COMMENTLINK": reverse("comment_reply_view", kwargs={"commentID": result[6]}),
                    }
                    comment_chains = get_comment_chain(cursor, result[9], comment)
                    mark_comment_chain_like_bookmark(cursor, comment_chains, user_id)
                    comment["COMMENTCHAINS"] = comment_chains
                    if len(comment_chains) > 0:
                        comment_chains[0][0] = None  # root comment = this and it is already viewed as post


                    context["POST"] = comment
                    if result[7] is not None:
                        context["POST"]["replied_to"] = result[8]
                    mark_post_like_bookmark(cursor, user_id, context["POST"])

            return render(request, "CreateRetweetView.html", context)

    return HttpResponse("Invalid GET request on POST URL")

def detailed_retweet_view(request, account_name, post_id, pm_notification_id):
    #TODO move these out
#     t = '''SELECT *
# FROM
# 	ACCOUNT_LIKES_POST alp
# 	JOIN POST_MENTION_NOTIFICATION pmn on(alp.PM_NOTIFICATION_ID = pmn.POST_MENTION_NOTIFICATION_ID)
# 	JOIN NOTIFICATION bn on(bn.ID = pmn.NOTIFICATION_BASE_ID)
# 	JOIN NOTIFICATION_NOTIFIES_ACCOUNT nna on(nna.NOTIFICATION_ID = bn.ID)
# 	JOIN ACCOUNT_POSTS_POST app on(app.ACCOUNT = )''';
#     t = '''SELECT *

    with connection.cursor() as cursor:
        post = None
        comment_chains = None
        user_id = request.session['user_id']
        result = cursor.execute('''
        SELECT
            arp.ACCOUNT_ID, (SELECT PROFILE_PHOTO from ACCOUNT WHERE ID = arp.ACCOUNT_ID), arp.TIMESTAMP, arp.TEXT,
            tv.TWEET_ID, tv.POST_ID, tv.AUTHOR, tv.PROFILE_PHOTO, tv.TEXT, tv.MEDIA, tv.TIMESTAMP
        FROM
            ACCOUNT_RETWEETS_POST arp
        JOIN
            POST_MENTION_NOTIFICATION pmn on(arp.PM_NOTIFICATION_ID = pmn.POST_MENTION_NOTIFICATION_ID)
        JOIN
            TWEET_VIEW tv on(tv.POST_ID = pmn.MENTIONED_POST_ID)
        WHERE
            (SELECT ACCOUNTNAME from ACCOUNT WHERE ID = arp.ACCOUNT_ID) = %s AND
            tv.POST_ID = %s AND
            pmn.POST_MENTION_NOTIFICATION_ID = %s
        ''', [account_name, post_id, pm_notification_id]).fetchone()
        if result is not None:
            post = {
                "AUTHOR": result[6],
                "PROFILE_PHOTO": result[7],
                "TEXT": result[8],
                "MEDIA": result[9],
                "TIMESTAMP": result[10],
                "POST_ID": result[5],
                "COMMENTLINK":  reverse("detailedTweetView", kwargs={"tweetID": result[4]}) + "#tweet-reply-box",
            }
            comment_chains = get_tweet_comment_chains(cursor, result[4])
            mark_comment_chain_like_bookmark(cursor,comment_chains,user_id)
            mark_post_like_bookmark(cursor, user_id,post)
        else:
            result = cursor.execute('''
                        SELECT
                            arp.ACCOUNT_ID, (SELECT PROFILE_PHOTO from ACCOUNT WHERE ID = arp.ACCOUNT_ID), arp.TIMESTAMP, arp.TEXT,
                            cv.COMMENT_ID, cv.POST_ID, cv.AUTHOR, cv.PROFILE_PHOTO, cv.TEXT, cv.MEDIA, cv.TIMESTAMP,
                            cv.PARENT_COMMENT_ID, cv."replied_to", cv.TWEET_ID
                        FROM
                            ACCOUNT_RETWEETS_POST arp
                        JOIN
                            POST_MENTION_NOTIFICATION pmn on(arp.PM_NOTIFICATION_ID = pmn.POST_MENTION_NOTIFICATION_ID)
                        JOIN
                            COMMENT_VIEW cv on(cv.POST_ID = pmn.MENTIONED_POST_ID)
                        WHERE
                            (SELECT ACCOUNTNAME from ACCOUNT WHERE ID = arp.ACCOUNT_ID) = %s AND
                            cv.POST_ID = %s AND
                            pmn.POST_MENTION_NOTIFICATION_ID = %s
                        ''', [account_name, post_id, pm_notification_id]).fetchone()

            if result is None:
                return HttpResponse("invalid (account_name, post_ID, pm_notification_ID) for retweet link")
            else:
                post = {
                    "AUTHOR": result[6],
                    "PROFILE_PHOTO": result[7],
                    "TEXT": result[8],
                    "MEDIA": result[9],
                    "TIMESTAMP": result[10],
                    "POST_ID": result[5],
                    "COMMENT_ID": result[4],
                    "COMMENTLINK": reverse("comment_reply_view", kwargs={"commentID": result[4]}),
                }
                if result[11] is not None:
                    post["replied_to"] = result[12]
                comment_chains = get_comment_chain(cursor, result[13], post)
                mark_comment_chain_like_bookmark(comment_chains)
                mark_post_like_bookmark(cursor, user_id, post)
                if len(comment_chains) > 0:
                    comment_chains[0][0] = None#root comment = this and it is already viewed as post
        context = {
            "RT": {
                "AUTHOR": account_name,
                "AUTHOR_PROFILE_PHOTO": result[1],
                "TIMESTAMP": result[2],
                "TEXT": result[3],
                "POST": post
            },
            "notification_count": get_unseen_notif_count(user_id),
            "USERLOGGEDIN": is_user_authenticated(request),
            "COMMENTCHAINS": comment_chains,
        }

        return  render(request, "DetailedReTweetView.html", context)
    return HttpResponse("Server connection fail")

@auth_or_redirect
def create_tweet(request):
    if request.POST:
        user_id = request.session['user_id']
        tweetBody = request.POST.get("TweetBody", None)
        media = request.FILES.get("Media", None)

        print((tweetBody, media))

        # To avoid getting a database error
        if tweetBody or media:
            allowed_accounts = request.POST.get("privacy", None)
            if allowed_accounts is None or allowed_accounts == 'Choose Audience':
                allowed_accounts = "PUBLIC"
            else:
                allowed_accounts = allowed_accounts.upper()

            if media:
                media = save_post_media(media)

            print((user_id, tweetBody, media, allowed_accounts))

            with connection.cursor() as cursor:
                newTweetIdVar = 0
                new_post_id_var = 0
                base_notif_id_var = 0
                pm_notif_id_var = 0
                result = cursor.callproc("CREATE_TWEET", [user_id, tweetBody, media, allowed_accounts, newTweetIdVar, new_post_id_var,base_notif_id_var, pm_notif_id_var])

                newTweetIdVar = result[4]
                new_post_id_var = result[5]
                base_notif_id_var = result[6]
                pm_notif_id_var = result[7]

                print(f"tID{newTweetIdVar} pID{new_post_id_var} pm_notif_id{pm_notif_id_var}")
                print(result)
                insert_mention_notif_from_post_text(cursor, tweetBody, base_notif_id_var, pm_notif_id_var, new_post_id_var)

                connection.commit()
                return redirect(reverse('detailedTweetView', kwargs={"tweetID": result[4]}))

        return HttpResponse("something went wrong during tweet submission")

def save_post_media(media):
    fs = FileSystemStorage()
    media_name = fs.save(media.name, media)
    return fs.url(media_name)

#no need for auth outside of ability to comment
def detailed_tweet_view(request, tweetID):
    print("TWEET %s" % tweetID)
    with connection.cursor() as cursor:
        user_id = request.session.get("user_id")

        cursor.execute("SELECT a.ACCOUNTNAME, a.PROFILE_PHOTO,  p.TEXT, p.MEDIA, p.TIMESTAMP, p.ID "
                       "FROM TWEET t JOIN POST p on(t.POST_ID = p.ID)"
                       "join ACCOUNT_POSTS_POST app on(t.POST_ID = app.POST_ID)"
                       "join ACCOUNT a on(a.ID = app.ACCOUNT_ID)WHERE t.TWEET_ID = %s", (tweetID,))
        result = cursor.fetchone()

        #TODO fetch retweet, like, comment count
        if result is not None:
            tweet = {
                "AUTHOR": result[0],
                "PROFILE_PHOTO": result[1],
                "TEXT": result[2],
                "MEDIA": result[3],
                "TIMESTAMP": result[4],
                "POST_ID": result[5],
                "COMMENTLINK": reverse("detailedTweetView", kwargs={"tweetID": tweetID}) + "#tweet-reply-box",
            }

            comment_chains = get_tweet_comment_chains(cursor, tweetID)
            mark_comment_chain_like_bookmark(cursor,comment_chains, user_id)

            mark_post_like_bookmark(cursor, user_id, tweet)

            notification_count = cursor.callfunc("get_unseen_notif_count", int, [user_id])

            context = {
                "notification_count": notification_count,
                "tweet": tweet,
                "TWEETID": tweetID,#use for generating link for comment reply button
                "USERLOGGEDIN": is_user_authenticated(request),
                "COMMENTCHAINS": comment_chains,
            }

            print(context)
            return render(request, "DetailedTweetView.html", context)

    return HttpResponse("TWEET DOES NOT EXIST")

def mark_post_like_bookmark(cursor, user_id, post):
    cursor.execute(f"SELECT COUNT(*) FROM ACCOUNT_LIKES_POST WHERE ACCOUNT_ID={user_id} AND POST_ID={post['POST_ID']};")
    count = cursor.fetchone()[0]

    if int(count) == 1:
        post["LIKED"] = True

    cursor.execute(f"SELECT COUNT(*) FROM ACCOUNT_BOOKMARKS_POST WHERE ACCOUNT_ID={user_id} AND POST_ID={post['POST_ID']};")
    count = cursor.fetchone()[0]

    if int(count) == 1:
        post["BOOKMARKED"] = True

def mark_comment_chain_like_bookmark(cursor, comment_chains, userID):
    for chain in comment_chains:
        print(f"cch {chain[0]}")
        mark_post_like_bookmark(cursor, userID, chain[0])
        for reply in chain[1]:
            mark_post_like_bookmark(cursor, userID, reply)
