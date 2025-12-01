from celery import shared_task
from django.core.mail import send_mail
from django.conf import settings
from tenders.models import User, Organization  

@shared_task
def send_approval_email_to_firm(user_id, organization_id):
    """
    Отправляет письмо фирме при одобрении регистрации менеджером
    """
    try:
        user = User.objects.get(id=user_id)
        organization = Organization.objects.get(id=organization_id)
        
        subject = f"Регистрация {organization.name} одобрена!"
        message = f"""
        Здравствуйте!

        Ваша регистрация на платформе Tender SRM успешно одобрена менеджером!

        Данные организации:
        - Название: {organization.name}
        - ID: {organization.id}
        - Статус: Активна 

        Теперь вы можете:
        • Просматривать тендеры
        • Отправлять предложения
        • Управлять профилем

        Логин: {user.username}
        Перейдите в личный кабинет: http://127.0.0.1:8000/profile/

        С уважением,
        Команда Tender SRM
        """
        
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            fail_silently=False,
        )
        
        return f"Письмо отправлено {user.email}"
        
    except Exception as e:
        return f"Ошибка отправки: {str(e)}"
