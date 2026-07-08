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
    path("post-details/", post_details), 
    path("signup", signup, name="signup"),
    path("verify_signup", verify_signup, name="verify_signup"),
    path("login", login, name="login"),
    path("logout", logout, name="logout"),
    path("forgot_password", forgot_password, name="forgot_password"),
    path("reset_password", reset_password, name="reset_password"),
    path("like_meme", like_meme, name="like_post"),
    path("view_meme", add_view, name="view_post"),
    path("comment_meme", add_comment, name="comment_post"),
    path("bookmark_meme", bookmark_meme, name="bookmark_post"),
    path("share_meme", share_meme, name="share_post"),
    path("get_comments", get_comments, name="get_comments"),
    path("delete_comment", delete_comment, name="delete_comment"),  
    path("get_bookmarks", get_bookmarked_memes, name="get_bookmarks"), 
    path("get_likes", get_liked_memes, name="get_likes"),
    path("get_watch_history", get_watch_history, name="get_watch_history"),
    path("get_profile", get_profile, name="get_profile"),
    path("update_profile", update_profile, name="update_profile"),

 ]+ static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)