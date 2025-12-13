# app/models.py
from mongoengine import Document, StringField, ListField, DateTimeField, IntField
import datetime

class Memes(Document):
    meta = {
        'collection': 'memes',
        'indexes': [
            '-created_at',
            'tags',
            'type',
        ]
    }

    title = StringField(max_length=5000)
    # store cloudinary secure URLs as strings
    file = StringField()
    tags = ListField(StringField(), default=list)
    user_name = StringField(max_length=1000)
    thumbnail = StringField()
    created_at = DateTimeField(default=datetime.datetime.utcnow)
    type = StringField(choices=('image', 'video'))
    language = StringField(choices=('telugu', 'english'))
    likes_count = IntField(default=0)
    views_count = IntField(default=0)
    bookmarks_count = IntField(default=0)
    share_count = IntField(default=0)


class UserInteraction(Document):
    meta = {
        "collection": "user_interactions",
        "indexes": ["device_id"]
    }

    device_id = StringField(required=True, unique=True)
    liked_memes = ListField(StringField(), default=list)
    bookmarked_memes = ListField(StringField(), default=list)
    viewed_memes = ListField(StringField(), default=list)

    created_at = DateTimeField(default=datetime.datetime.utcnow)
    updated_at = DateTimeField(default=datetime.datetime.utcnow)

    def touch(self):
        self.updated_at = datetime.datetime.utcnow()
        self.save()