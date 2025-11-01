from django.shortcuts import render
from .models import Memes
from django.http import HttpResponse, JsonResponse
from .serializers import MemesSerializer
# Create your views here.


def get_memes(request):
    try:
        type = request.GET.get('meme_type', None)
        if type is None:
            queryset = Memes.objects.all().order_by('-created_at') # newest first
            
        else:
            queryset = Memes.objects.all().order_by('-created_at').filter(type = type) # newest first
        serializer = MemesSerializer(queryset, many=True)
        return JsonResponse({"status": "success", "data": serializer.data})
    except Exception as e:
        return JsonResponse({"status": "error", "message": str(e)})
    
def privacy_policy(request):
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

def webhook(request):
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
        # Handle webhook events (Instagram sends updates here)
        try:
            data = request.body.decode('utf-8')
            print("📩 Received Webhook Event:", data)
            return JsonResponse({'status': 'received'}, status=200)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)

    else:
        return HttpResponse(status=405)