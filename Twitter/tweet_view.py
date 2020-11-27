from django.http import HttpResponse
from django.db import connection
from django.shortcuts import render, redirect
from django.urls import reverse
from django.core.files.storage import FileSystemStorage
from .auth import auth_or_redirect, is_user_authenticated
from .comment_view import __organizeCommentChains
import re

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