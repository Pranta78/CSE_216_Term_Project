from django.http import HttpResponse
from django.db import connection
from django.shortcuts import render, redirect
from django.urls import reverse
from django.core.files.storage import FileSystemStorage
from .auth import auth_or_redirect, is_user_authenticated
from .comment_view import __organizeCommentChains
import re


@auth_or_redirect
def create_retweet(request, post_id):
    #TODO do sanity check that post_id is valid
    user_id = request.session['user_id']
    if request.POST:
        text = request.POST["TEXT"]
        if user_id and post_id:
            with connection.cursor() as cursor:
                msg = ''
                pm_notification_id = 0
                retweeted_author_id = 0
                result = cursor.callproc("RETWEET_POST", [text,  post_id, user_id, retweeted_author_id, pm_notification_id])
                retweeted_author_id = result[3]
                pm_notification_id = result[4]
                retweeted_author_name = cursor.execute('''SELECT ACCOUNTNAME FROM ACCOUNT WHERE ID = %s;''', [retweeted_author_id]).fetchone()

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

            result = cursor.execute('''
            SELECT
                POST_ID, TIMESTAMP, TEXT, MEDIA,AUTHOR, PROFILE_PHOTO, TWEET_ID
            FROM 
                TWEET_VIEW 
            WHERE 
                POST_ID = %s  
            ''', [post_id]).fetchone()

            if result is None:
                result = cursor.execute('''
                SELECT
                    POST_ID, TIMESTAMP, TEXT, MEDIA,AUTHOR, PROFILE_PHOTO, COMMENT_ID
                FROM 
                    COMMENT_VIEW 
                WHERE 
                    POST_ID =  %s           
                ''', [post_id]).fetchone()

            if result is None:
                return HttpResponse("invalid (account_name, post_ID, pm_notification_ID) for create retweet link")

            context = {
                "AUTHOR": account_name,
                "POST": {
                    "AUTHOR": result[4],
                    "PROFILE_PHOTO": result[5],
                    "TEXT": result[2],
                    "MEDIA": result[3],
                    "TIMESTAMP": result[1],
                    "POST_ID": result[0],
                    "COMMENTLINK": "#tweet-reply-box",
                },
                "USERLOGGEDIN": is_user_authenticated(request),
            }
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

        if result is None:
            cursor.execute('''
            SELECT
                arp.ACCOUNT_ID, (SELECT PROFILE_PHOTO from ACCOUNT WHERE ID = arp.ACCOUNT_ID), arp.TIMESTAMP, arp.TEXT,
                cv.COMMENT_ID, cv.POST_ID, cv.AUTHOR, cv.PROFILE_PHOTO, cv.TEXT, cv.MEDIA, cv.TIMESTAMP
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

        context = {
            "RT": {
                "AUTHOR": account_name,
                "AUTHOR_PROFILE_PHOTO": result[1],
                "TIMESTAMP": result[2],
                "TEXT": result[3],
                "POST": {
                    "AUTHOR": result[6],
                    "PROFILE_PHOTO": result[7],
                    "TEXT": result[8],
                    "MEDIA": result[9],
                    "TIMESTAMP": result[10],
                    "POST_ID": result[5],
                    "COMMENTLINK": "#tweet-reply-box",
                }
            },
            "USERLOGGEDIN": is_user_authenticated(request),
            # "COMMENTCHAINS": comment_chains,
        }

        return  render(request, "DetailedReTweetView.html", context)
    return HttpResponse("Server connectio fail")

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
                if tweetBody:
                    mentions = fetch_mentioned_users_from_post(tweetBody)
                    print(f"mentions {mentions}")
                    if mentions and len(mentions) > 0:
                        for mention in mentions:
                            #CHECK if user valid and no post_mention has already  been created for user for this post
                            result = cursor.execute('''	
                                                    SELECT ACCOUNTNAME
                                                    FROM ACCOUNT a 
                                                    WHERE a.ACCOUNTNAME = %s AND 
                                                        (SELECT count(*)
                                                        FROM POST_MENTIONS_ACCOUNT pma
                                                        JOIN POST_MENTION_NOTIFICATION pmn ON(pmn.POST_MENTION_NOTIFICATION_ID = pma.PM_NOTIFICATION_ID)
                                                        WHERE pma.ACCOUNT_ID = a.ID AND pmn.MENTIONED_POST_ID = %s) = 0
                                                         ''', [mention, new_post_id_var]).fetchone()
                            if result is None:
                                cursor.execute('''
                                                INSERT INTO 
                                                    POST_MENTIONS_ACCOUNT 
                                                VALUES(
                                                   (SELECT ID  from ACCOUNT WHERE ACCOUNTNAME=:username), :pm_notif_id
                                                   )''', {'username': mention, 'pm_notif_id': pm_notif_id_var})
                                cursor.execute('''
                                            INSERT INTO 
                                                NOTIFICATION_NOTIFIES_ACCOUNT 
                                            VALUES(
                                               (SELECT ID  from ACCOUNT WHERE ACCOUNTNAME=:username), :base_notif_id, NULL 
                                               )''',
                                               {'username': mention, 'base_notif_id': base_notif_id_var, })
                #todo implemnt in comment
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
            #TODO VIEWS to alleviate the suffering
            cursor.execute( "SELECT a.id, a.ACCOUNTNAME, a.PROFILE_PHOTO, p.TEXT, p.MEDIA, p.TIMESTAMP, p.ID, c.COMMENT_ID, c.PARENT_COMMENT_ID, pa.ACCOUNTNAME "
                            "FROM TWEET t "
                            "JOIN TWEET_COMMENT c on (t.TWEET_ID = c.TWEET_ID)"
                            "LEFT OUTER JOIN TWEET_COMMENT pc on (pc.COMMENT_ID = c.PARENT_COMMENT_ID)"
                            "LEFT OUTER JOIN ACCOUNT_POSTS_POST papp on(papp.POST_ID = pc.POST_ID)"
                            "LEFT OUTER JOIN ACCOUNT pa on(papp.ACCOUNT_ID = pa.ID)"
                            "JOIN POST p on(c.POST_ID = p.ID)"
                            "JOIN ACCOUNT_POSTS_POST app on(app.POST_ID = c.POST_ID)"
                            "JOIN ACCOUNT a on (app.ACCOUNT_ID = a.ID)"
                            "WHERE t.TWEET_ID = %s "
                            "ORDER BY p.TIMESTAMP ", [tweetID])#orderby ensures that root of the chain is accessed first
            comment_results = cursor.fetchall()
            print(comment_results)
            comment_chains = __organizeCommentChains(comment_results)
            for comment_chain in comment_chains:
                for comment in comment_chain:
                    cursor.execute(f"SELECT COUNT(*) FROM ACCOUNT_LIKES_POST WHERE ACCOUNT_ID={user_id} AND POST_ID={comment['POST_ID']};")
                    count = cursor.fetchone()[0]

                    if int(count) == 1:
                        comment["LIKED"] = True

                    cursor.execute(f"SELECT COUNT(*) FROM ACCOUNT_BOOKMARKS_POST WHERE ACCOUNT_ID={user_id} AND POST_ID={comment['POST_ID']};")
                    count = cursor.fetchone()[0]

                    if int(count) == 1:
                        comment["BOOKMARKED"] = True

            comment_chains.reverse()

            tweet = {
                "AUTHOR": result[0],
                "PROFILE_PHOTO": result[1],
                "TEXT": result[2],
                "MEDIA": result[3],
                "TIMESTAMP": result[4],
                "POST_ID": result[5],
                "COMMENTLINK": "#tweet-reply-box",
            }#your setup requires a separate tweet object
            #would also be nice to set project rules for template context strings(i.e should they be full caps or not)

            cursor.execute(f"SELECT COUNT(*) FROM ACCOUNT_LIKES_POST WHERE ACCOUNT_ID={user_id} AND POST_ID={result[5]};")
            count = cursor.fetchone()[0]

            if int(count) == 1:
                tweet["LIKED"] = True

            cursor.execute(f"SELECT COUNT(*) FROM ACCOUNT_BOOKMARKS_POST WHERE ACCOUNT_ID={user_id} AND POST_ID={result[5]};")
            count = cursor.fetchone()[0]

            if int(count) == 1:
                tweet["BOOKMARKED"] = True

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


def fetch_mentioned_users_from_post(post_body):
    regex = '@(\w+)'
    return re.findall(regex, post_body)
