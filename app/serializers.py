# app/serializers.py
from bson import ObjectId
import datetime

def meme_to_dict(meme):
    """
    Convert MongoEngine Document to plain dict for JsonResponse.
    """
    data = {
        "id": str(meme.id),
        "title": meme.title,
        "file_url": meme.file,
        "tags": meme.tags or [],
        "user_name": meme.user_name,
        "thumbnail": meme.thumbnail,
        "created_at": meme.created_at.isoformat() if isinstance(meme.created_at, datetime.datetime) else meme.created_at,
        "type": meme.type,
        "language": meme.language,
        "likes_count": meme.likes_count or 0,
        "views_count": meme.views_count or 0,
        "bookmarks_count": meme.bookmarks_count or 0,
    }
    return data

def memes_list_to_dict(memes_queryset):
    return [meme_to_dict(m) for m in memes_queryset]
