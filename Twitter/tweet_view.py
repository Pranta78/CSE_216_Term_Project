from django.http import HttpResponse
from django.db import connection
from django.shortcuts import render, redirect
from django.urls import reverse

from .auth import auth_or_redirect, is_user_authenticated

#Working on the same view.py file together is a recipe for merge conflicts
#I have separated the tweet part into a different py file.
#Ideally, this should be a separate app but this is sufficient for now
#It'd be best if you separate your stuff as well
from .comment_view import __organizeCommentChains


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
                from django.core.files.storage import FileSystemStorage
                fs = FileSystemStorage()
                media_name = fs.save(media.name, media)
                media = fs.url(media_name)

            print((user_id, tweetBody, media, allowed_accounts))

            with connection.cursor() as cursor:
                newTweetIdVar = 0
                result = cursor.callproc("CREATE_TWEET", [user_id, tweetBody, media, allowed_accounts, newTweetIdVar])
                print(result[4])
                return redirect(reverse('detailedTweetView', kwargs={"tweetID": result[4]}))

        return HttpResponse("something went wrong during tweet submission")


#no need for auth outside of ability to comment
def detailed_tweet_view(request, tweetID):
    print("TWEET %s" % tweetID)
    with connection.cursor() as cursor:
        cursor.execute("SELECT a.ACCOUNTNAME, a.PROFILE_PHOTO,  p.TEXT, p.MEDIA, p.TIMESTAMP "
                       "FROM TWEET t JOIN POST p on(t.POST_ID = p.ID)"
                       "join ACCOUNT_POSTS_POST app on(t.POST_ID = app.POST_ID)"
                       "join ACCOUNT a on(a.ID = app.ACCOUNT_ID)WHERE t.TWEET_ID = %s", (tweetID,))
        result = cursor.fetchone()

        #TODO fetch retweet, like, comment count

        if result is not None:
            #TODO VIEWS to alleviate the suffering
            cursor.execute("SELECT a.id, a.ACCOUNTNAME, a.PROFILE_PHOTO, p.TEXT, p.MEDIA, p.TIMESTAMP, c.COMMENT_ID, c.PARENT_COMMENT_ID "
                           "FROM TWEET t "
                           "JOIN TWEET_COMMENT c on(t.TWEET_ID = c.TWEET_ID) "
                           "JOIN POST p on(c.POST_ID =  p.ID) "
                           "JOIN ACCOUNT_POSTS_POST app on(app.POST_ID = c.POST_ID) "
                           "JOIN ACCOUNT a on (app.ACCOUNT_ID = a.ID) "
                           "WHERE t.TWEET_ID = %s "
                           "ORDER BY p.TIMESTAMP ", [tweetID])#orderby ensures that root of the chain is accessed first
            comment_results = cursor.fetchall()
            print(comment_results)
            comment_chains = __organizeCommentChains(comment_results)
            comment_chains.reverse()
            
            tweet = {
                "AUTHOR": result[0],
                "PROFILE_PHOTO": result[1],
                "TEXT": result[2],
                "MEDIA": result[3],
                "TIMESTAMP": result[4],
                "COMMENTLINK": "#tweet-reply-box",
            }#your setup requires a separate tweet object
            #would also be nice to set project rules for template context strings(i.e should they be full caps or not)

            context = {
                "tweet": tweet,
                "TWEETID": tweetID,#use for generating link for comment reply button
                "USERLOGGEDIN": is_user_authenticated(request),
                "COMMENTCHAINS": comment_chains,
            }
            print(context)
            return render(request, "DetailedTweetView.html", context)

    return HttpResponse("TWEET DOES NOT EXIST")


