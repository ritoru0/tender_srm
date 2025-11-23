from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.db import transaction
from django import forms
from django.forms import formset_factory

from .forms import CustomUserCreationForm
from .models import User, Organization, Tender, Proposal, Document, Manager, Criterion

from tenders.services.tender_service import TenderService
from tenders.services.proposal_service import ProposalService
from tenders.services.organization_service import OrganizationService

class TenderForm(forms.Form):
    title = forms.CharField(
        max_length=200, 
        label="Название тендера",
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    description = forms.CharField(
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 3}), 
        required=False, 
        label="Описание"
    )
    method = forms.ChoiceField(
        choices=[('AHP', 'AHP'), ('TOPSIS', 'TOPSIS')],
        label="Метод оценки",
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    start_date = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}), 
        label="Дата начала"
    )
    end_date = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}), 
        label="Дата окончания"
    )
    budget = forms.DecimalField(
        max_digits=15, 
        decimal_places=2, 
        label="Бюджет",
        widget=forms.NumberInput(attrs={'class': 'form-control'})
    )

class CriterionForm(forms.Form):
    criterion = forms.ModelChoiceField(
        queryset=Criterion.objects.all(),
        label="Критерий",
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    weight = forms.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        min_value=0,
        max_value=1,
        label="Вес (0-1)",
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'})
    )

CriterionFormSet = formset_factory(CriterionForm, extra=1)

# ===================== ОСНОВНЫЕ СТРАНИЦЫ =====================

def home(request):
    """Главная страница"""
    if request.user.is_authenticated:
        return redirect('dashboard')

    stats = {
        'tenders_count': Tender.objects.filter(status='Открыт').count(),
        'organizations_count': Organization.objects.filter(verification_status='Подтверждено').count(),
        'proposals_count': Proposal.objects.count(),
    }
    return render(request, 'home.html', {'stats': stats})

def register(request):
    """Регистрация (только Фирма и Поставщик)"""
    if request.user.is_authenticated:
        return redirect('dashboard')

    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST, request.FILES)
        if form.is_valid():
            user = form.save(commit=False)
            user.email = form.cleaned_data['email']
            user.is_active = False  
            user.save()

            if user.role in ['Фирма', 'Поставщик']:
                organization = Organization.objects.create(
                    user=user,
                    name=form.cleaned_data['name'],
                    fio=form.cleaned_data['fio'],
                    registration_number=form.cleaned_data['registration_number'],
                    org_type=form.cleaned_data['org_type'],
                    address=form.cleaned_data.get('address', ''),
                    phone=form.cleaned_data.get('phone', ''),
                    verification_status='На проверке'
                )

                docs = [
                    ('charter', 'Устав'),
                    ('inn', 'ИНН'),
                    ('ogrn', 'ОГРН')
                ]
                for field, name in docs:
                    file = request.FILES.get(field)
                    if file:
                        Document.objects.create(
                            organization=organization,
                            document_type='verification',
                            name=name,
                            file=file,
                            verification_status='На проверке'
                        )

            messages.success(request, 'Регистрация успешна! Ожидайте проверки документов.')
            return redirect('login')
    else:
        form = CustomUserCreationForm()

    return render(request, 'registration/register.html', {'form': form})

def login_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')

    if request.method == 'POST':
        username = request.POST['username']
        password = request.POST['password']
        user = authenticate(request, username=username, password=password)

        if user:
            if user.is_active:
                login(request, user)
                messages.success(request, f'Добро пожаловать, {user.username}!')
                return redirect('dashboard')
            else:
                messages.warning(request, 'Аккаунт ожидает проверки менеджером.')
        else:
            messages.error(request, 'Неверные данные.')

    return render(request, 'registration/login.html')

@login_required
def logout_view(request):
    logout(request)
    messages.success(request, 'Вы вышли из системы.')
    return redirect('home')

# ===================== ДАШБОРД =====================

@login_required
def dashboard(request):
    user = request.user
    context = {'user': user}

    if hasattr(user, 'organization'):
        context['organization'] = user.organization

    # Менеджер
    if user.role == 'Менеджер':
        context['pending_organizations_count'] = Organization.objects.filter(verification_status='На проверке').count()
        context['pending_proposals_count'] = Proposal.objects.filter(status__in=['Подана', 'Проверяется']).count()
        context['active_tenders_count'] = Tender.objects.filter(status='Открыт').count()

    # Фирма
    elif user.role == 'Фирма' and hasattr(user, 'organization'):
        context['my_tenders'] = Tender.objects.filter(organization=user.organization)
        context['active_tenders'] = Tender.objects.filter(status='Открыт').exclude(organization=user.organization)

    # Поставщик
    elif user.role == 'Поставщик' and hasattr(user, 'organization'):
        context['active_tenders'] = Tender.objects.filter(status='Открыт')
        context['my_proposals'] = Proposal.objects.filter(supplier=user.organization)

    return render(request, 'dashboard.html', context)

# ===================== МЕНЕДЖЕР =====================

@login_required
def manager_requests(request):
    if request.user.role != 'Менеджер':
        messages.error(request, 'Доступ запрещён')
        return redirect('dashboard')


    pending_orgs = Organization.objects.filter(
        verification_status='На проверке'
    ).select_related('user')

    pending_proposals = Proposal.objects.filter(
        status__in=['Подана', 'Проверяется']
    ).select_related('tender', 'supplier')

    return render(request, 'manager/requests.html', {
        'pending_organizations': pending_orgs,
        'pending_proposals': pending_proposals,
    })

@login_required
def manager_request_detail(request, request_id):
    if request.user.role != 'Менеджер':
        return redirect('dashboard')

    organization = get_object_or_404(
        Organization.objects.select_related('user'), 
        id=request_id
    )
    
    documents = Document.objects.filter(
        organization=organization, 
        document_type='verification'
    )
    
    return render(request, 'manager/request_detail.html', {
        'organization': organization,
        'documents': documents
    })

@login_required
def manager_verify_organization(request, organization_id):
    if request.user.role != 'Менеджер':
        messages.error(request, 'Доступ запрещён')
        return redirect('dashboard')

    organization = get_object_or_404(Organization, id=organization_id)

    if request.method == 'POST':
        action = request.POST.get('action')


        try:
            OrganizationService.verify_organization(
                manager_user=request.user,
                org_id=organization_id,
                status='Подтверждено' if action == 'approve' else 'Отклонено',
            )
            messages.success(request, f'Организация успешно {"подтверждена" if action == "approve" else "отклонена"}.')
        except Exception as e:
            messages.error(request, f'Ошибка: {e}')

        return redirect('manager_requests')

    return redirect('manager_request_detail', request_id=organization_id)

# ===================== ТЕНДЕРЫ =====================

@login_required
def tender_list(request):
    if request.user.role == 'Фирма' and hasattr(request.user, 'organization'):
        my_tenders = Tender.objects.filter(organization=request.user.organization)
        other_tenders = Tender.objects.filter(status='Открыт').exclude(organization=request.user.organization)
        context = {'my_tenders': my_tenders, 'other_tenders': other_tenders}
    else:
        context = {'tenders': Tender.objects.filter(status='Открыт')}

    return render(request, 'tenders/tender_list.html', context)

@login_required
def tender_detail(request, tender_id):

    tender = get_object_or_404(
        Tender.objects.select_related('organization')
            .prefetch_related('criteria__criterion', 'proposals__supplier'),
        id=tender_id
    )

    can_participate = (
        request.user.role == 'Поставщик' and
        hasattr(request.user, 'organization') and
        request.user.organization.verification_status == 'Подтверждено' and
        tender.status == 'Открыт' and
        tender.organization != request.user.organization
    )

    is_owner = (
        request.user.role == 'Фирма' and
        hasattr(request.user, 'organization') and
        tender.organization == request.user.organization
    )

    context = {
        'tender': tender,
        'can_participate': can_participate,
        'is_owner': is_owner,
    }

    if is_owner:
        context['proposals'] = tender.proposals.select_related('supplier').all()

    return render(request, 'tenders/tender_detail.html', context)

@login_required
def create_tender(request):
    if request.user.role != 'Фирма' or not hasattr(request.user, 'organization') or request.user.organization.verification_status != 'Подтверждено':
        messages.error(request, 'Только подтверждённые фирмы могут создавать тендеры')
        return redirect('dashboard')

    if request.method == 'POST':
        tender_form = TenderForm(request.POST)
        criteria_formset = CriterionFormSet(request.POST, prefix='criteria')
        
        if tender_form.is_valid() and criteria_formset.is_valid():
            try:
                criteria_data = []
                for form in criteria_formset:
                    if form.cleaned_data:
                        criteria_data.append({
                            'criterion_id': form.cleaned_data['criterion'].id,
                            'weight': form.cleaned_data['weight']
                        })

                tender_data = {
                    'title': tender_form.cleaned_data['title'],
                    'description': tender_form.cleaned_data.get('description', ''),
                    'method': tender_form.cleaned_data['method'],
                    'start_date': tender_form.cleaned_data['start_date'],
                    'end_date': tender_form.cleaned_data['end_date'],
                    'budget': tender_form.cleaned_data['budget'],
                    'criteria': criteria_data
                }

                tender = TenderService.create_tender(request.user, tender_data)
                messages.success(request, 'Тендер успешно создан!')
                return redirect('tender_detail', tender.id)

            except Exception as e:
                messages.error(request, f'Ошибка при создании тендера: {e}')
        else:
            messages.error(request, 'Пожалуйста, исправьте ошибки в форме.')
    
    else:
        tender_form = TenderForm()
        criteria_formset = CriterionFormSet(prefix='criteria')

    return render(request, 'tenders/create_tender.html', {
        'form': tender_form,
        'criteria_formset': criteria_formset
    })

@login_required
def create_proposal(request, tender_id):
    tender = get_object_or_404(Tender, id=tender_id, status='Открыт')

    if request.user.role != 'Поставщик' or not hasattr(request.user, 'organization') or request.user.organization.verification_status != 'Подтверждено':
        messages.error(request, 'Только подтверждённые поставщики могут подавать заявки')
        return redirect('tender_detail', tender_id)

    try:
        files = request.FILES.getlist('documents') if request.method == 'POST' else []
        proposal = ProposalService.submit_proposal(request.user, tender_id, files)
        messages.success(request, 'Заявка успешно подана!')
        return redirect('tender_detail', tender_id)
    except Exception as e:
        messages.error(request, str(e))
        return redirect('tender_detail', tender_id)

    return render(request, 'tenders/create_proposal.html', {'tender': tender})