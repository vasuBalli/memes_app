# app/views.py
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
from django.core.cache import cache

from .models import Memes
from .serializers import meme_to_dict, memes_list_to_dict

import os
import json
import logging
import requests
import cloudinary.uploader
import yt_dlp

logger = logging.getLogger('app_logger')

COOKIES_PATH = "/home/ubuntu/memes_app/instagram_cookies.txt"
TEMP_DIR = os.path.join(settings.BASE_DIR, "memeverse")

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


def feed(request):
    logger.info("feed endpoint accessed")
    try:
        page = int(request.GET.get('page', 1))
        per_page = int(request.GET.get('per_page', 10))

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

        media_type = attachment.get("type")                      # ig_reel / image / video
        reel_id = attachment.get("payload", {}).get("reel_video_id") \
                  or attachment.get("payload", {}).get("id") \
                  or "unknown_id"

        title = attachment.get("payload", {}).get("title", "Instagram Media")
        media_url = clean_webhook_url(attachment.get("payload", {}).get("url") or "")

        # Extract hashtags
        tags_list = []
        if title:
            tags_list = [w.lstrip("#") for w in title.split() if w.startswith("#")]

        # Duplicate protection
        lock_key = f"webhook_{reel_id}"
        if cache.get(lock_key):
            logger.info("Duplicate webhook event, skipping.")
            return None
        cache.set(lock_key, True, 120)

        # Decide extension
        ext = "mp4" if media_type == "ig_reel" else "jpg"
        local_path = os.path.join(TEMP_DIR, f"{reel_id}.{ext}")
        os.makedirs(TEMP_DIR, exist_ok=True)

        # Download media
        r = requests.get(media_url, timeout=30)
        with open(local_path, "wb") as f:
            f.write(r.content)

        # Upload to Cloudinary
        upload = cloudinary.uploader.upload(
            local_path,
            resource_type="video" if ext == "mp4" else "image",
            folder="instagram_memes"
        )

        cloud_url = upload.get("secure_url") or upload.get("url")

        # -----------------------------
        # ✅ GENERATE THUMBNAIL FOR VIDEO ONLY
        # -----------------------------
        thumbnail_url = None
        public_id = upload.get("public_id")
        resource_type = upload.get("resource_type")
        # Fix for cases where public_id missing
        if isinstance(public_id, str) and ("http" in public_id or "https" in public_id):
            # These are URLs, not public IDs
            public_id = public_id.split("/upload/")[1].split(".")[0]

        if resource_type == "video":
            # Actual Cloudinary thumbnail
            
            thumbnail_url = cloudinary.CloudinaryImage(public_id).video_thumbnail(
                format="jpg",
                width=300,
                height=300,
                crop="fill"
            ).build_url()

        # For images → thumbnail stays None

        # Save meme document
        meme = Memes(
            title=title,
            file=cloud_url,
            thumbnail=thumbnail_url,
            type="video" if ext == "mp4" else "image",
            tags=tags_list,
            user_name="Meme Verse",
            language=language
        )
        meme.save()

        # Cleanup
        try:
            os.remove(local_path)
        except Exception:
            pass

        cache.delete(lock_key)
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
