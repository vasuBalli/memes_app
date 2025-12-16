# app/views.py
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
from django.core.cache import cache
from mongoengine.errors import DoesNotExist, ValidationError
from .models import Memes, UserInteraction
from .serializers import meme_to_dict, memes_list_to_dict
import magic
import os
import json
import logging
import requests
import cloudinary.uploader
import yt_dlp


logger = logging.getLogger('app_logger')

COOKIES_PATH = "/home/ubuntu/memes_app/instagram_cookies.txt"
TEMP_DIR = os.path.join(settings.BASE_DIR, "memeverse")

def get_or_create_user_by_device(device_id: str) -> UserInteraction:
    user = UserInteraction.objects(device_id=device_id).first()
    if not user:
        user = UserInteraction(device_id=device_id)
        user.save()
    return user

# ---------- Pagination helper ----------
import math
def paginate_mongo_queryset(queryset, page=1, per_page=10):
    if page < 1:
        page = 1
    total_items = queryset.count()
    total_pages = math.ceil(total_items / per_page) if total_items else 0
    skip = (page - 1) * per_page
    items = queryset.skip(skip).limit(per_page)
    return items, total_items, total_pages

# ---------- Endpoints ----------

def get_memes(request):
    logger.info("get_memes endpoint accessed")
    try:
        meme_type = request.GET.get('meme_type', None)
        if meme_type:
            queryset = Memes.objects(type=meme_type).order_by('-created_at')
        else:
            queryset = Memes.objects.order_by('-created_at')

        # return all (careful on production); better to paginate in feed endpoint
        data = memes_list_to_dict(queryset)
        for i in data:
            if i.get("file_url"):
                i["file_url"] = i["file_url"].replace("http://", "https://")
        return JsonResponse({"status": "success", "data": data})
    except Exception as e:
        logger.exception("Error fetching memes")
        return JsonResponse({"status": "error", "message": str(e)}, status=500)


def reels_feed(request):
    logger.info("reels_feed endpoint accessed")
    try:
        page = int(request.GET.get('page', 1))
        per_page = int(request.GET.get('per_page', 10))

        queryset = Memes.objects(type="video").order_by('-created_at')

        items, total_items, total_pages = paginate_mongo_queryset(queryset, page=page, per_page=per_page)
        data = memes_list_to_dict(items)

        for item in data:
            if item.get("file_url"):
                item["file_url"] = item["file_url"].replace("http://", "https://")

        return JsonResponse({
            "status": "success",
            "page": page,
            "per_page": per_page,
            "total_pages": total_pages,
            "total_items": total_items,
            "has_next": page < total_pages,
            "has_previous": page > 1,
            "data": data
        })
    except Exception as e:
        logger.exception("Error in reels_feed API")
        return JsonResponse({"status": "error", "message": str(e)}, status=500)
@csrf_exempt
def toggle_like(request):
    try:
          # ✅ SAFE JSON PARSE (NO CRASH)
       
        logger.info(f"method: {request.method}")
        logger.info(f"body: {request.body}")
        if request.method != "POST":
            return JsonResponse(
                {"status": "error", "message": "POST method required"},
                status=405
            )

        if not request.body:
            return JsonResponse(
                {"status": "error", "message": "Empty request body"},
                status=400
            )
        body = json.loads(request.body.decode("utf-8"))
        meme_id = body.get("meme_id")
        device_id = body.get("device_id")

        if not meme_id or not device_id:
            return JsonResponse(
                {"status": "error", "message": "meme_id and device_id required"},
                status=400
            )

        user = get_or_create_user_by_device(device_id)
        meme = Memes.objects.get(id=meme_id)
        if meme_id in user.liked_memes:
            user.liked_memes.remove(meme_id)
            meme.likes_count = max(meme.likes_count - 1, 0)
            liked = False
        else:
            user.liked_memes.append(meme_id)
            meme.likes_count += 1
            liked = True

        user.touch()
        meme.save()

        return JsonResponse({
            "status": "success",
            "liked": liked,
            "likes_count": meme.likes_count
        })

    except Exception as e:
        logger.exception("toggle_like error")
        return JsonResponse({"status": "error", "message": str(e)}, status=500)


@csrf_exempt
def toggle_bookmark(request):
    try:
        body = json.loads(request.body.decode("utf-8"))
        meme_id = body.get("meme_id")
        device_id = body.get("device_id")

        if not meme_id or not device_id:
            return JsonResponse(
                {"status": "error", "message": "meme_id and device_id required"},
                status=400
            )

        user = get_or_create_user_by_device(device_id)
        meme = Memes.objects.get(id=meme_id)

        if meme_id in user.bookmarked_memes:
            user.bookmarked_memes.remove(meme_id)
            meme.bookmarks_count = max(meme.bookmarks_count - 1, 0)
            bookmarked = False
        else:
            user.bookmarked_memes.append(meme_id)
            meme.bookmarks_count += 1
            bookmarked = True

        user.touch()
        meme.save()

        return JsonResponse({
            "status": "success",
            "bookmarked": bookmarked,
            "bookmarks_count": meme.bookmarks_count
        })

    except Exception as e:
        logger.exception("toggle_bookmark error")
        return JsonResponse({"status": "error", "message": str(e)}, status=500)

@csrf_exempt
def track_view(request):
    try:
        body = json.loads(request.body.decode("utf-8"))
        meme_id = body.get("meme_id")
        device_id = body.get("device_id")

        if not meme_id or not device_id:
            return JsonResponse({"status": "error"}, status=400)

        user = get_or_create_user_by_device(device_id)
        meme = Memes.objects.get(id=meme_id)
        if meme_id not in user.viewed_memes:
            user.viewed_memes.append(meme_id)
            meme.views_count += 1
            user.touch()
            meme.save()


        return JsonResponse({"status": "success"})

    except Exception:
        return JsonResponse({"status": "error"}, status=500)
    
def post_details(request):
    """
    Get a single post/meme by ID
    Optional: device_id to return like/bookmark status
    """
    try:
        post_id = request.GET.get("post_id")
        device_id = request.GET.get("device_id")  # optional

        if not post_id:
            return JsonResponse(
                {"status": "error", "message": "post_id is required"},
                status=400
            )

        # Fetch post
        meme = Memes.objects.get(id=post_id)

        # Convert to dict using your existing serializer
        data = meme_to_dict(meme)

        # Ensure https
        if data.get("file_url"):
            data["file_url"] = data["file_url"].replace("http://", "https://")

        # Defaults
        data["is_liked"] = False
        data["is_bookmarked"] = False

        # If device_id is provided, check user interactions
        if device_id:
            user = UserInteraction.objects(device_id=device_id).first()
            if user:
                data["is_liked"] = post_id in user.liked_memes
                data["is_bookmarked"] = post_id in user.bookmarked_memes

        return JsonResponse({
            "status": "success",
            "data": data
        })

    except DoesNotExist:
        return JsonResponse(
            {"status": "error", "message": "Post not found"},
            status=404
        )
    except ValidationError:
        return JsonResponse(
            {"status": "error", "message": "Invalid post_id"},
            status=400
        )
    except Exception as e:
        logger.exception("Error in post_details API")
        return JsonResponse(
            {"status": "error", "message": str(e)},
            status=500
        )

def feed(request):
    logger.info("feed endpoint accessed")
    try:
        page = int(request.GET.get('page', 1))
        per_page = int(request.GET.get('per_page', 10))
        # device_id = request.GET.get('device_id', "")
        # if not device_id:
        #     get_or_create_user_by_device(device_id)
        queryset = Memes.objects.order_by('-created_at')
        items, total_items, total_pages = paginate_mongo_queryset(queryset, page=page, per_page=per_page)
        data = memes_list_to_dict(items)

        for item in data:
            if item.get("file_url"):
                item["file_url"] = item["file_url"].replace("http://", "https://")

        return JsonResponse({
            "status": "success",
            "page": page,
            "per_page": per_page,
            "total_pages": total_pages,
            "total_items": total_items,
            "has_next": page < total_pages,
            "has_previous": page > 1,
            "data": data
        })
    except Exception as e:
        logger.exception("Error in feed API")
        return JsonResponse({"status": "error", "message": str(e)}, status=500)


# ---------- Instagram download + upload helpers (adapted) ----------

def download_and_upload_instagram_video(url, language="english"):
    logger.info(f"Downloading Instagram video from URL: {url}")
    try:
        temp_dir = TEMP_DIR
        os.makedirs(temp_dir, exist_ok=True)
        ydl_opts = {
            'outtmpl': os.path.join(temp_dir, '%(id)s.%(ext)s'),
            'cookies': COOKIES_PATH,
            'format': 'best',
            'merge_output_format': 'mp4',
            'quiet': True,
            'noplaylist': True,
            'no_cookies_update': True,
            'retries': 3,
            'http_headers': {
                'User-Agent': (
                    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '    
                    'AppleWebKit/537.36 (KHTML, like Gecko) '
                    'Chrome/125.0 Safari/537.36'
                ),
                'Accept-Language': 'en-US,en;q=0.9',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            },
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            file_path = ydl.prepare_filename(info)
            if not file_path.endswith('.mp4'):
                file_path = f"{os.path.splitext(file_path)[0]}.mp4"

        title = info.get("title") or "Instagram Video"
        description = info.get("description") or ""
        uploader = info.get("uploader") or info.get("uploader_id") or "unknown"

        tags = []
        if description:
            tags = [word.lstrip("#") for word in description.split() if word.startswith("#")]

        # Upload to Cloudinary
        upload_result = cloudinary.uploader.upload(
            file_path,
            resource_type="video",
            folder="instagram_memes"
        )

        thumbnail_url = upload_result.get("thumbnail_url") or upload_result.get("secure_url") or upload_result.get("url")
        file_secure_url = upload_result.get("secure_url") or upload_result.get("url")

        meme = Memes(
            title=title,
            file=file_secure_url,
            thumbnail=thumbnail_url,
            type="video",
            tags=tags,
            user_name=uploader,
            language=language
        )
        meme.save()

        # cleanup
        try:
            os.remove(file_path)
        except Exception:
            pass

        return meme
    except Exception as e:
        logger.exception("Error in download_and_upload_instagram_video")
        return None


def clean_webhook_url(url: str) -> str:
    url = url.replace("\\/", "/")
    url = url.replace("\\", "")
    return url


@csrf_exempt
def webhook(request):
    logger.info("Webhook endpoint accessed")
    if request.method == 'GET':
        try:
            challenge = request.GET.get('hub.challenge')
            return HttpResponse(challenge)
        except Exception as e:
            logger.exception("Webhook verification failed")
            return HttpResponse('Verification failed', status=403)

    elif request.method == 'POST':
        logger.info("Webhook POST request received")
        try:
            data = json.loads(request.body.decode('utf-8'))
            logger.info(f"Webhook payload: {data}")

            x = download_instagram_video(data, language="english")
            logger.info("uploaded successfully (if not None)")
            return JsonResponse({'status': 'received'}, status=200)
        except Exception as e:
            logger.exception("Error handling webhook POST")
            return JsonResponse({'error': str(e)}, status=400)
    else:
        return HttpResponse(status=405)



def download_instagram_video(payload, language="english"):
    logger.info("download_instagram_video called")
    try:
        entry = payload.get("entry", [])[0]
        messaging = entry.get("messaging", [])[0]
        attachment = messaging.get("message", {}).get("attachments", [])[0]

        media_url = clean_webhook_url(attachment.get("payload", {}).get("url") or "")
        title = attachment.get("payload", {}).get("title", "Instagram Media")

        tags_list = [w.lstrip("#") for w in title.split() if w.startswith("#")]

        reel_id = (
            attachment.get("payload", {}).get("reel_video_id")
            or attachment.get("payload", {}).get("id")
            or "unknown_id"
        )

        local_path = os.path.join(TEMP_DIR, f"{reel_id}")
        os.makedirs(TEMP_DIR, exist_ok=True)

        # Download the media
        r = requests.get(media_url, timeout=30)
        with open(local_path, "wb") as f:
            f.write(r.content)

        # Detect REAL file type
        mime = magic.from_file(local_path, mime=True)
        is_video = "video" in mime

        # Upload to Cloudinary with correct resource type
        upload = cloudinary.uploader.upload(
            local_path,
            resource_type="video" if is_video else "image",
            folder="instagram_memes"
        )

        cloud_url = upload["secure_url"]

        # Generate HD thumbnail ONLY for video
        thumbnail_url = None
        if is_video:
            # cloud_name = settings.CLOUDINARY_STORAGE["CLOUD_NAME"]
            public_id = upload["public_id"]
            thumbnail_url = (
                f"https://res.cloudinary.com/dvrmhmvkw/video/upload/"
                f"c_fill,g_auto:face,h_720,w_720,q_auto:good/{public_id}.jpg"
            )

        # Create meme
        meme = Memes(
            title=title[:200],
            file=cloud_url,
            thumbnail=thumbnail_url,
            type="video" if is_video else "image",
            tags=tags_list,
            user_name="Meme Verse",
            language=language,
        )
        meme.save()

        os.remove(local_path)
        return meme

    except Exception as e:
        logger.exception("Error in download_instagram_video")
        return None



def privacy_policy(request):
    logger.info("Privacy policy page accessed")
    html_content = """
    <html>
    <head><title>Privacy Policy</title></head>
    <body style="font-family: Arial; margin: 40px;">
        <h1>Privacy Policy</h1>
        <p>We respect your privacy and are committed to protecting your personal information.</p>
        <p>This application uses the Instagram Graph API to access your public content only 
        with your explicit permission.</p>
        <p>No personal or sensitive information is stored or shared with third parties.</p>
        <p>If you wish to revoke access, you can do so through your Instagram settings at any time.</p>
        <p>For any privacy concerns, contact us at <b>support@yourdomain.com</b>.</p>
    </body>
    </html>
    """
    return HttpResponse(html_content)
