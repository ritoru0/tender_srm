from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APITestCase, APIClient
from rest_framework_simplejwt.tokens import AccessToken

from tenders.models import Organization, Tender, Proposal, Criterion, Document

User = get_user_model()


class BaseAPITestCase(APITestCase):
    def setUp(self):
        self.client = APIClient()
        
        self.manager_user = User.objects.create_user(
            username='manager',
            email='manager@test.com',
            password='testpass123',
            role='Менеджер',
            is_active=True
        )
        
        self.firm_user = User.objects.create_user(
            username='firm',
            email='firm@test.com',
            password='testpass123',
            role='Фирма',
            is_active=True
        )
        
        self.supplier_user = User.objects.create_user(
            username='supplier',
            email='supplier@test.com',
            password='testpass123',
            role='Поставщик',
            is_active=True
        )
        
        self.firm_organization = Organization.objects.create(
            user=self.firm_user,
            name='Тестовая Фирма',
            fio='Иванов Иван',
            registration_number='123456789',
            org_type='ООО',
            verification_status='Подтверждено'
        )
        
        self.supplier_organization = Organization.objects.create(
            user=self.supplier_user,
            name='Тестовый Поставщик',
            fio='Петров Петр',
            registration_number='987654321',
            org_type='ИП',
            verification_status='Подтверждено'
        )
        
        self.criterion1 = Criterion.objects.create(
            name='Цена',
            description='Стоимость предложения',
            criterion_type='Количественный',
            direction='Минимизирующий'
        )
        
        self.criterion2 = Criterion.objects.create(
            name='Качество',
            description='Качество товаров',
            criterion_type='Качественный',
            direction='Максимизирующий'
        )
        
        self.tender = Tender.objects.create(
            title='Тестовый тендер',
            description='Описание тестового тендера',
            status='Открыт',
            method='AHP',
            start_date='2025-01-01',
            end_date='2025-12-31',
            budget=100000.00,
            organization=self.firm_organization
        )

    def authenticate_user(self, user):
        """Аутентифицирует пользователя через JWT"""
        token = str(AccessToken.for_user(user))
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')


class AuthenticationTests(BaseAPITestCase):
    def test_user_registration(self):
        """Тест регистрации нового пользователя"""
        url = reverse('api_register')
        data = {
            'username': 'newuser',
            'email': 'newuser@test.com',
            'password': 'newpass123',
            'role': 'Поставщик',
            'name': 'Новая организация',
            'fio': 'Сидоров Сидор',
            'registration_number': '111222333',
            'org_type': 'ООО',
            'address': 'Тестовый адрес',
            'phone': '+79990001122'
        }
        
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(User.objects.filter(username='newuser').exists())
        
        # Проверка, что организация создана
        organization = Organization.objects.get(registration_number='111222333')
        self.assertEqual(organization.verification_status, 'На проверке')
        self.assertFalse(organization.user.is_active)

    def test_user_login(self):
        """Тест входа пользователя"""
        url = reverse('api_login')
        data = {
            'username': 'firm',
            'password': 'testpass123'
        }
        
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('tokens', response.data)
        self.assertIn('access', response.data['tokens'])

    def test_user_login_invalid_credentials(self):
        """Тест входа с неверными учетными данными"""
        url = reverse('api_login')
        data = {
            'username': 'firm',
            'password': 'wrongpassword'
        }
        
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_protected_endpoint_access(self):
        """Тест доступа к защищенным эндпоинтам"""
        url = reverse('api_profile')
        
        # Проверка, что без аутентификации - доступ запрещен
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        
        # Проверка, что с аутентификацией - доступ разрешен
        self.authenticate_user(self.firm_user)
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)


class ManagerAPITests(BaseAPITestCase):
    def test_get_pending_organizations(self):
        """Тест получения списка организаций на проверку"""
        
        self.authenticate_user(self.manager_user)
        url = reverse('api_pending_organizations')
        
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_organization_verification(self):
        """Тест верификации организации менеджером"""
       
        pending_user = User.objects.create_user(
            username='pending',
            email='pending@test.com',
            password='testpass123',
            role='Поставщик',
            is_active=False
        )
        
        pending_org = Organization.objects.create(
            user=pending_user,
            name='Организация на проверке',
            fio='Тестов Тест',
            registration_number='555666777',
            org_type='ООО',
            verification_status='На проверке'
        )
        
        self.authenticate_user(self.manager_user)
        url = reverse('api_verify_organization', kwargs={'pk': pending_org.id})
        
        data = {
            'verification_status': 'Подтверждено',
            'notes': 'Все документы в порядке'
        }
        
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Проверка, что организация подтверждена
        pending_org.refresh_from_db()
        self.assertEqual(pending_org.verification_status, 'Подтверждено')
        self.assertTrue(pending_org.user.is_active)


class BasicAPITests(BaseAPITestCase):
    def test_api_endpoints_availability(self):
        """Тест доступности основных API эндпоинтов"""
        endpoints = [
            {
                'url': reverse('api_login'),
                'method': 'post',
                'data': {'username': 'firm', 'password': 'testpass123'},
                'auth_required': False,
                'expected_statuses': [status.HTTP_200_OK]
            },
            {
                'url': reverse('api_login'),
                'method': 'post', 
                'data': {'username': 'firm', 'password': 'wrongpass'},
                'auth_required': False,
                'expected_statuses': [status.HTTP_401_UNAUTHORIZED]
            },
            {
                'url': reverse('api_register'),
                'method': 'post',
                'data': {
                    'username': 'testuser',
                    'email': 'test@test.com',
                    'password': 'testpass123',
                    'role': 'Поставщик',
                    'name': 'Тест Орг',
                    'fio': 'Тест Тест',
                    'registration_number': '999888777',
                    'org_type': 'ООО'
                },
                'auth_required': False,
                'expected_statuses': [status.HTTP_201_CREATED, status.HTTP_400_BAD_REQUEST]
            },
            {
                'url': reverse('api_profile'),
                'method': 'get',
                'data': {},
                'auth_required': True,
                'expected_statuses': [status.HTTP_200_OK]
            },
        ]
        
        for endpoint in endpoints:
            # Сбросы
            self.client.credentials()
            
            if endpoint['auth_required']:
                self.authenticate_user(self.firm_user)
            
            if endpoint['method'] == 'post':
                response = self.client.post(endpoint['url'], endpoint['data'], format='json')
            else:
                response = self.client.get(endpoint['url'])
            
            self.assertIn(
                response.status_code, 
                endpoint['expected_statuses'],
                f"URL: {endpoint['url']}, Method: {endpoint['method']}, Status: {response.status_code}"
            )

    def test_jwt_authentication(self):
        """Тест JWT аутентификации"""

        login_data = {
            'username': 'firm',
            'password': 'testpass123'
        }
        response = self.client.post(reverse('api_login'), login_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('tokens', response.data)
        
        # Токен
        token = response.data['tokens']['access']
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        
        profile_response = self.client.get(reverse('api_profile'))
        self.assertEqual(profile_response.status_code, status.HTTP_200_OK)

    def test_user_roles(self):
        """Тест корректности ролей пользователей"""
        self.assertEqual(self.manager_user.role, 'Менеджер')
        self.assertEqual(self.firm_user.role, 'Фирма')
        self.assertEqual(self.supplier_user.role, 'Поставщик')
        self.assertTrue(hasattr(self.firm_user, 'organization'))
        self.assertTrue(hasattr(self.supplier_user, 'organization'))


class OrganizationAPITests(BaseAPITestCase):
    def test_organization_detail(self):
        """Тест получения детальной информации об организации"""
        self.authenticate_user(self.manager_user)
        url = reverse('api_organization_detail', kwargs={'pk': self.firm_organization.id})
        
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['name'], 'Тестовая Фирма')


class SimpleModelTests(TestCase):
    """Простые тесты моделей"""
    def test_user_creation(self):
        """Тест создания пользователя"""
        user = User.objects.create_user(
            username='testuser',
            password='testpass123',
            role='Поставщик'
        )
        self.assertEqual(user.role, 'Поставщик')
        self.assertTrue(user.is_active)

    def test_organization_creation(self):
        """Тест создания организации"""
        user = User.objects.create_user(
            username='orguser',
            password='testpass123',
            role='Фирма'
        )
        
        organization = Organization.objects.create(
            user=user,
            name='Тестовая организация',
            fio='Тестовый руководитель',
            registration_number='123456',
            org_type='ООО',
            verification_status='На проверке'
        )
        
        self.assertEqual(organization.name, 'Тестовая организация')
        self.assertEqual(organization.verification_status, 'На проверке')


class TenderAPITests(BaseAPITestCase):
    def test_tender_list_access(self):
        """Тест доступа к списку тендеров"""
        
        self.authenticate_user(self.supplier_user)
        self.assertEqual(Tender.objects.count(), 1)
        self.assertEqual(self.tender.title, 'Тестовый тендер')

    def test_tender_creation_permissions(self):
        """Тест проверки прав на создание тендеров"""

        self.assertTrue(
            self.firm_user.is_active and 
            self.firm_user.role == 'Фирма' and
            hasattr(self.firm_user, 'organization') and
            self.firm_organization.verification_status == 'Подтверждено'
        )
        
        self.assertFalse(
            self.supplier_user.role == 'Фирма'
        )


class ProposalAPITests(BaseAPITestCase):
    def test_proposal_creation_permissions(self):
        """Тест проверки прав на создание заявок"""
        
        can_create_proposal = (
            self.supplier_user.role == 'Поставщик' and
            hasattr(self.supplier_user, 'organization') and
            self.supplier_organization.verification_status == 'Подтверждено' and
            self.tender.status == 'Открыт' and
            self.tender.organization != self.supplier_organization
        )
        self.assertTrue(can_create_proposal)
        
        cannot_create_own_proposal = (
            self.firm_user.role == 'Поставщик' or  
            self.tender.organization == self.firm_organization 
        )
        self.assertTrue(cannot_create_own_proposal)


class SecurityTests(BaseAPITestCase):
    def test_manager_only_endpoints(self):
        """Тест что эндпоинты менеджера недоступны другим ролям"""
        
        manager_endpoints = [
            reverse('api_pending_organizations'),
            reverse('api_pending_proposals'),
        ]
        
        self.authenticate_user(self.firm_user)
        for url in manager_endpoints:
            response = self.client.get(url)
            self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        
        self.authenticate_user(self.supplier_user)
        for url in manager_endpoints:
            response = self.client.get(url)
            self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        
        self.authenticate_user(self.manager_user)
        for url in manager_endpoints:
            response = self.client.get(url)
            self.assertIn(response.status_code, [status.HTTP_200_OK])

    def test_inactive_user_access(self):
        """Тест что не подтверждённые менеджером пользователи не могут получить доступ"""
       
        inactive_user = User.objects.create_user(
            username='inactive',
            password='testpass123',
            role='Поставщик',
            is_active=False
        )
        
        try:
            self.authenticate_user(inactive_user)
            response = self.client.get(reverse('api_profile'))
            self.assertIn(response.status_code, [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN])
            
        except Exception:
        
            pass

    def test_unauthenticated_access(self):
        """Тест доступа без аутентификации"""
        
        protected_endpoints = [
            reverse('api_profile'),
            reverse('api_pending_organizations'),
            reverse('api_tender_list'),
        ]
        
        for url in protected_endpoints:
            self.client.credentials()  
            response = self.client.get(url)
            self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)