from django.shortcuts import render
from .models import Memes
from django.http import JsonResponse
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
        return JsonResponse({"status": "blah"})
    except Exception as e:
        return JsonResponse({"status": "error", "message": str(e)})