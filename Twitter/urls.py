"""Twitter URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/3.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.conf.urls import url
from django.conf import settings
from django.conf.urls.static import static
from .views import (create_account, login, home_page,
                    logout, skeleton, bookmark)

from .profile_view import profile, profile_edit, user_profile, follower, following, viewLikedPosts, viewPostedTweets
from .message_view import message, inbox

from .tweet_view import detailed_tweet_view, create_tweet
from .comment_view import create_reply_tweet, create_reply_comment
from .auth import deco_test

urlpatterns = [
    url(r'^admin/', admin.site.urls),
    url(r'^create-account/', create_account),
    url(r'^login/', login, name='login'),
    url(r'^logout/', logout),
    url(r'^home/', home_page),
    url(r'^profile/', profile),
    url(r'^profile-edit/', profile_edit),
    url(r'^skeleton/', skeleton),
    url(r'^messages/', message),
    url(r'^bookmarks/', bookmark),
    url(r'^user/(\w+)/$', user_profile, name='user_profile'),
    url(r'^user/(\w+)/followers/$', follower, name='user_profile_follower'),
    url(r'^user/(\w+)/following/$', following, name='user_profile_following'),
    url(r'^user/(\w+)/tweets/$', viewPostedTweets, name='user_profile_tweets'),
    url(r'^user/(\w+)/likes/$', viewLikedPosts, name='user_profile_likes'),
    url(r'^inbox/(\w+)/$', inbox, name='user_inbox'),
    url(r'^create/tweet/', create_tweet),
    url(r'^create/reply/tweet/(?P<tweetID>\w+)/$', create_reply_tweet),
    url(r'^create/reply/comment/(?P<commentID>\w+)/$', create_reply_comment),
    url(r'^tweet/(?P<tweetID>\w+)/$', detailed_tweet_view, name='detailedTweetView'),
    url(r'^decotest/', deco_test),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
