from rest_framework import serializers
from django.contrib.auth import get_user_model
from tenders.models import User, Organization, Tender, Proposal, Document, Manager, TenderCriterion, Criterion, Evaluation, Contract
from django.db import transaction


User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ('id', 'username', 'email', 'role', 'is_active', 'created_at')


class DocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Document
        fields = ('id', 'name', 'file', 'verification_status', 'uploaded_at')


class OrganizationRegistrationSerializer(serializers.ModelSerializer):
    # Поля пользователя
    username = serializers.CharField(max_length=150)
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, min_length=8)
    role = serializers.ChoiceField(choices=[('Фирма', 'Фирма'), ('Поставщик', 'Поставщик')])

    # Поля организации
    name = serializers.CharField(max_length=200)
    fio = serializers.CharField(max_length=100)
    registration_number = serializers.CharField(max_length=50)
    org_type = serializers.CharField(max_length=50)
    description = serializers.CharField(required=False, allow_blank=True)
    address = serializers.CharField(required=False, allow_blank=True)
    phone = serializers.CharField(required=False, allow_blank=True)

    # Документы
    charter = serializers.FileField(required=False)
    inn = serializers.FileField(required=False)
    ogrn = serializers.FileField(required=False)

    class Meta:
        model = Organization
        fields = (
            'username', 'email', 'password', 'role',
            'name', 'fio', 'registration_number', 'org_type',
            'description', 'address', 'phone',
            'charter', 'inn', 'ogrn'
        )

    def create(self, validated_data):
       
        username = validated_data.pop('username')
        email = validated_data.pop('email')
        password = validated_data.pop('password')
        role = validated_data.pop('role')
        
        charter = validated_data.pop('charter', None)
        inn = validated_data.pop('inn', None)
        ogrn = validated_data.pop('ogrn', None)

        with transaction.atomic():
            
            user = User.objects.create_user(
                username=username,
                email=email,
                password=password,
                role=role,
                is_active=False  
            )

            organization = Organization.objects.create(
                user=user,
                verification_status='На проверке',
                **validated_data
            )

            documents_data = [
                (charter, 'Устав'),
                (inn, 'Свидетельство ИНН'),
                (ogrn, 'Свидетельство ОГРН')
            ]
            
            for file, name in documents_data:
                if file:
                    Document.objects.create(
                        organization=organization,
                        document_type='verification',
                        name=name,
                        file=file,
                        verification_status='На проверке'
                    )

        return organization


class DocumentDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = Document
        fields = ('id', 'name', 'file', 'verification_status', 'uploaded_at')


class OrganizationDetailSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    verification_documents = DocumentDetailSerializer(many=True, read_only=True)
    
    class Meta:
        model = Organization
        fields = (
            'id', 'name', 'fio', 'registration_number', 'org_type',
            'description', 'address', 'phone', 'verification_status',
            'verified_at', 'user', 'verification_documents'
        )


class ProposalSerializer(serializers.ModelSerializer):
    supplier_name = serializers.CharField(source='supplier.name', read_only=True)
    tender_title = serializers.CharField(source='tender.title', read_only=True)
    
    class Meta:
        model = Proposal
        fields = (
            'id', 'tender', 'tender_title', 'supplier', 'supplier_name',
            'status', 'final_score', 'submitted_at'
        )


class OrganizationVerificationSerializer(serializers.Serializer):
    verification_status = serializers.ChoiceField(choices=[('Подтверждено', 'Подтверждено'), ('Отклонено', 'Отклонено')])
    notes = serializers.CharField(required=False, allow_blank=True)


class ProposalVerificationSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=[('Подтверждена', 'Подтверждена'), ('Отклонена', 'Отклонена')])
    notes = serializers.CharField(required=False, allow_blank=True)


class CriterionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Criterion
        fields = ('id', 'name', 'description', 'criterion_type', 'max_value', 'direction')


class TenderCriterionSerializer(serializers.ModelSerializer):
    criterion = CriterionSerializer(read_only=True)
    
    class Meta:
        model = TenderCriterion
        fields = ('id', 'criterion', 'weight')


class TenderSerializer(serializers.ModelSerializer):
    organization_name = serializers.CharField(source='organization.name', read_only=True)
    
    class Meta:
        model = Tender
        fields = (
            'id', 'title', 'description', 'status', 'method',
            'start_date', 'end_date', 'budget', 'organization', 'organization_name',
            'created_at'
        )


class TenderDetailSerializer(serializers.ModelSerializer):
    organization_name = serializers.CharField(source='organization.name', read_only=True)
    criteria = TenderCriterionSerializer(many=True, read_only=True)
    
    class Meta:
        model = Tender
        fields = (
            'id', 'title', 'description', 'status', 'method',
            'start_date', 'end_date', 'budget', 'organization', 'organization_name',
            'created_at', 'criteria'
        )

class TenderCreateSerializer(serializers.ModelSerializer):
    criteria = serializers.ListField(
        child=serializers.DictField(),
        write_only=True,
        required=False
    )
    
    class Meta:
        model = Tender
        fields = (
            'id', 'title', 'description', 'method',
            'start_date', 'end_date', 'budget', 'criteria'
        )

    def create(self, validated_data):
        criteria_data = validated_data.pop('criteria', [])
        tender = Tender.objects.create(**validated_data)
        
        for criterion_item in criteria_data:
            TenderCriterion.objects.create(
                tender=tender,
                criterion_id=criterion_item['criterion_id'],
                weight=criterion_item['weight']
            )
        
        return tender


class TenderListSerializer(serializers.ModelSerializer):
    organization_name = serializers.CharField(source='organization.name', read_only=True)
    proposals_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Tender
        fields = (
            'id', 'title', 'description', 'status', 'method',
            'start_date', 'end_date', 'budget', 'organization_name',
            'proposals_count', 'created_at'
        )
    
    def get_proposals_count(self, obj):
        return obj.proposals.count()


class ProposalCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Proposal
        fields = ('id', 'tender', 'supplier', 'description', 'status')
        read_only_fields = ('supplier', 'status')

    def create(self, validated_data):
        validated_data['supplier'] = self.context['request'].user.organization
        return super().create(validated_data)