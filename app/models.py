# app/models.py
from mongoengine import Document, StringField, ListField, DateTimeField
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

    title = StringField(max_length=200)
    # store cloudinary secure URLs as strings
    file = StringField()
    tags = ListField(StringField(), default=list)
    user_name = StringField(max_length=200)
    thumbnail = StringField()
    created_at = DateTimeField(default=datetime.datetime.utcnow)
    type = StringField(choices=('image', 'video'))
    language = StringField(choices=('telugu', 'english'))
