from rest_framework import status, generics
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import authenticate
from django.utils import timezone
from django.db import transaction
from tenders.models import User, Organization, Tender, Proposal, Document, Manager
from .serializers import (
    OrganizationRegistrationSerializer, UserSerializer,
    OrganizationDetailSerializer, ProposalSerializer,
    OrganizationVerificationSerializer, ProposalVerificationSerializer,
    TenderSerializer, TenderDetailSerializer,
    TenderCreateSerializer, TenderListSerializer, ProposalCreateSerializer
)
from tenders.services.tender_service import TenderService
from tenders.services.proposal_service import ProposalService
from tenders.services.organization_service import OrganizationService


# ===== АУТЕНТИФИКАЦИЯ =====
class OrganizationRegistrationAPIView(APIView):
    permission_classes = [AllowAny]
    
    def post(self, request):
        serializer = OrganizationRegistrationSerializer(
            data=request.data, 
            context={'request': request}
        )
        
        if serializer.is_valid():
            organization = serializer.save()
            user = organization.user
            refresh = RefreshToken.for_user(user)
            
            return Response({
                'message': 'Регистрация успешна. Полный доступ будет после проверки документов.',
                'user': {
                    'id': user.id,
                    'username': user.username,
                    'email': user.email,
                    'role': user.role,
                    'is_active': user.is_active,
                },
                'organization': {
                    'id': organization.id,
                    'name': organization.name,
                    'verification_status': organization.verification_status
                },
                'tokens': {
                    'refresh': str(refresh),
                    'access': str(refresh.access_token),
                },
                'restrictions': {
                    'can_create_tenders': False,
                    'can_participate_in_tenders': False,
                    'needs_verification': True
                }
            }, status=status.HTTP_201_CREATED)
        
        return Response({
            'message': 'Ошибка валидации',
            'errors': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)


class LoginAPIView(APIView):
    permission_classes = [AllowAny]
    
    def post(self, request):
        username = request.data.get('username')
        password = request.data.get('password')
        
        user = authenticate(username=username, password=password)
        
        if user:
            refresh = RefreshToken.for_user(user)
            
            response_data = {
                'message': 'Вход выполнен успешно' if user.is_active else 'Аккаунт ожидает проверки',
                'user': UserSerializer(user).data,
                'tokens': {
                    'refresh': str(refresh),
                    'access': str(refresh.access_token),
                }
            }
            
            if hasattr(user, 'organization'):
                response_data['organization'] = {
                    'id': user.organization.id,
                    'name': user.organization.name,
                    'verification_status': user.organization.verification_status
                }
            
            response_data['permissions'] = {
                'can_create_tenders': user.is_active and user.role == 'Фирма',
                'can_participate_in_tenders': user.is_active and user.role == 'Поставщик',
                'can_manage_verifications': user.is_active and user.role == 'Менеджер'
            }
            
            status_code = status.HTTP_200_OK if user.is_active else status.HTTP_202_ACCEPTED
            return Response(response_data, status=status_code)
        
        return Response({
            'message': 'Неверные учетные данные'
        }, status=status.HTTP_401_UNAUTHORIZED)


class UserProfileAPIView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        user = request.user
        serializer = UserSerializer(user)
        
        response_data = serializer.data
        response_data['permissions'] = {
            'can_create_tenders': user.is_active and user.role == 'Фирма',
            'can_participate_in_tenders': user.is_active and user.role == 'Поставщик',
            'can_manage_verifications': user.is_active and user.role == 'Менеджер'
        }
        
        if hasattr(user, 'organization'):
            response_data['organization'] = {
                'id': user.organization.id,
                'name': user.organization.name,
                'verification_status': user.organization.verification_status
            }
        
        return Response(response_data)


class CheckActivationAPIView(APIView):
    permission_classes = [AllowAny]
    
    def post(self, request):
        """Проверка активации аккаунта"""
        
        username = request.data.get('username')
        
        try:
            user = User.objects.get(username=username)
            response_data = {
                'username': user.username,
                'is_active': user.is_active,
            }
            
            if hasattr(user, 'organization'):
                response_data['verification_status'] = user.organization.verification_status
                response_data['organization_name'] = user.organization.name
            
            return Response(response_data)
        except User.DoesNotExist:
            return Response({
                'error': 'Пользователь не найден'
            }, status=status.HTTP_404_NOT_FOUND)


# ===== МЕНЕДЖЕР API =====

class ManagerPermission(IsAuthenticated):
    """Разрешение только для менеджеров"""
    
    def has_permission(self, request, view):
        return super().has_permission(request, view) and request.user.role == 'Менеджер'


class PendingOrganizationsAPIView(generics.ListAPIView):
    """Список организаций на проверку"""
    
    permission_classes = [ManagerPermission]
    serializer_class = OrganizationDetailSerializer
    
    def get_queryset(self):
        return Organization.objects.filter(
            verification_status='На проверке'
        ).select_related('user').prefetch_related('verification_documents')


class OrganizationDetailAPIView(generics.RetrieveAPIView):
    """Детальная информация об организации"""
    
    permission_classes = [ManagerPermission]
    
    serializer_class = OrganizationDetailSerializer
    queryset = Organization.objects.all()


class VerifyOrganizationAPIView(APIView):
    """Верификация организации менеджером — через сервис (единственная точка правды)"""
    permission_classes = [ManagerPermission]

    def post(self, request, pk):
        serializer = OrganizationVerificationSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        try:

            OrganizationService.verify_organization(
                manager_user=request.user,
                org_id=pk,
                status=serializer.validated_data['verification_status'],
            )
            
            organization = Organization.objects.get(pk=pk)

            return Response({
                'message': f'Организация {serializer.validated_data["verification_status"].lower()}',
                'organization_id': organization.id,
                'verification_status': organization.verification_status,
                'verified_at': organization.verified_at,
                'verified_by': organization.verified_by.fio if organization.verified_by else None
            }, status=status.HTTP_200_OK)

        except Organization.DoesNotExist:
            return Response({'error': 'Организация не найдена'}, status=status.HTTP_404_NOT_FOUND)
        except PermissionError as e:
            return Response({'error': str(e)}, status=status.HTTP_403_FORBIDDEN)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


class PendingProposalsAPIView(generics.ListAPIView):
    """Список предложений на проверку"""
    
    permission_classes = [ManagerPermission]
    serializer_class = ProposalSerializer
    
    def get_queryset(self):
        return Proposal.objects.filter(
            status__in=['Подана', 'Проверяется']
        ).select_related('supplier', 'tender')


class VerifyProposalAPIView(APIView):
    """Верификация предложения менеджером"""
    
    permission_classes = [ManagerPermission]
    
    def post(self, request, pk):
        try:
            proposal = Proposal.objects.get(pk=pk)
        except Proposal.DoesNotExist:
            return Response({'error': 'Предложение не найдено'}, status=status.HTTP_404_NOT_FOUND)
        
        serializer = ProposalVerificationSerializer(data=request.data)
        if serializer.is_valid():
            status_value = serializer.validated_data['status']
            notes = serializer.validated_data.get('notes', '')
            
            with transaction.atomic():
                proposal.status = status_value
                proposal.save()
                
                manager_profile, created = Manager.objects.get_or_create(
                    user=request.user,
                    defaults={'fio': request.user.get_full_name() or request.user.username}
                )
                
                proposal.documents.update(
                    verification_status='Подтвержден' if status_value == 'Подтверждена' else 'Отклонен',
                    verified_by=manager_profile
                )
            
            return Response({
                'message': f'Предложение {status_value.lower()}',
                'proposal_id': proposal.id,
                'status': status_value
            })
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# ===== ТЕНДЕРЫ API =====

class TenderListAPIView(generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = TenderListSerializer
    
    def get_queryset(self):
        user = self.request.user
        if user.role == 'Фирма' and hasattr(user, 'organization'):
            return Tender.objects.filter(status='Открыт')
        else:
            return Tender.objects.filter(status='Открыт')


class TenderCreateAPIView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """Получение списка критериев для формы создания тендера"""
        try:
            criteria = TenderService.get_criteria_list()
            serializer = CriterionSerializer(criteria, many=True)
            return Response(serializer.data)
        except Exception as e:
            return Response({"error": str(e)}, status=400)

    def post(self, request):
        serializer = TenderCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=400)
        
        try:
            tender = TenderService.create_tender(request.user, serializer.validated_data)
            return Response({"message": "Тендер создан", "id": tender.id}, status=201)
        except PermissionError as e:
            return Response({"error": str(e)}, status=403)
        except Exception as e:
            return Response({"error": str(e)}, status=400)


class TenderDetailAPIView(generics.RetrieveAPIView):
    permission_classes = [IsAuthenticated]
    queryset = Tender.objects.all()
    serializer_class = TenderDetailSerializer


# ===== ПРЕДЛОЖЕНИЯ API =====

class ProposalCreateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, tender_id):
        try:
            proposal = ProposalService.submit_proposal(
                request.user, tender_id, request.FILES.getlist("documents")
            )
            return Response({"message": "Заявка подана", "id": proposal.id}, status=201)
        except (PermissionError, ValueError) as e:
            return Response({"error": str(e)}, status=400)