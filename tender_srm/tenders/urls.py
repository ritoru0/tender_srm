from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('register/', views.register, name='register'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('dashboard/', views.dashboard, name='dashboard'),
    
    # Менеджер
    path('manager/requests/', views.manager_requests, name='manager_requests'),
    path('manager/request/<int:request_id>/', views.manager_request_detail, name='manager_request_detail'),
    path('manager/verify-organization/<int:organization_id>/', views.manager_verify_organization, name='manager_verify_organization'),
    
    # Тендеры
    path('tenders/', views.tender_list, name='tender_list'),
    path('tenders/<int:tender_id>/', views.tender_detail, name='tender_detail'),
    path('tenders/create/', views.create_tender, name='create_tender'),
    path('tenders/<int:tender_id>/proposal/', views.create_proposal, name='create_proposal'),
]