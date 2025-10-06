from django.urls import path
from .views import *

urlpatterns = [
    path('memes/', get_memes, name='get_memes'),
]