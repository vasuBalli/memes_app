from django.urls import path
from .views import *
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('memes/', get_memes, name='get_memes'),
    path('privacy_policy/', privacy_policy),
    path('webhook/', webhook),
    path('feed/', feed, name='feed'),
    path("reels/", reels_feed, name="reels"),
    path("like/", toggle_like),
    path("bookmark/", toggle_bookmark),
    path("view/", track_view),
 ]+ static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)