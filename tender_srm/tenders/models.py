from django.db import models
from django.contrib.auth.models import AbstractUser
from django.core.validators import MinValueValidator, MaxValueValidator
from decimal import Decimal


class User(AbstractUser):
    ROLE_CHOICES = (
        ('Фирма', 'Фирма'),
        ('Поставщик', 'Поставщик'),
        ('Менеджер', 'Менеджер'),
    )
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='Фирма')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    groups = models.ManyToManyField(
        'auth.Group',
        verbose_name='groups',
        blank=True,
        help_text='The groups this user belongs to.',
        related_name='tenders_user_groups',  
        related_query_name='tenders_user',
    )
    user_permissions = models.ManyToManyField(
        'auth.Permission',
        verbose_name='user permissions',
        blank=True,
        help_text='Specific permissions for this user.',
        related_name='tenders_user_permissions',  
        related_query_name='tenders_user',
    )

    def __str__(self):
        return self.username


class Organization(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='organization')
    name = models.CharField("Название", max_length=200)
    fio = models.CharField("ФИО руководителя", max_length=100)
    registration_number = models.CharField("УНП", max_length=50, unique=True)
    org_type = models.CharField("Тип организации", max_length=50)
    description = models.TextField(blank=True)
    address = models.CharField(max_length=200, blank=True)
    phone = models.CharField(max_length=20, blank=True)

    STATUS_CHOICES = (
        ('На проверке', 'На проверке'),
        ('Подтверждено', 'Подтверждено'),
        ('Отклонено', 'Отклонено'),
    )
    verification_status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='На проверке')
    verified_at = models.DateTimeField(null=True, blank=True)
    verified_by = models.ForeignKey('Manager', on_delete=models.SET_NULL, null=True, blank=True, related_name='verified_organizations')

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Организация"
        verbose_name_plural = "Организации"


class Manager(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='manager_profile')
    fio = models.CharField("ФИО", max_length=100)
    phone = models.CharField(max_length=20, blank=True)

    def __str__(self):
        return self.fio


class Tender(models.Model):
    STATUS_CHOICES = (('Открыт', 'Открыт'), ('В оценке', 'В оценке'), ('Закрыт', 'Закрыт'))
    METHOD_CHOICES = (('AHP', 'AHP'), ('TOPSIS', 'TOPSIS'))

    title = models.CharField("Название тендера", max_length=200)
    description = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Открыт')
    method = models.CharField("Метод оценки", max_length=20, choices=METHOD_CHOICES)
    start_date = models.DateField()
    end_date = models.DateField()
    budget = models.DecimalField(max_digits=15, decimal_places=2, validators=[MinValueValidator(0)])
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='tenders')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title


class Criterion(models.Model):
    TYPE_CHOICES = (('Количественный', 'Количественный'), ('Качественный', 'Качественный'))
    DIRECTION_CHOICES = (('Максимизирующий', 'Максимизирующий'), ('Минимизирующий', 'Минимизирующий'))

    name = models.CharField("Название критерия", max_length=100, unique=True)
    description = models.TextField(blank=True)
    criterion_type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    max_value = models.DecimalField(max_digits=5, decimal_places=2, default=10.00)
    direction = models.CharField(max_length=20, choices=DIRECTION_CHOICES)

    def __str__(self):
        return self.name


class TenderCriterion(models.Model):
    tender = models.ForeignKey(Tender, on_delete=models.CASCADE, related_name='criteria')
    criterion = models.ForeignKey(Criterion, on_delete=models.CASCADE)
    weight = models.DecimalField(max_digits=5, decimal_places=2, validators=[MinValueValidator(0), MaxValueValidator(1)])

    class Meta:
        unique_together = ('tender', 'criterion')

    def __str__(self):
        return f"{self.criterion.name} — {self.weight}"


class Proposal(models.Model):
    STATUS_CHOICES = (
        ('Подана', 'Подана'),
        ('Проверяется', 'Проверяется'),
        ('Подтверждена', 'Подтверждена'),
        ('Отклонена', 'Отклонена'),
    )

    tender = models.ForeignKey(Tender, on_delete=models.CASCADE, related_name='proposals')
    supplier = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='proposals')
    description = models.JSONField(default=dict, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Подана')
    final_score = models.DecimalField(max_digits=5, decimal_places=2, default=0.0)
    submitted_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Заявка #{self.pk} от {self.supplier}"


class Document(models.Model):
    DOCUMENT_TYPE_CHOICES = (
        ('verification', 'Для верификации организации'),
        ('proposal', 'Для заявки на тендер'),
    )

    proposal = models.ForeignKey(
        Proposal,
        on_delete=models.CASCADE,
        related_name='documents',
        null=True,
        blank=True
    )
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name='verification_documents',
        null=True,
        blank=True
    )

    document_type = models.CharField(max_length=20, choices=DOCUMENT_TYPE_CHOICES, default='proposal')

    name = models.CharField("Название документа", max_length=100)
    file = models.FileField("Файл", upload_to='documents/')
    uploaded_at = models.DateTimeField(auto_now_add=True)
    verification_status = models.CharField(
        max_length=20,
        choices=[('На проверке', 'На проверке'), ('Подтвержден', 'Подтвержден'), ('Отклонен', 'Отклонен')],
        default='На проверке'
    )
    verified_by = models.ForeignKey(Manager, on_delete=models.SET_NULL, null=True, blank=True)

    def __str__(self):
        target = self.organization or self.proposal or "Неизвестно"
        return f"{self.name} — {target}"

    class Meta:
        verbose_name = "Документ"
        verbose_name_plural = "Документы"


class Evaluation(models.Model):
    proposal = models.ForeignKey(Proposal, on_delete=models.CASCADE, related_name='evaluations')
    tender_criterion = models.ForeignKey(TenderCriterion, on_delete=models.CASCADE)
    score = models.DecimalField(max_digits=5, decimal_places=2, validators=[MinValueValidator(1), MaxValueValidator(10)])
    comment = models.TextField(blank=True)
    evaluator = models.ForeignKey(Manager, on_delete=models.SET_NULL, null=True, blank=True)
    evaluated_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('proposal', 'tender_criterion')


class Contract(models.Model):
    proposal = models.OneToOneField(Proposal, on_delete=models.SET_NULL, null=True, blank=True)
    contract_number = models.CharField("Номер договора", max_length=50, unique=True)
    signed_date = models.DateField("Дата подписания")
    pdf_file = models.FileField("PDF договора", upload_to='contracts/')
    status = models.CharField(max_length=20, choices=[('Подписан', 'Подписан'), ('Расторгнут', 'Расторгнут')], default='Подписан')

    def __str__(self):
        return self.contract_number