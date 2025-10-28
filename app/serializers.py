from rest_framework import serializers
from .models import Memes

class MemesSerializer(serializers.ModelSerializer):
    file_url = serializers.SerializerMethodField()

    class Meta:
        model = Memes
        # Include all fields you want in the API response
        fields = [
            'id',
            'title',
            'file_url',   # the serialized URL
            'tags',
            'downloads',
            'created_at',
            'type',
            
            'language',
        ]

    def get_file_url(self, obj):
        """Return the actual URL of the Cloudinary file"""
        if obj.file:
            return obj.file.url
        return None
