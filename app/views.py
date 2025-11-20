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


def clean_webhook_url(url: str) -> str:
    # Instagram webhook URL contains escaped slashes
    url = url.replace("\\/", "/")

    # Some webhook implementations escape backslashes too
    url = url.replace("\\", "")

    return url


SESSION_FILE = os.path.join(settings.BASE_DIR, "insta_session.json")
TEMP_DIR = os.path.join(settings.BASE_DIR, "memeverse")
def download_instagram_video(payload,language="english"):
    logger.info(f"Downloading Instagram video from webhook payload")
    try:
        attachment = payload["entry"][0]["messaging"][0]["message"]["attachments"][0]
        media_type = attachment["type"]                       # ig_reel / image / video
        reel_id = attachment["payload"].get("reel_video_id")
        title = attachment["payload"].get("title", "Instagram Media")
        media_url = clean_webhook_url(attachment["payload"]["url"])   
        

        # 🔥 Extract tags from title
        tags_list = []
        if title:
            tags_list = [w.strip() for w in title.split() if w.startswith("#")]
        tags = ",".join(tags_list)
        logger.info(f"Extracted tags: {tags}")

        # Prevent duplicates
        lock_key = f"webhook_{reel_id}"
        if cache.get(lock_key):
            return None
        
        cache.set(lock_key, True, 120)

        # File type
        ext = "mp4" if media_type == "ig_reel" else "jpg"
        local_path = os.path.join(TEMP_DIR, f"{reel_id}.{ext}")

        # Download
        with open(local_path, "wb") as f:
            f.write(requests.get(media_url).content)
        logger.info(f"Downloaded Instagram media to {local_path}")

        # Upload to Cloudinary
        upload = cloudinary.uploader.upload(
            local_path,
            resource_type="video" if ext == "mp4" else "image",
            folder="instagram_memes"
        )
        logger.info(f"Uploaded to Cloudinary: {upload['secure_url']}")  

        cloud_url = upload["secure_url"]
        thumbnail = upload.get("thumbnail_url") or cloud_url

        meme = Memes.objects.create(
            title=title,
            file=cloud_url,
            thumbnail=thumbnail,
            type="video" if ext == "mp4" else "image",
            tags=tags,                      # ⭐ TAGS ADDED HERE
            user_name="Meme Verse",
            language=language
        )
        logger.info(f"Created Meme object with ID: {meme.id}")

        os.remove(local_path)
        cache.delete(lock_key)

        return meme
    except Exception as e:
        import traceback
        logger.error(f"Error in download_instagram_video: {str(e)}")
        logger.error(traceback.format_exc())
        return None
    
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
            # if os.path.exists(COOKIES_PATH):
            #     logger.info("Using existing Instagram cookies")
            # else:
            #     logger.info("Instagram cookies not found, logging in...")
            #     login_and_save_cookies("shailajakathi85", "Vasu@1918")
            data = request.body.decode('utf-8')
            logger.info(f"Webhook data: {data}")
            data = json.loads(data)

          
            # entry = data.get("entry", [])[0]
            # messaging = entry.get("messaging", [])[0]
            # message_obj = messaging.get("message", {})

            # message_text = message_obj.get("text")
            # sender_id = messaging.get("sender", {}).get("id")
            # if message_text:
            #     url = message_text.replace("\"", "")
            #     logger.info("download started ")
                # download_and_upload_instagram_video(url)
                # if "instagram.com" in url:
            x = download_instagram_video(data, language="english")
            # logger.info(f"Video downloaded to: {x}")
            logger.info("uploaded successfully")
                # else:
                #     logger.info("Not a valid Instagram URL")
            # logger.info(f"Received Webhook Event: {data}")
            return JsonResponse({'status': 'received'}, status=200)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)

    else:
        return HttpResponse(status=405)


