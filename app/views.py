from django.http import HttpResponse, JsonResponse
import json
import random
from core.auth import token_required
import secrets
from datetime import timedelta
from django.utils import timezone
from django.contrib.auth.hashers import check_password
from django.core.mail import send_mail
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
from django.db import connection,transaction
from django.core.cache import cache
from mongoengine.errors import DoesNotExist, ValidationError
from .models import Memes, UserInteraction
from .serializers import meme_to_dict, memes_list_to_dict
import magic
import os
import json
from django.contrib.auth.hashers import make_password
from django.views.decorators.http import require_POST,require_GET
import logging
import requests
import cloudinary.uploader
import yt_dlp
from django.http import JsonResponse
from django.core.paginator import Paginator, EmptyPage
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


logger = logging.getLogger('app_logger')

COOKIES_PATH = "/home/ubuntu/memes_app/instagram_cookies.txt"
TEMP_DIR = os.path.join(settings.BASE_DIR, "memeverse")

def get_or_create_user_by_device(device_id: str) -> UserInteraction:
    logger.info(f"create user function triggered")
    user = UserInteraction.objects(device_id=device_id).first()
    if not user:
        user = UserInteraction(device_id=device_id)
        user.save()
    return user

# ---------- Pagination helper ----------
import math


# ---------- Endpoints ----------




def get_memes(request):
    logger.info("get_memes endpoint accessed")

    try:
        meme_type = request.GET.get("meme_type")
        cursor_id = request.GET.get("cursor")
        limit = min(int(request.GET.get("limit", 20)), 50)

        sql = """
            SELECT
                id,
                title,
                file_url,
                thumbnail_url,
                type,
                language,
                likes_count,
                views_count,
                bookmarks_count,
                shares_count,
                created_at
            FROM memes
            WHERE 1=1
        """

        params = []

        # Filter by type
        if meme_type:
            sql += " AND type = %s"
            params.append(meme_type)

        # Cursor pagination
        if cursor_id:
            sql += " AND id < %s"
            params.append(cursor_id)

        # Order and limit
        sql += """
            ORDER BY id DESC
            LIMIT %s
        """

        params.append(limit + 1)  # fetch one extra row

        with connection.cursor() as cursor:
            cursor.execute(sql, params)

            columns = [col[0] for col in cursor.description]
            rows = [
                dict(zip(columns, row))
                for row in cursor.fetchall()
            ]

        has_next = len(rows) > limit

        if has_next:
            rows = rows[:limit]

        # Ensure HTTPS URLs
        for item in rows:

            if item.get("file_url"):
                item["file_url"] = item["file_url"].replace(
                    "http://",
                    "https://"
                )

            if item.get("thumbnail_url"):
                item["thumbnail_url"] = item["thumbnail_url"].replace(
                    "http://",
                    "https://"
                )

            # Convert datetime to string
            if item.get("created_at"):
                item["created_at"] = (
                    item["created_at"].isoformat()
                )

        next_cursor = (
            rows[-1]["id"]
            if has_next and rows
            else None
        )

        return JsonResponse({
            "status": "success",
            "data": rows,
            "pagination": {
                "has_next": has_next,
                "next_cursor": next_cursor,
                "limit": limit
            }
        })

    except Exception as e:
        logger.exception("Error fetching memes")

        return JsonResponse({
            "status": "error",
            "message": str(e)
        }, status=500)

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
        logger.info(f"parsed body: {body}")
        meme_id = body.get("meme_id")
        device_id = body.get("device_id")
        logger.info(f"meme_id: {meme_id}, device_id: {device_id}")
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
            "likes_count": Memes.objects.get(id=meme_id).likes_count
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
        device_id = request.GET.get('device_id', "")
        if device_id:
            get_or_create_user_by_device(device_id)
        # body = json.loads(request.body.decode("utf-8"))
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

def download_and_upload_instagram_media(url, language="english"):
    logger.info(f"Downloading Instagram media from URL: {url}")

    try:
        temp_dir = TEMP_DIR
        os.makedirs(temp_dir, exist_ok=True)
        import uuid

        temp_filename = str(uuid.uuid4())

        ydl_opts = {
            'outtmpl': os.path.join(temp_dir, f'{temp_filename}.%(ext)s'),
            'cookiefile': COOKIES_PATH,
            'format': 'best',
            'merge_output_format': 'mp4',
            'quiet': True,
            'noplaylist': True,
            'no_cookies_update': True,
            'retries': 3,
        }

        logger.info(f"Cookie file: {COOKIES_PATH}")
        logger.info(f"Cookie exists: {os.path.exists(COOKIES_PATH)}")

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            file_path = ydl.prepare_filename(info)

        logger.info(f"Downloaded file: {file_path}")

        # Detect media type
        mime_type = magic.from_file(file_path, mime=True)
        logger.info(f"MIME type: {mime_type}")

        is_video = mime_type.startswith("video")
        media_type = "video" if is_video else "image"

        title = info.get("title") or "Instagram Media"
        description = info.get("description") or ""
        uploader = info.get("uploader") or info.get("uploader_id") or "unknown"

        tags = []
        if description:
            tags = [
                word.lstrip("#")
                for word in description.split()
                if word.startswith("#")
            ]

        # Upload to Cloudinary
        upload_result = cloudinary.uploader.upload(
            file_path,
            resource_type=media_type,
            folder="instagram_memes"
        )

        file_secure_url = (
            upload_result.get("secure_url")
            or upload_result.get("url")
        )

        thumbnail_url = None

        if is_video:
            public_id = upload_result["public_id"]

            thumbnail_url = (
                f"https://res.cloudinary.com/dvrmhmvkw/"
                f"video/upload/"
                f"c_fill,g_auto,h_720,w_720,q_auto:good/"
                f"{public_id}.jpg"
            )
        else:
            thumbnail_url = file_secure_url

        with transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO memes (
                        title,
                        file_url,
                        thumbnail_url,
                        type,
                        language,
                        likes_count,
                        views_count,
                        bookmarks_count,
                        shares_count,
                        comments_count,
                        created_at
                    )
                    VALUES (
                        %s, %s, %s, %s, %s,
                        0, 0, 0, 0, 0, NOW()
                    )
                    RETURNING id
                    """,
                    [
                        title[:5000],
                        file_secure_url,
                        thumbnail_url,
                        media_type,
                        language
                    ]
                )

                meme_id = cursor.fetchone()[0]

        logger.info(f"Meme created successfully. ID={meme_id}")

        if os.path.exists(file_path):
            os.remove(file_path)

        return {
            "status": "success",
            
        }

    except Exception:
        logger.exception("Error in download_and_upload_instagram_media")
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

            if x:
                logger.info("Uploaded successfully")
            else:
                logger.error("Upload failed")
            logger.info("uploaded successfully (if not None)")
            return JsonResponse({'status': 'received'}, status=200)
        except Exception as e:
            logger.exception("Error handling webhook POST")
            return JsonResponse({'error': str(e)}, status=400)
    else:
        return HttpResponse(status=405)
from django.db import connection
import json

def download_instagram_video(payload, language="english"):
    logger.info("download_instagram_video called")

    try:
        entry = payload.get("entry", [])[0]
        messaging = entry.get("messaging", [])[0]
        attachment = messaging.get("message", {}).get("attachments", [])[0]

        media_url = clean_webhook_url(
            attachment.get("payload", {}).get("url") or ""
        )

        logger.info(f"Instagram URL: {media_url}")

        meme = download_and_upload_instagram_media(
            media_url,
            language=language
        )

        if meme:
            logger.info(f"Meme created successfully")
            return meme

        logger.error("Failed to create meme")
        return None

    except Exception:
        logger.exception("Error in download_instagram_video")
        return None


# def download_instagram_video(payload, language="english"):
#     logger.info("download_instagram_video called")
#     try:
#         entry = payload.get("entry", [])[0]
#         messaging = entry.get("messaging", [])[0]
#         attachment = messaging.get("message", {}).get("attachments", [])[0]

#         media_url = clean_webhook_url(attachment.get("payload", {}).get("url") or "")
#         title = attachment.get("payload", {}).get("title", "Instagram Media")

#         tags_list = [w.lstrip("#") for w in title.split() if w.startswith("#")]

#         reel_id = (
#             attachment.get("payload", {}).get("reel_video_id")
#             or attachment.get("payload", {}).get("id")
#             or "unknown_id"
#         )

#         local_path = os.path.join(TEMP_DIR, f"{reel_id}")
#         os.makedirs(TEMP_DIR, exist_ok=True)

#         # Download the media
#         r = requests.get(media_url, timeout=30)
#         with open(local_path, "wb") as f:
#             f.write(r.content)

#         # Detect REAL file type
#         mime = magic.from_file(local_path, mime=True)
#         is_video = "video" in mime

#         # Upload to Cloudinary with correct resource type
#         upload = cloudinary.uploader.upload(
#             local_path,
#             resource_type="video" if is_video else "image",
#             folder="instagram_memes"
#         )

#         cloud_url = upload["secure_url"]

#         # Generate HD thumbnail ONLY for video
#         thumbnail_url = None
#         if is_video:
#             # cloud_name = settings.CLOUDINARY_STORAGE["CLOUD_NAME"]
#             public_id = upload["public_id"]
#             thumbnail_url = (
#                 f"https://res.cloudinary.com/dvrmhmvkw/video/upload/"
#                 f"c_fill,g_auto:face,h_720,w_720,q_auto:good/{public_id}.jpg"
#             )

#         # Create meme
#         meme = Memes(
#             title=title[:200],
#             file=cloud_url,
#             thumbnail=thumbnail_url,
#             type="video" if is_video else "image",
#             tags=tags_list,
#             user_name="Meme Verse",
#             language=language,
#         )
#         meme.save()

#         os.remove(local_path)
#         return meme

#     except Exception as e:
#         logger.exception("Error in download_instagram_video")
#         return None

@require_POST
def signup(request):

    try:
        body = json.loads(request.body)

        user_name = body.get("user_name", "").strip()
        email = body.get("email", "").strip().lower()
        password = body.get("password", "").strip()
        device_id = body.get("device_id", "")

        if not user_name:
            return JsonResponse({
                "status": "error",
                "message": "Username is required"
            }, status=400)

        if not email:
            return JsonResponse({
                "status": "error",
                "message": "Email is required"
            }, status=400)

        if not password:
            return JsonResponse({
                "status": "error",
                "message": "Password is required"
            }, status=400)

        with connection.cursor() as cursor:

            # Email already exists?
            cursor.execute("""
                SELECT id
                FROM users
                WHERE email=%s
            """, [email])

            if cursor.fetchone():

                return JsonResponse({
                    "status": "error",
                    "message": "Email already registered"
                }, status=400)

            # Delete previous OTP
            cursor.execute("""
                DELETE FROM signup_otps
                WHERE email=%s
            """, [email])

            otp = str(random.randint(100000, 999999))

            expires_at = timezone.now() + timedelta(minutes=10)

            hashed_password = make_password(password)

            cursor.execute("""
                INSERT INTO signup_otps
                (
                    user_name,
                    email,
                    password,
                    otp,
                    device_id,
                    expires_at
                )
                VALUES
                (
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s
                )
            """, [
                user_name,
                email,
                hashed_password,
                otp,
                device_id,
                expires_at
            ])

        # Send Email
        send_mail(
            subject="MEMEVERSE - Email Verification",
            message=f"""
Hi {user_name},

Your verification OTP is:

{otp}

This OTP is valid for 10 minutes.

Regards,
MEMEVERSE
""",
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[email],
            fail_silently=False
        )

        return JsonResponse({
            "status": "success",
            "message": "OTP sent successfully"
        })

    except Exception as e:

        return JsonResponse({
            "status": "error",
            "message": str(e)
        }, status=500)


@require_POST
def login(request):
    try:

        body = json.loads(request.body)

        email = body.get("email", "").strip().lower()
        password = body.get("password", "").strip()

        device_id = body.get("device_id")
        device_name = body.get("device_name")
        platform = body.get("platform")

        ip_address = request.META.get("REMOTE_ADDR")

        if not email or not password:
            return JsonResponse({
                "status": "error",
                "message": "Email and password are required."
            }, status=400)

        with connection.cursor() as cursor:

            cursor.execute("""
                SELECT
                    id,
                    user_name,
                    email,
                    password,
                    profile_pic
                FROM users
                WHERE email=%s
            """, [email])

            row = cursor.fetchone()

            if not row:
                return JsonResponse({
                    "status": "error",
                    "message": "Invalid email or password."
                }, status=401)

            user_id, user_name, user_email, hashed_password, profile_pic = row

            if not check_password(password, hashed_password):
                return JsonResponse({
                    "status": "error",
                    "message": "Invalid email or password."
                }, status=401)

            # Generate Secure Token
            token = secrets.token_urlsafe(40)

            expires_at = timezone.now() + timedelta(days=30)

            cursor.execute("""
                INSERT INTO user_tokens
                (
                    user_id,
                    token,
                    device_id,
                    device_name,
                    platform,
                    ip_address,
                    created_at,
                    last_used_at,
                    expires_at
                )
                VALUES
                (
                    %s,%s,%s,%s,%s,%s,
                    NOW(),
                    NOW(),
                    %s
                )
            """, [
                user_id,
                token,
                device_id,
                device_name,
                platform,
                ip_address,
                expires_at
            ])

            cursor.execute("""
                UPDATE users
                SET last_seen = NOW()
                WHERE id=%s
            """, [user_id])

        return JsonResponse({
            "status": "success",
            "message": "Login successful.",
            "token": token,
            "user": {
                "id": user_id,
                "user_name": user_name,
                "email": user_email,
                "profile_pic": profile_pic
            }
        })

    except Exception as e:

        return JsonResponse({
            "status": "error",
            "message": str(e)
        }, status=500)
@require_POST
def verify_signup(request):
    try:

        body = json.loads(request.body)

        email = body.get("email", "").strip().lower()
        otp = body.get("otp", "").strip()

        device_name = body.get("device_name")
        device_id = body.get("device_id")
        platform = body.get("platform")

        ip_address = request.META.get("REMOTE_ADDR")

        if not email or not otp:
            return JsonResponse({
                "status": "error",
                "message": "Email and OTP are required."
            }, status=400)

        with connection.cursor() as cursor:

            # Fetch OTP
            cursor.execute("""
            SELECT
                user_name,
                email,
                password,
                device_id
            FROM signup_otps
            WHERE email=%s
            AND otp=%s
            AND expires_at > NOW()
            """, [email, otp])

            row = cursor.fetchone()

            if not row:
                return JsonResponse({
                    "status": "error",
                    "message": "Invalid or expired OTP."
                }, status=400)

           
            user_name, email, password, signup_device_id = row
            # Create user
            cursor.execute("""
                INSERT INTO users
                (
                    user_name,
                    email,
                    password,
                    device_id,
                    created_at,
                    last_seen
                )
                VALUES
                (
                    %s,
                    %s,
                    %s,
                    %s,
                    NOW(),
                    NOW()
                )
                RETURNING id
            """, [
                user_name,
                email,
                password,
                signup_device_id
            ])

            user_id = cursor.fetchone()[0]

            # Generate Login Token
            token = secrets.token_urlsafe(40)

            expires_at = timezone.now() + timedelta(days=30)

            cursor.execute("""
                INSERT INTO user_tokens
                (
                    user_id,
                    token,
                    device_id,
                    device_name,
                    platform,
                    ip_address,
                    created_at,
                    last_used_at,
                    expires_at
                )
                VALUES
                (
                    %s,%s,%s,%s,%s,%s,
                    NOW(),
                    NOW(),
                    %s
                )
            """, [
                user_id,
                token,
                device_id,
                device_name,
                platform,
                ip_address,
                expires_at
            ])

            # Delete OTP
            cursor.execute("""
                DELETE FROM signup_otps
                WHERE email=%s
            """, [email])

        return JsonResponse({
            "status": "success",
            "message": "Account verified successfully.",
            "token": token,
            "user": {
                "id": user_id,
                "user_name": user_name,
                "email": email
            }
        })

    except Exception as e:

        return JsonResponse({
            "status": "error",
            "message": str(e)
        }, status=500)

@require_POST
def login(request):
    try:

        body = json.loads(request.body)

        email = body.get("email", "").strip().lower()
        password = body.get("password", "").strip()

        device_id = body.get("device_id")
        device_name = body.get("device_name")
        platform = body.get("platform")

        ip_address = request.META.get("REMOTE_ADDR")

        if not email or not password:
            return JsonResponse({
                "status": "error",
                "message": "Email and password are required."
            }, status=400)

        with connection.cursor() as cursor:

            cursor.execute("""
                SELECT
                    id,
                    user_name,
                    email,
                    password,
                    profile_pic
                FROM users
                WHERE email=%s
            """, [email])

            user = cursor.fetchone()

            if not user:
                return JsonResponse({
                    "status": "error",
                    "message": "Invalid email or password."
                }, status=401)

            user_id, user_name, user_email, hashed_password, profile_pic = user

            if not check_password(password, hashed_password):
                return JsonResponse({
                    "status": "error",
                    "message": "Invalid email or password."
                }, status=401)

            # Optional: remove old token for same device
            if device_id:
                cursor.execute("""
                    DELETE FROM user_tokens
                    WHERE user_id=%s
                    AND device_id=%s
                """, [user_id, device_id])

            token = secrets.token_urlsafe(40)

            expires_at = timezone.now() + timedelta(days=30)

            cursor.execute("""
                INSERT INTO user_tokens
                (
                    user_id,
                    token,
                    device_id,
                    device_name,
                    platform,
                    ip_address,
                    created_at,
                    last_used_at,
                    expires_at
                )
                VALUES
                (
                    %s,%s,%s,%s,%s,%s,
                    NOW(),
                    NOW(),
                    %s
                )
            """, [
                user_id,
                token,
                device_id,
                device_name,
                platform,
                ip_address,
                expires_at
            ])

            cursor.execute("""
                UPDATE users
                SET last_seen = NOW()
                WHERE id=%s
            """, [user_id])

        return JsonResponse({
            "status": "success",
            "message": "Login successful.",
            "token": token,
            "user": {
                "id": user_id,
                "user_name": user_name,
                "email": user_email,
                "profile_pic": profile_pic
            }
        })

    except Exception as e:
        return JsonResponse({
            "status": "error",
            "message": str(e)
        }, status=500)

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

@require_POST
def logout(request):
    try:

        auth_header = request.headers.get("Authorization")
        print(f"Authorization header: {auth_header}")
        if not auth_header:
            return JsonResponse({
                "status": "error",
                "message": "Authorization token is required."
            }, status=401)

       
        token = auth_header

        with connection.cursor() as cursor:

            cursor.execute("""
                SELECT id
                FROM user_tokens
                WHERE token=%s
                AND is_active=TRUE
            """, [token])

            token_data = cursor.fetchone()

            if not token_data:
                return JsonResponse({
                    "status": "error",
                    "message": "Invalid or expired token."
                }, status=401)

            cursor.execute("""
                UPDATE user_tokens
                SET
                    is_active = FALSE,
                    last_used_at = NOW()
                WHERE token=%s
            """, [token])

        return JsonResponse({
            "status": "success",
            "message": "Logged out successfully."
        })

    except Exception as e:

        return JsonResponse({
            "status": "error",
            "message": str(e)
        }, status=500)
    


@require_POST
def forgot_password(request):

    try:

        body = json.loads(request.body)

        email = body.get("email", "").strip().lower()

        if not email:
            return JsonResponse({
                "status": "error",
                "message": "Email is required."
            }, status=400)

        with connection.cursor() as cursor:

            cursor.execute("""
                SELECT id,user_name
                FROM users
                WHERE email=%s
            """, [email])

            user = cursor.fetchone()

            if not user:
                return JsonResponse({
                    "status": "error",
                    "message": "Email not found."
                }, status=404)

            user_id, user_name = user

            cursor.execute("""
                DELETE FROM password_reset_otps
                WHERE email=%s
            """, [email])

            otp = str(random.randint(100000, 999999))

            expires_at = timezone.now() + timedelta(minutes=10)

            cursor.execute("""
                INSERT INTO password_reset_otps
                (
                    email,
                    otp,
                    expires_at
                )
                VALUES
                (
                    %s,%s,%s
                )
            """, [
                email,
                otp,
                expires_at
            ])

        # send_mail(email, user_name, otp)
        send_mail(
            subject="MEMEVERSE - Email Verification",
            message=f"""
Hi {user_name},

Your password reset OTP is:

{otp}


Regards,
MEMEVERSE
""",
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[email],
            fail_silently=False
        )

        return JsonResponse({
            "status":"success",
            "message":"OTP sent successfully."
        })

    except Exception as e:

        return JsonResponse({
            "status":"error",
            "message":str(e)
        }, status=500)



@require_POST
def reset_password(request):

    try:

        body = json.loads(request.body)

        email = body.get("email", "").strip().lower()
        otp = body.get("otp", "").strip()
        password = body.get("password", "").strip()

        hashed_password = make_password(password)

        with connection.cursor() as cursor:

            cursor.execute("""
                SELECT id
                FROM password_reset_otps
                WHERE email=%s
                AND otp=%s
                AND expires_at > NOW()
            """, [email, otp])

            row = cursor.fetchone()

            if not row:
                return JsonResponse({
                    "status":"error",
                    "message":"Invalid or expired OTP."
                }, status=400)

            cursor.execute("""
                UPDATE users
                SET password=%s
                WHERE email=%s
            """, [
                hashed_password,
                email
            ])

            cursor.execute("""
                DELETE FROM password_reset_otps
                WHERE email=%s
            """, [email])

            # Logout from all devices after password reset
            cursor.execute("""
                UPDATE user_tokens
                SET is_active=FALSE
                WHERE user_id = (
                    SELECT id
                    FROM users
                    WHERE email=%s
                )
            """, [email])

        return JsonResponse({
            "status":"success",
            "message":"Password updated successfully."
        })

    except Exception as e:

        return JsonResponse({
            "status":"error",
            "message":str(e)
        }, status=500)

@require_POST
@token_required
def like_meme(request):
    try:

        body = json.loads(request.body)

        meme_id = body.get("meme_id")
        print(f"Received meme_id: {meme_id}"   )
        user_id = request.user["id"]
        print(f"User ID from token: {user_id}")
        if not meme_id:
            return JsonResponse({
                "status": "error",
                "message": "meme_id is required."
            }, status=400)

        with connection.cursor() as cursor:

            cursor.execute("""
                SELECT meme_id
                FROM meme_likes
                WHERE meme_id=%s
                AND user_id=%s
            """, [meme_id, user_id])

            existing = cursor.fetchone()

            # Unlike
            if existing:

                cursor.execute("""
                    DELETE FROM meme_likes
                    WHERE meme_id=%s
                    AND user_id=%s
                """, [meme_id, user_id])

                cursor.execute("""
                    UPDATE memes
                    SET likes_count = GREATEST(likes_count - 1, 0)
                    WHERE id=%s
                    RETURNING likes_count
                """, [meme_id])

                likes_count = cursor.fetchone()[0]

                return JsonResponse({
                    "status": "success",
                    "liked": False,
                    "likes_count": likes_count
                })

            # Like
            cursor.execute("""
                INSERT INTO meme_likes
                (
                    meme_id,
                    user_id
                )
                VALUES
                (
                    %s,
                    %s
                )
            """, [
                meme_id,
                user_id
            ])

            cursor.execute("""
                UPDATE memes
                SET likes_count = likes_count + 1
                WHERE id=%s
                RETURNING likes_count
            """, [meme_id])

            likes_count = cursor.fetchone()[0]

        return JsonResponse({
            "status": "success",
            "liked": True,
            "likes_count": likes_count
        })

    except Exception as e:

        return JsonResponse({
            "status": "error",
            "message": str(e)
        }, status=500)

@require_POST
@token_required
def add_comment(request):

    try:

        body = json.loads(request.body)

        meme_id = body.get("meme_id")
        comment_text = body.get("comment_text")
        parent_comment_id = body.get("parent_comment_id")

        user_id = request.user["id"]

        if not meme_id:
            return JsonResponse({
                "status":"error",
                "message":"meme_id required"
            }, status=400)

        if not comment_text:
            return JsonResponse({
                "status":"error",
                "message":"comment_text required"
            }, status=400)

        with connection.cursor() as cursor:

            cursor.execute("""
                INSERT INTO meme_comments
                (
                    meme_id,
                    user_id,
                    parent_comment_id,
                    comment_text
                )
                VALUES
                (
                    %s,
                    %s,
                    %s,
                    %s
                )
                RETURNING id
            """, [
                meme_id,
                user_id,
                parent_comment_id,
                comment_text
            ])

            comment_id = cursor.fetchone()[0]

            cursor.execute("""
                UPDATE memes
                SET comments_count = comments_count + 1
                WHERE id=%s
                RETURNING comments_count
            """, [meme_id])

            comments_count = cursor.fetchone()[0]

        return JsonResponse({

            "status":"success",

            "comment":{
                "id":comment_id,
                "comment_text":comment_text,
                "user_name":request.user["user_name"],
                "profile_pic":request.user["profile_pic"]
            },

            "comments_count":comments_count

        })

    except Exception as e:

        return JsonResponse({
            "status":"error",
            "message":str(e)
        }, status=500)

@require_POST
@token_required
def share_meme(request):

    try:

        body = json.loads(request.body)

        meme_id = body.get("meme_id")
        platform = body.get("platform", "unknown")

        user_id = request.user["id"]

        if not meme_id:
            return JsonResponse({
                "status": "error",
                "message": "meme_id is required."
            }, status=400)

        with connection.cursor() as cursor:

            cursor.execute("""
                INSERT INTO meme_shares
                (
                    meme_id,
                    user_id,
                    platform
                )
                VALUES
                (
                    %s,
                    %s,
                    %s
                )
            """, [
                meme_id,
                user_id,
                platform
            ])

            cursor.execute("""
                UPDATE memes
                SET shares_count = shares_count + 1
                WHERE id=%s
                RETURNING shares_count
            """, [meme_id])

            shares_count = cursor.fetchone()[0]

        return JsonResponse({
            "status": "success",
            "shares_count": shares_count
        })

    except Exception as e:

        return JsonResponse({
            "status": "error",
            "message": str(e)
        }, status=500)
@require_GET
@token_required
def get_bookmarked_memes(request):

    try:

        page = int(request.GET.get("page", 1))
        page_size = int(request.GET.get("page_size", 20))

        user_id = request.user["id"]

        offset = (page - 1) * page_size

        with connection.cursor() as cursor:

            #########################################################
            # Total Count
            #########################################################

            cursor.execute("""
                SELECT COUNT(*)
                FROM meme_bookmarks
                WHERE user_id=%s
            """, [user_id])

            total = cursor.fetchone()[0]

            #########################################################
            # Bookmarks
            #########################################################

            cursor.execute("""
                SELECT

                    m.id,
                    m.title,
                    m.file_url,
                    m.thumbnail_url,
                    m.type,
                    m.language,
                    m.duration,

                    m.likes_count,
                    m.views_count,
                    m.bookmarks_count,
                    m.shares_count,
                    m.comments_count,

                    m.created_at,

                    CASE
                        WHEN ml.id IS NULL THEN FALSE
                        ELSE TRUE
                    END AS liked

                FROM meme_bookmarks mb

                JOIN memes m
                    ON m.id=mb.meme_id

                LEFT JOIN meme_likes ml
                    ON ml.meme_id=m.id
                    AND ml.user_id=%s

                WHERE mb.user_id=%s

                ORDER BY mb.created_at DESC

                LIMIT %s
                OFFSET %s

            """, [

                user_id,
                user_id,
                page_size,
                offset

            ])

            rows = cursor.fetchall()

            memes = []

            for row in rows:

                memes.append({

                    "id": row[0],

                    "title": row[1],

                    "file_url": row[2],

                    "thumbnail_url": row[3],

                    "type": row[4],

                    "language": row[5],

                    "duration": row[6],

                    "likes_count": row[7],

                    "views_count": row[8],

                    "bookmarks_count": row[9],

                    "shares_count": row[10],

                    "comments_count": row[11],

                    "created_at": row[12],

                    "liked": row[13],

                    "bookmarked": True

                })

        return JsonResponse({

            "status": "success",

            "page": page,

            "page_size": page_size,

            "total": total,

            "data": memes

        })

    except Exception as e:

        return JsonResponse({

            "status": "error",

            "message": str(e)

        }, status=500)
@require_GET
@token_required
def get_liked_memes(request):

    try:

        page = int(request.GET.get("page", 1))
        page_size = int(request.GET.get("page_size", 20))

        user_id = request.user["id"]

        offset = (page - 1) * page_size

        with connection.cursor() as cursor:

            ########################################################
            # Total Likes
            ########################################################

            cursor.execute("""
                SELECT COUNT(*)
                FROM meme_likes
                WHERE user_id=%s
            """, [user_id])

            total = cursor.fetchone()[0]

            ########################################################
            # Fetch Memes
            ########################################################

            cursor.execute("""

                SELECT

                    m.id,
                    m.title,
                    m.file_url,
                    m.thumbnail_url,
                    m.type,
                    m.language,
                    m.duration,

                    m.likes_count,
                    m.views_count,
                    m.bookmarks_count,
                    m.shares_count,
                    m.comments_count,

                    m.created_at,

                    CASE
                        WHEN mb.id IS NULL THEN FALSE
                        ELSE TRUE
                    END AS bookmarked

                FROM meme_likes ml

                JOIN memes m
                    ON m.id = ml.meme_id

                LEFT JOIN meme_bookmarks mb
                    ON mb.meme_id=m.id
                    AND mb.user_id=%s

                WHERE ml.user_id=%s

                ORDER BY ml.created_at DESC

                LIMIT %s
                OFFSET %s

            """, [

                user_id,
                user_id,
                page_size,
                offset

            ])

            rows = cursor.fetchall()

            memes = []

            for row in rows:

                memes.append({

                    "id": row[0],

                    "title": row[1],

                    "file_url": row[2],

                    "thumbnail_url": row[3],

                    "type": row[4],

                    "language": row[5],

                    "duration": row[6],

                    "likes_count": row[7],

                    "views_count": row[8],

                    "bookmarks_count": row[9],

                    "shares_count": row[10],

                    "comments_count": row[11],

                    "created_at": row[12],

                    "liked": True,

                    "bookmarked": row[13]

                })

        return JsonResponse({

            "status": "success",

            "page": page,

            "page_size": page_size,

            "total": total,

            "data": memes

        })

    except Exception as e:

        return JsonResponse({

            "status": "error",

            "message": str(e)

        }, status=500)
@require_GET
@token_required
def get_watch_history(request):

    try:

        page = int(request.GET.get("page", 1))
        page_size = int(request.GET.get("page_size", 20))

        user_id = request.user["id"]

        offset = (page - 1) * page_size

        with connection.cursor() as cursor:

            ########################################################
            # Total History
            ########################################################

            cursor.execute("""
                SELECT COUNT(*)
                FROM meme_views
                WHERE user_id=%s
            """, [user_id])

            total = cursor.fetchone()[0]

            ########################################################
            # Fetch History
            ########################################################

            cursor.execute("""

                SELECT

                    m.id,
                    m.title,
                    m.file_url,
                    m.thumbnail_url,
                    m.type,
                    m.language,
                    m.duration,

                    m.likes_count,
                    m.views_count,
                    m.bookmarks_count,
                    m.shares_count,
                    m.comments_count,

                    mv.watched_seconds,
                    mv.is_completed,
                    mv.created_at,

                    CASE
                        WHEN ml.id IS NULL THEN FALSE
                        ELSE TRUE
                    END AS liked,

                    CASE
                        WHEN mb.id IS NULL THEN FALSE
                        ELSE TRUE
                    END AS bookmarked

                FROM meme_views mv

                JOIN memes m
                    ON m.id = mv.meme_id

                LEFT JOIN meme_likes ml
                    ON ml.meme_id = m.id
                    AND ml.user_id=%s

                LEFT JOIN meme_bookmarks mb
                    ON mb.meme_id = m.id
                    AND mb.user_id=%s

                WHERE mv.user_id=%s

                ORDER BY mv.created_at DESC

                LIMIT %s
                OFFSET %s

            """, [

                user_id,
                user_id,
                user_id,
                page_size,
                offset

            ])

            rows = cursor.fetchall()

            history = []

            for row in rows:

                history.append({

                    "id": row[0],

                    "title": row[1],

                    "file_url": row[2],

                    "thumbnail_url": row[3],

                    "type": row[4],

                    "language": row[5],

                    "duration": row[6],

                    "likes_count": row[7],

                    "views_count": row[8],

                    "bookmarks_count": row[9],

                    "shares_count": row[10],

                    "comments_count": row[11],

                    "watched_seconds": row[12],

                    "is_completed": row[13],

                    "last_watched": row[14],

                    "liked": row[15],

                    "bookmarked": row[16]

                })

        return JsonResponse({

            "status": "success",

            "page": page,

            "page_size": page_size,

            "total": total,

            "data": history

        })

    except Exception as e:

        return JsonResponse({

            "status": "error",

            "message": str(e)

        }, status=500)
@require_GET
@token_required
def get_profile(request):

    try:

        user_id = request.user["id"]

        with connection.cursor() as cursor:

            ####################################################
            # User Details
            ####################################################

            cursor.execute("""
                SELECT
                    id,
                    user_name,
                    email,
                    profile_pic,
                    is_google_user,
                    created_at,
                    last_seen
                FROM users
                WHERE id=%s
            """, [user_id])

            row = cursor.fetchone()

            if not row:
                return JsonResponse({
                    "status": "error",
                    "message": "User not found."
                }, status=404)

            ####################################################
            # Total Likes
            ####################################################

            cursor.execute("""
                SELECT COUNT(*)
                FROM meme_likes
                WHERE user_id=%s
            """, [user_id])

            liked_memes = cursor.fetchone()[0]

            ####################################################
            # Total Bookmarks
            ####################################################

            cursor.execute("""
                SELECT COUNT(*)
                FROM meme_bookmarks
                WHERE user_id=%s
            """, [user_id])

            bookmarked_memes = cursor.fetchone()[0]

            ####################################################
            # Watch History
            ####################################################

            cursor.execute("""
                SELECT COUNT(*)
                FROM meme_views
                WHERE user_id=%s
            """, [user_id])

            watched_memes = cursor.fetchone()[0]

            ####################################################
            # Comments
            ####################################################

            cursor.execute("""
                SELECT COUNT(*)
                FROM meme_comments
                WHERE user_id=%s
            """, [user_id])

            comments = cursor.fetchone()[0]

            ####################################################
            # Uploaded Memes
            ####################################################

            cursor.execute("""
                SELECT COUNT(*)
                FROM memes
                WHERE uploaded_by=%s
            """, [user_id])

            uploaded_memes = cursor.fetchone()[0]

        return JsonResponse({

            "status": "success",

            "user": {

                "id": row[0],

                "user_name": row[1],

                "email": row[2],

                "profile_pic": row[3],

                "is_google_user": row[4],

                "created_at": row[5],

                "last_seen": row[6]

            },

            "stats": {

                "uploaded_memes": uploaded_memes,

                "liked_memes": liked_memes,

                "bookmarked_memes": bookmarked_memes,

                "watched_memes": watched_memes,

                "comments": comments

            }

        })

    except Exception as e:

        return JsonResponse({

            "status": "error",

            "message": str(e)

        }, status=500)
@require_POST
@token_required
def update_profile(request):

    try:

        body = json.loads(request.body)

        user_name = body.get("user_name")
        profile_pic = body.get("profile_pic")

        user_id = request.user["id"]

        with connection.cursor() as cursor:

            #######################################################
            # Fetch Existing Data
            #######################################################

            cursor.execute("""
                SELECT
                    user_name,
                    profile_pic
                FROM users
                WHERE id=%s
            """, [user_id])

            row = cursor.fetchone()

            if not row:
                return JsonResponse({
                    "status": "error",
                    "message": "User not found."
                }, status=404)

            current_name = row[0]
            current_profile = row[1]

            #######################################################
            # Preserve Existing Values
            #######################################################

            if user_name is None:
                user_name = current_name

            if profile_pic is None:
                profile_pic = current_profile

            #######################################################
            # Update
            #######################################################

            cursor.execute("""
                UPDATE users
                SET
                    user_name=%s,
                    profile_pic=%s,
                    last_seen=NOW()
                WHERE id=%s
            """, [
                user_name,
                profile_pic,
                user_id
            ])

        return JsonResponse({

            "status": "success",

            "message": "Profile updated successfully.",

            "user": {

                "id": user_id,

                "user_name": user_name,

                "profile_pic": profile_pic

            }

        })

    except Exception as e:

        return JsonResponse({

            "status": "error",

            "message": str(e)

        }, status=500)
from collections import defaultdict


@require_GET
@token_required
def get_comments(request):

    try:

        meme_id = request.GET.get("meme_id")

        page = int(request.GET.get("page", 1))
        page_size = int(request.GET.get("page_size", 20))

        user_id = request.user["id"]

        if not meme_id:
            return JsonResponse({
                "status": "error",
                "message": "meme_id is required."
            }, status=400)

        offset = (page - 1) * page_size

        with connection.cursor() as cursor:

            ###################################################
            # Total Count
            ###################################################

            cursor.execute("""
                SELECT COUNT(*)
                FROM meme_comments
                WHERE meme_id=%s
                AND parent_comment_id IS NULL
            """, [meme_id])

            total_comments = cursor.fetchone()[0]

            ###################################################
            # Parent Comments
            ###################################################

            cursor.execute("""
                SELECT
                    c.id,
                    c.comment_text,
                    c.likes_count,
                    c.created_at,
                    u.id,
                    u.user_name,
                    u.profile_pic
                FROM meme_comments c
                JOIN users u
                    ON u.id=c.user_id
                WHERE
                    c.meme_id=%s
                    AND c.parent_comment_id IS NULL
                ORDER BY c.created_at DESC
                LIMIT %s
                OFFSET %s
            """, [
                meme_id,
                page_size,
                offset
            ])

            parent_comments = cursor.fetchall()

            parent_ids = [row[0] for row in parent_comments]

            replies_map = defaultdict(list)

            ###################################################
            # Replies (Single Query)
            ###################################################

            if parent_ids:

                cursor.execute("""
                    SELECT
                        c.id,
                        c.parent_comment_id,
                        c.comment_text,
                        c.likes_count,
                        c.created_at,

                        u.id,
                        u.user_name,
                        u.profile_pic

                    FROM meme_comments c

                    JOIN users u
                        ON u.id=c.user_id

                    WHERE c.parent_comment_id = ANY(%s)

                    ORDER BY c.created_at ASC
                """, [parent_ids])

                reply_rows = cursor.fetchall()

                for r in reply_rows:

                    replies_map[r[1]].append({

                        "id": r[0],

                        "comment_text": r[2],

                        "likes_count": r[3],

                        "created_at": r[4],

                        "user": {

                            "id": r[5],

                            "user_name": r[6],

                            "profile_pic": r[7]

                        },

                        "is_owner": r[5] == user_id

                    })

            ###################################################
            # Response
            ###################################################

            comments = []

            for row in parent_comments:

                replies = replies_map.get(row[0], [])

                comments.append({

                    "id": row[0],

                    "comment_text": row[1],

                    "likes_count": row[2],

                    "created_at": row[3],

                    "user": {

                        "id": row[4],

                        "user_name": row[5],

                        "profile_pic": row[6]

                    },

                    "is_owner": row[4] == user_id,

                    "reply_count": len(replies),

                    "replies": replies

                })

        return JsonResponse({

            "status": "success",

            "page": page,

            "page_size": page_size,

            "total_comments": total_comments,

            "comments": comments

        })

    except Exception as e:

        return JsonResponse({

            "status": "error",

            "message": str(e)

        }, status=500)

@require_POST
@token_required
def delete_comment(request):

    try:

        body = json.loads(request.body)

        comment_id = body.get("comment_id")

        user_id = request.user["id"]

        if not comment_id:
            return JsonResponse({
                "status": "error",
                "message": "comment_id is required."
            }, status=400)

        with connection.cursor() as cursor:

            ########################################################
            # Verify Owner
            ########################################################

            cursor.execute("""
                SELECT
                    meme_id,
                    user_id
                FROM meme_comments
                WHERE id=%s
            """, [comment_id])

            row = cursor.fetchone()

            if not row:
                return JsonResponse({
                    "status": "error",
                    "message": "Comment not found."
                }, status=404)

            meme_id = row[0]
            owner_id = row[1]

            if owner_id != user_id:

                return JsonResponse({
                    "status": "error",
                    "message": "You are not authorized to delete this comment."
                }, status=403)

            ########################################################
            # Count comments that will be deleted
            ########################################################

            cursor.execute("""
                SELECT COUNT(*)
                FROM meme_comments
                WHERE id=%s
                   OR parent_comment_id=%s
            """, [comment_id, comment_id])

            deleted_count = cursor.fetchone()[0]

            ########################################################
            # Delete Comment
            ########################################################

            cursor.execute("""
                DELETE FROM meme_comments
                WHERE id=%s
            """, [comment_id])

            ########################################################
            # Update Meme Count
            ########################################################

            cursor.execute("""
                UPDATE memes
                SET comments_count = GREATEST(comments_count - %s, 0)
                WHERE id=%s
                RETURNING comments_count
            """, [
                deleted_count,
                meme_id
            ])

            comments_count = cursor.fetchone()[0]

        return JsonResponse({

            "status": "success",

            "message": "Comment deleted successfully.",

            "comments_count": comments_count

        })

    except Exception as e:

        return JsonResponse({

            "status": "error",

            "message": str(e)

        }, status=500)
@require_POST
@token_required
def bookmark_meme(request):
    try:

        body = json.loads(request.body)

        meme_id = body.get("meme_id")
        user_id = request.user["id"]

        if not meme_id:
            return JsonResponse({
                "status": "error",
                "message": "meme_id is required."
            }, status=400)

        with connection.cursor() as cursor:

            # Check bookmark exists
            cursor.execute("""
                SELECT id
                FROM meme_bookmarks
                WHERE meme_id=%s
                AND user_id=%s
            """, [meme_id, user_id])

            bookmark = cursor.fetchone()

            # Remove Bookmark
            if bookmark:

                cursor.execute("""
                    DELETE FROM meme_bookmarks
                    WHERE meme_id=%s
                    AND user_id=%s
                """, [meme_id, user_id])

                cursor.execute("""
                    UPDATE memes
                    SET bookmarks_count = GREATEST(bookmarks_count - 1, 0)
                    WHERE id=%s
                    RETURNING bookmarks_count
                """, [meme_id])

                bookmarks_count = cursor.fetchone()[0]

                return JsonResponse({
                    "status": "success",
                    "bookmarked": False,
                    "bookmarks_count": bookmarks_count
                })

            # Add Bookmark
            cursor.execute("""
                INSERT INTO meme_bookmarks
                (
                    meme_id,
                    user_id
                )
                VALUES
                (
                    %s,
                    %s
                )
            """, [meme_id, user_id])

            cursor.execute("""
                UPDATE memes
                SET bookmarks_count = bookmarks_count + 1
                WHERE id=%s
                RETURNING bookmarks_count
            """, [meme_id])

            bookmarks_count = cursor.fetchone()[0]

        return JsonResponse({
            "status": "success",
            "bookmarked": True,
            "bookmarks_count": bookmarks_count
        })

    except Exception as e:

        return JsonResponse({
            "status": "error",
            "message": str(e)
        }, status=500)
@require_POST
@token_required
def add_view(request):
    try:

        body = json.loads(request.body)

        meme_id = body.get("meme_id")
        watched_seconds = body.get("watched_seconds", 0)
        is_completed = body.get("is_completed", False)

        user_id = request.user["id"]

        if not meme_id:
            return JsonResponse({
                "status": "error",
                "message": "meme_id is required"
            }, status=400)

        with connection.cursor() as cursor:

            cursor.execute("""
                SELECT id
                FROM meme_views
                WHERE meme_id=%s
                AND user_id=%s
            """, [meme_id, user_id])

            existing = cursor.fetchone()

            if existing:

                cursor.execute("""
                    UPDATE meme_views
                    SET
                        watched_seconds=%s,
                        is_completed=%s,
                        created_at=NOW()
                    WHERE id=%s
                """, [
                    watched_seconds,
                    is_completed,
                    existing[0]
                ])

            else:

                cursor.execute("""
                    INSERT INTO meme_views
                    (
                        meme_id,
                        user_id,
                        watched_seconds,
                        is_completed
                    )
                    VALUES
                    (
                        %s,
                        %s,
                        %s,
                        %s
                    )
                """, [
                    meme_id,
                    user_id,
                    watched_seconds,
                    is_completed
                ])

                cursor.execute("""
                    UPDATE memes
                    SET views_count = views_count + 1
                    WHERE id=%s
                    RETURNING views_count
                """, [meme_id])

                views_count = cursor.fetchone()[0]

                return JsonResponse({
                    "status": "success",
                    "views_count": views_count
                })

            cursor.execute("""
                SELECT views_count
                FROM memes
                WHERE id=%s
            """, [meme_id])

            views_count = cursor.fetchone()[0]

        return JsonResponse({
            "status": "success",
            "views_count": views_count
        })

    except Exception as e:

        return JsonResponse({
            "status": "error",
            "message": str(e)
        }, status=500)