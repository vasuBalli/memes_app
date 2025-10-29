
from django.db import models
from cloudinary.models import CloudinaryField

#testingg

class Memes(models.Model):
    TYPE_CHOICES = (
        ('image', 'Image'),
        ('video', 'Video'),
    )
    language = (
        ('telugu', 'Tel'),
        ('english', 'Eng'),
    )

    title = models.CharField(max_length=100,null=True, blank=True)
    file = CloudinaryField(resource_type="auto", null=True, blank=True)
    tags = models.CharField(max_length=200, blank=True)
    user_name = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    type = models.CharField(max_length=50, choices=TYPE_CHOICES, null=True, blank=True)
    language = models.CharField(max_length=50, choices=language, null=True, blank=True)

    def __str__(self):
        return self.title



