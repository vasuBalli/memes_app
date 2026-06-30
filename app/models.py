# app/models.py

from django.db import models

class Memes(models.Model):

    TYPE_CHOICES = (
        ('image', 'Image'),
        ('video', 'Video'),
    )

    LANGUAGE_CHOICES = (
        ('telugu', 'Telugu'),
        ('english', 'English'),
    )

    title = models.CharField(max_length=5000)

    # Cloudinary URL
    file = models.URLField(max_length=1000)

    tags = models.JSONField(default=list, blank=True)

    user_name = models.CharField(max_length=1000, blank=True)

    thumbnail = models.URLField(
        max_length=1000,
        blank=True,
        null=True
    )

    created_at = models.DateTimeField(auto_now_add=True)

    type = models.CharField(
        max_length=20,
        choices=TYPE_CHOICES
    )

    language = models.CharField(
        max_length=20,
        choices=LANGUAGE_CHOICES
    )

    likes_count = models.IntegerField(default=0)
    views_count = models.IntegerField(default=0)
    bookmarks_count = models.IntegerField(default=0)
    share_count = models.IntegerField(default=0)

class Meta:
    ordering = ['-created_at']
    indexes = [
        models.Index(fields=['created_at']),
        models.Index(fields=['type']),
    ]

    def __str__(self):
        return self.title


class NginxDailyTraffic(models.Model):


    date = models.DateField(unique=True)

    total_requests = models.IntegerField(default=0)

    human_requests = models.IntegerField(default=0)
    bot_requests = models.IntegerField(default=0)

    human_unique_visitors = models.IntegerField(default=0)
    bot_unique_visitors = models.IntegerField(default=0)

class Meta:
    ordering = ['-date']

    def __str__(self):
        return str(self.date)


class UserInteraction(models.Model):


    device_id = models.CharField(
        max_length=255,
        unique=True
    )

    liked_memes = models.JSONField(
        default=list,
        blank=True
    )

    bookmarked_memes = models.JSONField(
        default=list,
        blank=True
    )

    viewed_memes = models.JSONField(
        default=list,
        blank=True
    )

    created_at = models.DateTimeField(auto_now_add=True)

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=['device_id'])
        ]

    def touch(self):
        self.save()

    def __str__(self):
        return self.device_id
