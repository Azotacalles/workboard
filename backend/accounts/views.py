from django.middleware.csrf import get_token
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.decorators import api_view, permission_classes
from rest_framework.views import APIView

from .serializers import RegisterSerializer, UserSerializer
from django.contrib.auth import get_user_model, login

User = get_user_model()

@api_view(['GET'])
def me(request):
    user = request.user
    return Response(UserSerializer(user).data)


@api_view(['GET'])
@permission_classes([AllowAny])
def csrf(request):
    return Response({'csrfToken': get_token(request)})


@method_decorator(csrf_protect, name='dispatch')
class RegisterAPIView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        if request.user.is_authenticated:
            return Response({'message': 'Вы уже вошли в аккаунт.'},
                            status=409
                            )
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        user = User.objects.create_user(
            email=data['email'],
            username=data['username'],
            password=data['password'],
        )
        login(request, user)
        return Response(UserSerializer(user).data, status=201)
