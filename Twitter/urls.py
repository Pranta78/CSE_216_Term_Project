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
from .views import (create_account, login, home_page,
                    profile_edit, test, logout, navbar, profile,
                    skeleton, message, inbox, user_profile)

urlpatterns = [
    url(r'^admin/', admin.site.urls),
    url(r'^create-account/', create_account),
    url(r'^login/', login),
    url(r'^logout/', logout),
    url(r'^home/', home_page),
    url(r'^profile/', profile),
    url(r'^profile-edit/', profile_edit),
    url(r'^test/', test),
    url(r'^navbar/', navbar),
    url(r'^skeleton/', skeleton),
    url(r'^messages/', message),
    url(r'^user/(\w+)/$', user_profile, name='user_profile'),
    url(r'^inbox/(\w+)/$', inbox, name='user_inbox'),
]
