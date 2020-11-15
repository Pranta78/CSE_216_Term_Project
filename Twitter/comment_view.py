from django.db import connection
from django.http import HttpResponse
from django.shortcuts import render, redirect
from django.urls import reverse

from Twitter.auth import auth_or_redirect


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
        result = cursor.execute("SELECT t.TWEET_ID, a.id, a.ACCOUNTNAME, a.PROFILE_PHOTO, p.TEXT, p.MEDIA, p.TIMESTAMP, p.ID "
                                         "FROM TWEET t "
                                         "JOIN TWEET_COMMENT c on (t.TWEET_ID = c.TWEET_ID)"
                                         "JOIN POST p on(c.POST_ID = p.ID)"
                                         "JOIN ACCOUNT_POSTS_POST app on(app.POST_ID = c.POST_ID)"
                                         "JOIN ACCOUNT a on (app.ACCOUNT_ID = a.ID)"
                                         "WHERE c.COMMENT_ID =  %s", [commentID]).fetchone()
        print(f"commanet reply {result}")

        if result is not None:
            if request.POST:
                return create_comment(request,result[0], commentID)
            else:
                comment = {
                    "AUTHOR": result[2],
                    "AUTHORPHOTO": result[3],
                    "TEXT": result[4],
                    "MEDIA": result[5],
                    "TIMESTAMP": result[6],
                    "POST_ID": result[7],
                    "COMMENTLINK": "/create/reply/comment/%s" % commentID,
                }  # your setup requires a separate tweet object
                # would also be nice to set project rules for template context strings(i.e should they be full caps or not)

                context = {
                    "comment": comment,
                    "COMMENTID": commentID,  # use for generating link for comment reply button
                    "POST_ID":  result[7],
                    "USERLOGGEDIN": True,
                }
                return render(request, "CommentReplyView.html", context)
        return HttpResponse("invalid parent comment id for comment")
    return HttpResponse("invalid GET request on POST URL")


@auth_or_redirect
def create_comment(request, tweetID, parentCommentID):
    if request.POST:
        user_id = request.session['user_id']
        #TODO verify form data has correct user_id, commment_id
        commentBody = request.POST.get("CommentBody", None)
        media = request.FILES.get("Media", None)

        # To avoid getting a database error
        if commentBody or media:
            allowed_accounts = request.POST.get("privacy", None)#TODO This is pointless for comments. Update schema

            if allowed_accounts is None:
                allowed_accounts = "PUBLIC"
            else:
                allowed_accounts = allowed_accounts.upper()

            print(f"comment,  media {media}")
            if media:
                from django.core.files.storage import FileSystemStorage
                fs = FileSystemStorage()
                media_name = fs.save(media.name, media)
                media = fs.url(media_name)
                print(f"finally, media {media}")

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
                connection.commit()
                return redirect(reverse('detailedTweetView', kwargs={"tweetID": tweetID}))#TODO add comment chain focused view

            return HttpResponse("something went wrong during comment submission")

    return HttpResponse("invalid GET request on POST URL")


def __organizeCommentChains(comment_results):
    comment_chains = []#list of lists, first entry = root, anything after is a replay in that chain
    chain_dict = {}
    parent_dict ={}#temp disjoint set
    for result_row in comment_results:
        comment_id = result_row[7]

        comment = {
            "AUTHOR": result_row[1],
            "PROFILE_PHOTO": result_row[2],
            "TEXT": result_row[3],
            "MEDIA": result_row[4],
            "TIMESTAMP": result_row[5],
            "POST_ID": result_row[6],
            "replied_to": result_row[8],
            "COMMENTLINK": "/create/reply/comment/%s" % comment_id,
        }

        parent_dict[comment_id] = result_row[6]
        chain_root_id = __find_comment_parent_helper(comment_id, parent_dict)
        print(comment)
        if chain_root_id not in chain_dict:
            chain_dict[chain_root_id] = len(comment_chains)
            comment_chains.append([comment])
        else:
            comment_chains[chain_dict[chain_root_id]].append(comment)
    print(comment_chains)
    return comment_chains


def __find_comment_parent_helper(cur_comment_id, parent_dict):
    if parent_dict.get(cur_comment_id) is None:
        return cur_comment_id
    parent_dict[cur_comment_id] = __find_comment_parent_helper(parent_dict[cur_comment_id], parent_dict)#path compression
    return parent_dict[cur_comment_id]