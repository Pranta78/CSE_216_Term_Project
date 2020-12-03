from django.db import connection
from django.http import HttpResponse
from django.shortcuts import render, redirect
from django.urls import reverse

from Twitter.auth import auth_or_redirect, is_user_authenticated
from .notification_view import insert_mention_notif_from_post_text


@auth_or_redirect
def create_reply_tweet(request, tweetID):
    with connection.cursor() as cursor:
        tweet_id_result = cursor.execute("SELECT TWEET_ID FROM TWEET WHERE TWEET_ID = %s", [tweetID]).fetchone()
        if tweet_id_result is not None:
            return create_comment(request, tweetID, None)

    return HttpResponse("invalid parent tweet id for comment")


@auth_or_redirect
def create_reply_comment(request, commentID):
    user_id = request.session.get("user_id", None)
    with connection.cursor() as cursor:
        result = cursor.execute("SELECT t.TWEET_ID, a.id, a.ACCOUNTNAME, a.PROFILE_PHOTO,"
                                " p.TEXT, p.MEDIA, p.TIMESTAMP, p.ID , a.ID  "
                                 "FROM TWEET t "
                                 "JOIN TWEET_COMMENT c on (t.TWEET_ID = c.TWEET_ID)"
                                 "JOIN POST p on(c.POST_ID = p.ID)"
                                 "JOIN ACCOUNT_POSTS_POST app on(app.POST_ID = c.POST_ID)"
                                 "JOIN ACCOUNT a on (app.ACCOUNT_ID = a.ID)"
                                 "WHERE c.COMMENT_ID =  %s", [commentID]).fetchone()
        print(f"commant reply {result}")

        if result is not None:
            if request.POST:
                return create_comment(request,result[0], commentID)
            else:

                comment = {
                    "AUTHOR": result[2],
                    "PROFILE_PHOTO": result[3],
                    "TEXT": result[4],
                    "MEDIA": result[5],
                    "TIMESTAMP": result[6],
                    "POST_ID": result[7],
                    "COMMENTLINK": "/create/reply/comment/%s" % commentID,
                    "AUTHOR_ID": int(result[8]),
                }
                # would also be nice to set project rules for template context strings(i.e should they be full caps or not)

                notification_count = cursor.callfunc("get_unseen_notif_count", int, [user_id])

                cursor.execute(f"SELECT COUNT(*) FROM ACCOUNT_LIKES_POST WHERE ACCOUNT_ID={user_id} AND POST_ID={comment['POST_ID']};")
                count = cursor.fetchone()[0]

                if int(count) == 1:
                    comment["LIKED"] = True

                cursor.execute(f"SELECT COUNT(*) FROM ACCOUNT_BOOKMARKS_POST WHERE ACCOUNT_ID={user_id} AND POST_ID={comment['POST_ID']};")
                count = cursor.fetchone()[0]

                if int(count) == 1:
                    comment["BOOKMARKED"] = True

                context = {
                    "notification_count": notification_count,
                    "comment": comment,
                    "COMMENTID": commentID,  # use for generating link for comment reply button
                    "POST_ID":  result[7],
                    "USERLOGGEDIN": True,
                    "USER_ID": user_id,
                }

                cursor.execute('''SELECT 
                                        AUTHOR, PROFILE_PHOTO,  TEXT, MEDIA, TIMESTAMP, POST_ID,
                                         COMMENT_ID, "replied_to", ACCOUNT_ID
                                    FROM
                                        COMMENT_VIEW 
                                    WHERE
                                        PARENT_COMMENT_ID = %s
                                    ORDER BY TIMESTAMP ASC''', [commentID]);
                comment_reply_result = cursor.fetchall()
                replies = []
                for reply_result in comment_reply_result:
                    reply = {
                        "AUTHOR": reply_result[0],
                        "PROFILE_PHOTO": reply_result[1],
                        "TEXT": reply_result[2],
                        "MEDIA": reply_result[3],
                        "TIMESTAMP": reply_result[4],
                        "POST_ID": reply_result[5],
                        "replied_to": reply_result[7],
                        "COMMENTLINK": "/create/reply/comment/%s" % reply_result[6],
                        "AUTHOR_ID": int(reply_result[8]),
                    }

                    cursor.execute(f"SELECT COUNT(*) FROM ACCOUNT_LIKES_POST WHERE ACCOUNT_ID={user_id} AND POST_ID={reply['POST_ID']};")
                    count = cursor.fetchone()[0]

                    if int(count) == 1:
                        reply["LIKED"] = True

                    cursor.execute(f"SELECT COUNT(*) FROM ACCOUNT_BOOKMARKS_POST WHERE ACCOUNT_ID={user_id} AND POST_ID={reply['POST_ID']};")
                    count = cursor.fetchone()[0]

                    if int(count) == 1:
                        reply["BOOKMARKED"] = True

                    replies.append(reply)
                context['replies'] = replies
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
            allowed_accounts = request.POST.get("privacy", None)

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
                new_post_id = 0
                new_notif_id = 0
                new_pm_notif_id = 0
                if parentCommentID is None:
                    result = cursor.callproc("CREATE_ROOT_COMMENT",
                                             [user_id, tweetID, commentBody, media, allowed_accounts,
                                              newCommentID, new_notif_id, new_pm_notif_id, new_post_id])
                    new_commentID = result[5]
                    new_notif_id = result[6]
                    new_pm_notif_id = result[7]
                    new_post_id = result[8]
                else:
                    result = cursor.callproc("CREATE_COMMENT",
                                         [user_id, tweetID, parentCommentID, commentBody, media, allowed_accounts,
                                          newCommentID, new_notif_id, new_pm_notif_id, new_post_id])
                    new_commentID = result[6]
                    new_notif_id = result[7]
                    new_pm_notif_id = result[8]
                    new_post_id = result[9]

                insert_mention_notif_from_post_text(cursor, commentBody, new_notif_id, new_pm_notif_id, new_post_id)

                connection.commit()
                return redirect(reverse('detailedTweetView', kwargs={"tweetID": tweetID}))#TODO add comment chain focused view

            return HttpResponse("something went wrong during comment submission")

    return HttpResponse("invalid GET request on POST URL")

def get_tweet_comments_unorganized(cursor, tweet_id):
    result = cursor.execute('''
        SELECT
            POST_ID, TIMESTAMP, TEXT, MEDIA,AUTHOR, PROFILE_PHOTO, COMMENT_ID, "replied_to",
            PARENT_COMMENT_ID, TWEET_ID, ACCOUNT_ID
        FROM 
            COMMENT_VIEW 
        WHERE
            TWEET_ID = %s
        ORDER BY
		    TIMESTAMP ASC
    ''', [tweet_id]).fetchall()

    comments = []
    for result_row in result:
        comment = {
            "AUTHOR": result_row[4],
            "PROFILE_PHOTO": result_row[5],
            "TEXT": result_row[2],
            "MEDIA": result_row[3],
            "TIMESTAMP": result_row[1],
            "POST_ID": result_row[0],
            "COMMENT_ID": result_row[6],
            "PARENT_COMMENT_ID": result_row[8],
            "COMMENTLINK": reverse("comment_reply_view", kwargs={"commentID": result_row[6]}),
            "AUTHOR_ID": int(result_row[10]),
        }
        if result_row[8]:
            comment["replied_to"] = result_row[7]
        comments.append(comment)
    return comments

def organizeCommentChains(comments):
    comment_chains = []#list of lists, first entry = root, anything after is a reply in that chain
    chain_dict = {}
    parent_dict ={}#temp disjoint set
    for comment in comments:
        parent_dict[comment["COMMENT_ID"]] = comment["PARENT_COMMENT_ID"]
        chain_root_id = __find_comment_parent_helper(comment["COMMENT_ID"], parent_dict)
        #print(comment)
        # if chain_root_id not in chain_dict:
        #     chain_dict[chain_root_id] = len(comment_chains)
        #     comment_chains.append([comment])
        # else:
        #     comment_chains[chain_dict[chain_root_id]].append(comment)
        if chain_root_id not in chain_dict:
            chain_dict[chain_root_id] = len(comment_chains)
            comment_chains.append([comment, []])
        else:
            comment_chains[chain_dict[chain_root_id]][1].append(comment)
    print(comment_chains)
    return comment_chains


def __find_comment_parent_helper(cur_comment_id, parent_dict):
    if parent_dict.get(cur_comment_id) is None:
        return cur_comment_id
    parent_dict[cur_comment_id] = __find_comment_parent_helper(parent_dict[cur_comment_id], parent_dict)#path compression
    return parent_dict[cur_comment_id]

def get_tweet_comment_chains(cursor, tweet_id):
    comments = get_tweet_comments_unorganized(cursor, tweet_id)
    return organizeCommentChains(comments)

def get_comment_chain(cursor, tweet_id, comment):#need to fin indirectly parented children too
    comments = get_tweet_comments_unorganized(cursor, tweet_id)
    chains = organizeCommentChains(comments)
    for chain in chains:
        if chain[0]["COMMENT_ID"] == comment["COMMENT_ID"]:
            return chain[1]
    return [[comment, []]]


def __find_comment_parent_helper(cur_comment_id, parent_dict):
    if parent_dict.get(cur_comment_id) is None:
        return cur_comment_id
    parent_dict[cur_comment_id] = __find_comment_parent_helper(parent_dict[cur_comment_id], parent_dict)#path compression
    return parent_dict[cur_comment_id]
