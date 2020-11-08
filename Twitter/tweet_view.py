from django.http import HttpResponse
from django.db import connection
from django.shortcuts import render, redirect
from django.urls import reverse
#working on the same view.py file together is a recipe for merge conflicts
#I have separated the tweet part into a different py file.
#Ideally, this should be a separate app but this is sufficient for now
#It'd be best if you separate your stuff as well

def test(request):
    img_path = 'file:///D:/twitter/download.png'
    context = {"img_path": img_path}
    template_name = "test.html"
    return render(request, template_name, context)

def createTweet(request):
    if request.POST:
        if request.session['user_id'] is None:
            return redirect("/login")
        user_id = request.session['user_id']
        tweetBody = request.POST.get("TweetBody", None)
        media = request.POST.get("Media", None)
        
        allowed_accounts = request.POST.get("privacy", None)
        if allowed_accounts is None:
            allowed_accounts = "PUBLIC"
        else:
            allowed_accounts = allowed_accounts.upper()

        print((user_id, tweetBody, media, allowed_accounts))

        with connection.cursor() as cursor:
            newTweetIdVar = 0
            result = cursor.callproc("CREATE_TWEET", (user_id, tweetBody, media, allowed_accounts, newTweetIdVar))
            print(result[4])
            return redirect(reverse('detailedTweetView', kwargs={"tweetID": result[4]}))

        return HttpResponse("something went wrong during tweet submission")


def detailedTweetView(request, tweetID):
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
            tweet = {
                "AUTHOR": result[0],
                "userphoto": result[1],
                "TEXT": result[2],
                "MEDIA": result[3],
                "TIMESTAMP": result[4]
            }#your setup requires a separarte tweet object

            context = {
                "tweet": tweet,
            }
            print(context)
            print(request.u)
            return render(request, "DetailedTweetView.html", context)

    return HttpResponse("TWEET DOES NOT EXIST")

