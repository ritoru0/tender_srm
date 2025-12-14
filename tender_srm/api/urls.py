from django.urls import path
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from . import views

urlpatterns = [
    # JWT токены
    path('token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    
    # Регистрация и аутентификация
    path('register/', views.OrganizationRegistrationAPIView.as_view(), name='api_register'),
    path('login/', views.LoginAPIView.as_view(), name='api_login'),
    path('check-activation/', views.CheckActivationAPIView.as_view(), name='api_check_activation'),
    
    # Профиль
    path('profile/', views.UserProfileAPIView.as_view(), name='api_profile'),
    
    # Менеджер 
    path('manager/pending-organizations/', views.PendingOrganizationsAPIView.as_view(), name='api_pending_organizations'),
    path('manager/organizations/<int:pk>/', views.OrganizationDetailAPIView.as_view(), name='api_organization_detail'),
    path('manager/organizations/<int:pk>/verify/', views.VerifyOrganizationAPIView.as_view(), name='api_verify_organization'),
    path('manager/pending-proposals/', views.PendingProposalsAPIView.as_view(), name='api_pending_proposals'),
    path('manager/proposals/<int:pk>/verify/', views.VerifyProposalAPIView.as_view(), name='api_verify_proposal'),
    path('manager/proposals/<int:pk>/', views.ProposalDetailAPIView.as_view(), name='api_proposal_detail'),
    path('manager/evaluations/<int:pk>/', views.EvaluationUpdateAPIView.as_view(), name='api_evaluation_update'),
    
    # Тендеры
    path('tenders/', views.TenderListAPIView.as_view(), name='api_tender_list'),
    path('tenders/create/', views.TenderCreateAPIView.as_view(), name='api_tender_create'),
    path('tenders/<int:pk>/', views.TenderDetailAPIView.as_view(), name='api_tender_detail'),
    
    # Предложения
    path('tenders/<int:tender_id>/proposal/', views.ProposalCreateAPIView.as_view(), name='api_proposal_create'),
]