from django.shortcuts import render
from rest_framework.response import Response
from rest_framework.decorators import api_view
from .serializers import UserSerializer


@api_view(['GET'])
def me(request):
    user = request.user
    return Response(UserSerializer(user).data)