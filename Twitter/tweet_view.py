from django.http import HttpResponse
from django.db import connection
from django.shortcuts import render, redirect
from django.urls import reverse

from .auth import auth_or_redirect, is_user_authenticated

#Working on the same view.py file together is a recipe for merge conflicts
#I have separated the tweet part into a different py file.
#Ideally, this should be a separate app but this is sufficient for now
#It'd be best if you separate your stuff as well

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

@auth_or_redirect
def create_reply_tweet(request, tweetID):
    with connection.cursor() as cursor:
        tweet_id_result = cursor.execute("SELECT TWEET_ID FROM TWEET WHERE TWEET_ID = %s", [tweetID]).fetchone()
        if tweet_id_result is not None:
            return create_comment(request, tweetID, None)

    return HttpResponse("invalid parent tweet id for comment")

@auth_or_redirect
def create_reply_comment(request, commentID):
    with connection.cursor() as cursor:
        tweet_id_result = cursor.execute("SELECT t.TWEET_ID "
                                          "FROM TWEET t "
                                          "join TWEET_COMMENT c on (t.TWEET_ID = c.TWEET_ID)"
                                          "WHERE c.COMMENT_ID =  %s", [commentID]).fetchone()
        if tweet_id_result is not None:
            create_comment(request,tweet_id_result[0], commentID)
    return HttpResponse("invalid parent comment id for comment")

@auth_or_redirect
def create_comment(request, tweetID, parentCommentID):
    if request.POST:
        user_id = request.session['user_id']
        #TODO verify form data has correct user_id, commment_id
        commentBody = request.POST.get("CommentBody", None)
        media = request.POST.get("Media", None)

        allowed_accounts = request.POST.get("privacy", None)#TODO This is pointless for comments. Update schema

        if allowed_accounts is None:
            allowed_accounts = "PUBLIC"
        else:
            allowed_accounts = allowed_accounts.upper()

        print((user_id, tweetID, commentBody, media, allowed_accounts))

        with connection.cursor() as cursor:
            newCommentID = 0
            # I was getting errors with default parameters so a create_root_comment proc was added
            if parentCommentID is None:
                result = cursor.callproc("CREATE_ROOT_COMMENT", [user_id, tweetID, commentBody, media, allowed_accounts, newCommentID])
            else:
                result = cursor.callproc("CREATE_COMMENT",
                                         [user_id, tweetID, parentCommentID, commentBody, media, allowed_accounts, newCommentID])
            print(result[4])
            return redirect(reverse('detailedTweetView', kwargs={"tweetID": tweetID}))#TODO add comment chain focused view

        return HttpResponse("something went wrong during comment submission")


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

        print("tweetView" + str(result))

        if result is not None:
            #TODO VIEWS to allevaite the suffering
            cursor.execute("SELECT a.id, a.ACCOUNTNAME, a.PROFILE_PHOTO, p.TEXT, p.MEDIA, p.TIMESTAMP  "
                           "FROM TWEET t "
                           "JOIN TWEET_COMMENT c on(t.TWEET_ID = c.TWEET_ID)"
                           "JOIN POST p on(c.POST_ID =  p.ID)"
                           "JOIN ACCOUNT_POSTS_POST app on(app.POST_ID = c.POST_ID)"
                           "JOIN ACCOUNT a on (app.ACCOUNT_ID = a.ID)"
                           "WHERE t.TWEET_ID = %s", [tweetID])

            comments = []
            comment_results = cursor.fetchall()
            for result_row in comment_results:
                comments.append({
                    "AUTHOR": result_row[1],
                    "AUTHORPHOTO": result_row[2],
                    "TEXT": result_row[3],
                    "MEDIA": result_row[4],
                    "TIMESTAMP": result_row[5]
                })

            tweet = {
                "AUTHOR": result[0],
                "AUTHORPHOTO": result[1],
                "TEXT": result[2],
                "MEDIA": result[3],
                "TIMESTAMP": result[4]
            }#your setup requires a separate tweet object
            #would also be nice to set project rules for template context strings(i.e should they be full caps or not)

            context = {
                "tweet": tweet,
                "comments": comments,
                "TWEETID": tweetID,#use for generating link for comment reply button
                "USERLOGGEDIN": is_user_authenticated(request),
            }
            print(context)
            return render(request, "DetailedTweetView.html", context)

    return HttpResponse("TWEET DOES NOT EXIST")

