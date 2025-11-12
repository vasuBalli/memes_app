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
logger = logging.getLogger('app_logger')

COOKIES_PATH = "/home/ubuntu/memes_app/instagram_cookies.txt"



def login_and_save_cookies(username, password):
    """
    Logs into Instagram using Instaloader (no GUI needed) and saves cookies.
    """
    logging.info("Logging into Instagram to save cookies")
    try:
        loader = instaloader.Instaloader()
        loader.login(username, password)
        # Save cookies in yt-dlp compatible format
        session_file = f"{username}.session"
        loader.save_session_to_file(session_file)
        # Convert to yt-dlp cookies.txt
        with open(session_file, "r") as src, open(COOKIES_PATH, "w") as dest:
            for line in src:
                dest.write(line)
        logger.info("Instagram login successful, cookies saved.")
    except Exception as e:
        logger.error(f"Instagram login failed: {str(e)}")   



def download_and_upload_instagram_video(url, language="english"):
    logging.info(f"Downloading Instagram video from URL: {url}")
    try:
        temp_dir = "memeverse"
        os.makedirs(temp_dir, exist_ok=True)

        print(f"Using cookies from: {COOKIES_PATH}")

        ydl_opts = {
            'outtmpl': os.path.join(temp_dir, '%(id)s.%(ext)s'),
            'cookies': COOKIES_PATH,
            'format': 'best',
            'merge_output_format': 'mp4',
            'quiet': False,
            'verbose': True,
            'noplaylist': True,
        }

        # ✅ Ensure yt_dlp has safe environment for file access
        os.environ["HOME"] = "/tmp"
        os.environ["XDG_CONFIG_HOME"] = "/tmp"
        logger.info("=== COOKIE DEBUG START ===")
        logger.info("COOKIES_PATH =", COOKIES_PATH)
        logger.info("Exists:", os.path.exists(COOKIES_PATH))
        logger.info("Readable:", os.access(COOKIES_PATH, os.R_OK))
        logger.info("First line preview:")
        try:
            with open(COOKIES_PATH) as f:
                logger.info(f.readline().strip())
        except Exception as fe:
            logger.info("Error opening cookies file:", fe)
        logger.info("=== COOKIE DEBUG END ===")

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            file_path = ydl.prepare_filename(info)
            if not file_path.endswith('.mp4'):
                file_path = f"{os.path.splitext(file_path)[0]}.mp4"

        title = info.get("title") or "Instagram Video"
        description = info.get("description") or ""
        uploader = info.get("uploader") or info.get("uploader_id") or "unknown"
        tags = ",".join([word for word in description.split() if word.startswith("#")])

        # upload_result = cloudinary.uploader.upload(
        #     file_path, resource_type="video", folder="instagram_memes"
        # )

        # os.remove(file_path)
        logger.info(f"Downloaded and processed ")
        return "none"

    except Exception as e:
        import traceback
        logger.error(f"Error downloading/uploading Instagram video: {str(e)}")
        logger.error(traceback.format_exc())




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
            data = json.loads(data)

          
            entry = data.get("entry", [])[0]
            messaging = entry.get("messaging", [])[0]
            message_obj = messaging.get("message", {})

            message_text = message_obj.get("text")
            sender_id = messaging.get("sender", {}).get("id")
            if message_text:
                url = message_text.replace("\"", "")
                download_and_upload_instagram_video(url)
                logger.info("uploaded successfully")
            # logger.info(f"Received Webhook Event: {data}")
            return JsonResponse({'status': 'received'}, status=200)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)

    else:
        return HttpResponse(status=405)


