from functools import wraps

from django.db import connection
from django.http import JsonResponse


def token_required(view_func):

    @wraps(view_func)
    def wrapper(request, *args, **kwargs):

        try:

            auth_header = request.headers.get("Authorization")

            if not auth_header:
                return JsonResponse({
                    "status": "error",
                    "message": "Authorization header is required."
                }, status=401)

            
            token = auth_header.replace("Token ", "").strip()

            with connection.cursor() as cursor:

                cursor.execute("""
                    SELECT
                        u.id,
                        u.user_name,
                        u.email,
                        u.profile_pic,
                        ut.device_id,
                        ut.device_name,
                        ut.platform
                    FROM user_tokens ut
                    JOIN users u
                        ON u.id = ut.user_id
                    WHERE
                        ut.token = %s
                       -- AND ut.is_active = TRUE
                       -- AND ut.expires_at > NOW()
                    LIMIT 1
                """, [token])

                row = cursor.fetchone()

                if not row:
                    return JsonResponse({
                        "status": "error",
                        "message": "Invalid or expired token."
                    }, status=401)

                request.user = {
                    "id": row[0],
                    "user_name": row[1],
                    "email": row[2],
                    "profile_pic": row[3],
                    "device_id": row[4],
                    "device_name": row[5],
                    "platform": row[6],
                }

                # Update last used time
                cursor.execute("""
                    UPDATE user_tokens
                    SET last_used_at = NOW()
                    WHERE token = %s
                """, [token])

            return view_func(request, *args, **kwargs)

        except Exception as e:

            return JsonResponse({
                "status": "error",
                "message": str(e)
            }, status=500)

    return wrapper