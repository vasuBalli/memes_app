from .models import Memes
from django.http import HttpResponse, JsonResponse
from .serializers import MemesSerializer
from django.views.decorators.csrf import csrf_exempt
import requests
import logging
import instaloader
import yt_dlp
import cloudinary.uploader
from django.conf import settings
from django.core.files import File
import os
import json
from django.conf import settings
from instagrapi import Client
from django.core.cache import cache
logger = logging.getLogger('app_logger')

COOKIES_PATH = "/home/ubuntu/memes_app/instagram_cookies.txt"


def get_memes(request):
    logger.info("get_memes endpoint accessed")
    try:
        logger.info("Fetching memes from database")
        type = request.GET.get('meme_type', None)
        if type is None:
            queryset = Memes.objects.all().order_by('-created_at') # newest first
            
        else:
            queryset = Memes.objects.all().order_by('-created_at').filter(type = type) # newest first
        serializer = MemesSerializer(queryset, many=True)
        data =serializer.data
        logger.info(f"Fetched {len(data)} memes")
        for i in data:
            print(i["file_url"])
            try:
                i["file_url"] = i["file_url"].replace("http://", "https://")
            #s
            except:
                pass    
        return JsonResponse({"status": "success", "data": data})
    except Exception as e:
        logger.error(f"Error fetching memes: {str(e)}")
        return JsonResponse({"status": "error", "message": str(e)})


def download_and_upload_instagram_video(url, language="english"):
    logger.info(f"Downloading Instagram video from URL: {url}")
    import sys
    

    logger.info("DJANGO PYTHON: %s", sys.executable)
    logger.info("DJANGO yt-dlp path: %s", yt_dlp.__file__)
    logger.info("DJANGO yt-dlp version: %s", yt_dlp.__version__)


    try:
        temp_dir = "memeverse"
        os.makedirs(temp_dir, exist_ok=True)
        logger.info("cookies path : "+COOKIES_PATH)
        ydl_opts = {
            'outtmpl': os.path.join(temp_dir, '%(id)s.%(ext)s'),
            'cookies': COOKIES_PATH,
            'format': 'best',
            'merge_output_format': 'mp4',
            'quiet': False,
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

        # 🔹 Step 1: Download + Extract metadata
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)

            file_path = ydl.prepare_filename(info)
            if not file_path.endswith('.mp4'):
                file_path = f"{os.path.splitext(file_path)[0]}.mp4"

        # 🔹 Step 2: Extract details from metadata
        title = info.get("title") or "Instagram Video"
        description = info.get("description") or ""
        uploader = info.get("uploader") or info.get("uploader_id") or "unknown"

        # Extract hashtags as tags
        tags = []
        if description:
            tags = [word for word in description.split() if word.startswith("#")]
        tags_str = ",".join(tags) if tags else ""

        # 🔹 Step 3: Upload to Cloudinary
        upload_result = cloudinary.uploader.upload(
            file_path,
            resource_type="video",
            folder="instagram_memes"
        )

        thumbnail_url = upload_result.get("thumbnail_url") or upload_result.get("url")

        # 🔹 Step 4: Save to Django model
        meme = Memes.objects.create(
            title=title,
            file=upload_result["secure_url"],
            thumbnail=thumbnail_url,
            type="video",
            tags=tags_str,
            user_name=uploader,
            language=language
        )

        # 🔹 Step 5: Cleanup local file
        os.remove(file_path)
        return meme
    except Exception as e:
        import traceback

        logger.error(f"Error downloading/uploading Instagram video: {str(e)}")
        logger.info("Cookie file exists:"+ os.path.exists("/home/ubuntu/memes_app/instagram_cookies.txt"))
        logger.info("Cookie file size:"+ os.path.getsize("/home/ubuntu/memes_app/instagram_cookies.txt"))
        logger.error(traceback.format_exc())




SESSION_FILE = os.path.join(settings.BASE_DIR, "insta_session.json")
TEMP_DIR = os.path.join(settings.BASE_DIR, "memeverse")
def download_instagram_video(url,language="english"):
    logger.info(f"Downloading Instagram media from URL: {url}")
    cl = Client()

    # Load saved session (works faster)
    if os.path.exists(SESSION_FILE):
        cl.load_settings(SESSION_FILE)

    cl.login("shailajakathi85", "Vasu@1918")
    cl.dump_settings(SESSION_FILE)

    # Convert URL → PK
    media_pk = cl.media_pk_from_url(url)

    # 🔥 Strong duplicate prevention (2 minutes)
    lock_key = f"media_download_lock_{media_pk}"
    if cache.get(lock_key):
        return None  # skip duplicate call

    cache.set(lock_key, True, 120)

    # ====================================================================================
    # STEP 1: Fetch full metadata
    # ====================================================================================
    media = cl.media_info(media_pk)

    # Title / Caption
    title = media.caption_text or "Instagram Post"
    description = media.caption_text or ""
    uploader = media.user.username
    logger.info(f"title: {title}, uploader: {uploader}")
    # Hashtags
    tags = [w for w in description.split() if w.startswith("#")]
    tags_str = ",".join(tags)

    # ====================================================================================
    # STEP 2: Detect media type (video / image)
    # ====================================================================================
    is_video = hasattr(media, "video_url") and media.video_url is not None

    if is_video:
        file_url = media.video_url
        ext = "mp4"
        file_type = "video"
    else:
        # Instagram images are under media.thumbnail_url
        file_url = media.thumbnail_url or media.resources[0].thumbnail_url
        ext = "jpg"
        file_type = "image"
    logger.info(f"Detected media type: {file_type}")
    # ====================================================================================
    # STEP 3: Download file locally
    # ====================================================================================
    local_path = os.path.join(TEMP_DIR, f"{media_pk}.{ext}")

    with open(local_path, "wb") as f:
        f.write(requests.get(file_url).content)

    # ====================================================================================
    # STEP 4: Upload to Cloudinary
    # ====================================================================================
    upload = cloudinary.uploader.upload(
        local_path,
        resource_type="video" if is_video else "image",
        folder="instagram_memes"
    )
    logger.info(f"Uploaded to Cloudinary: {upload.get('secure_url')}")

    cloud_url = upload["secure_url"]
    thumbnail_url = upload.get("thumbnail_url") or cloud_url

    # ====================================================================================
    # STEP 5: Save in DB
    # ====================================================================================
    meme = Memes.objects.create(
        title=title,
        file=cloud_url,
        thumbnail=thumbnail_url,
        type=file_type,      # ⭐ image or video automatically
        tags=tags_str,
        user_name=uploader,
        language=language.lower()
    )

    # Cleanup
    os.remove(local_path)
    cache.delete(lock_key)

    return meme
    
def privacy_policy(request):
    logger.info("Privacy policy page accessed")
   
    # fetch_instagram_video()
    print("sucessfully uploaded")
    # logger.info("Privacy policy page accessed")
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





@csrf_exempt
def webhook(request):
    logger.info("Webhook endpoint accessed")
    if request.method == 'GET':
        # Webhook verification (Meta Challenge)
        try:
            mode = request.GET.get('hub.mode')
            token = request.GET.get('hub.verify_token')
            challenge = request.GET.get('hub.challenge')
            return HttpResponse(challenge)
        except Exception as e:
            return HttpResponse('Verification failed', status=403)
        
    elif request.method == 'POST':
        logger.info("Webhook POST request received")
        # Handle webhook events (Instagram sends updates here)
        try:
            if os.path.exists(COOKIES_PATH):
                logger.info("Using existing Instagram cookies")
            else:
                logger.info("Instagram cookies not found, logging in...")
                login_and_save_cookies("shailajakathi85", "Vasu@1918")
            data = request.body.decode('utf-8')
            logger.info(f"Webhook data: {data}")
            data = json.loads(data)

          
            entry = data.get("entry", [])[0]
            messaging = entry.get("messaging", [])[0]
            message_obj = messaging.get("message", {})

            message_text = message_obj.get("text")
            sender_id = messaging.get("sender", {}).get("id")
            if message_text:
                url = message_text.replace("\"", "")
                logger.info("download started ")
                # download_and_upload_instagram_video(url)
                if "instagram.com" in url:
                    x = download_instagram_video(url)
                    logger.info(f"Video downloaded to: {x}")
                    logger.info("uploaded successfully")
                else:
                    logger.info("Not a valid Instagram URL")
            # logger.info(f"Received Webhook Event: {data}")
            return JsonResponse({'status': 'received'}, status=200)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)

    else:
        return HttpResponse(status=405)


