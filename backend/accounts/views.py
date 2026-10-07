from django.middleware.csrf import get_token
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.decorators import api_view, permission_classes

from .serializers import UserSerializer


@api_view(['GET'])
def me(request):
    user = request.user
    return Response(UserSerializer(user).data)


@api_view(['GET'])
@permission_classes([AllowAny])
def csrf(request):
    return Response({'csrfToken': get_token(request)})