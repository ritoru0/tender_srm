from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.db import transaction
from django import forms
from django.forms import formset_factory

from django.core.paginator import Paginator
from .forms import CustomUserCreationForm
from .models import User, Organization, Tender, Proposal, Document, Manager, Criterion

from tenders.services.tender_service import TenderService
from tenders.services.proposal_service import ProposalService
from tenders.services.organization_service import OrganizationService

from tenders.services.criterion_service import CriterionService
from django.db.models import Count, Q
from tenders.services.evaluation_service import EvaluationService


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

    # ========== МЕНЕДЖЕР ==========
    if user.role == 'Менеджер':
        context.update({
            'pending_organizations_count': Organization.objects.filter(verification_status='На проверке').count(),
            'pending_proposals_count': Proposal.objects.filter(status__in=['Подана', 'Проверяется']).count(),
            'active_tenders_count': Tender.objects.filter(status='Открыт').count(),
            'criteria_count': Criterion.objects.count(),  # ← ЭТО ОБЯЗАТЕЛЬНО!
        })

    # ========== ФИРМА ==========
    elif user.role == 'Фирма':
        if hasattr(user, 'organization') and user.organization.verification_status == 'Подтверждено':
            context['my_tenders'] = Tender.objects.filter(organization=user.organization)
            context['active_tenders'] = Tender.objects.filter(status='Открыт').exclude(organization=user.organization)

    # ========== ПОСТАВЩИК ==========
    elif user.role == 'Поставщик':
        if hasattr(user, 'organization') and user.organization.verification_status == 'Подтверждено':
            context['active_tenders'] = Tender.objects.filter(status='Открыт')
            context['my_proposals'] = Proposal.objects.filter(supplier=user.organization)

    return render(request, 'dashboard.html', context)

# ===================== МЕНЕДЖЕР =====================


@login_required
def manager_requests(request):
    if request.user.role != 'Менеджер':
        messages.error(request, 'Доступ запрещён')
        return redirect('dashboard')

    pending_organizations = Organization.objects.filter(
        verification_status='На проверке'
    ).select_related('user')

    pending_proposals = Proposal.objects.filter(status='Подана') \
        .select_related('tender', 'supplier', 'tender__organization') \
        .annotate(
            documents_count=Count('documents', distinct=True),
            quant_count=Count(
                'evaluations',
                filter=Q(evaluations__tender_criterion__criterion__criterion_type='Количественный'),
                distinct=True
            ),
            qual_count=Count(
                'evaluations',
                filter=Q(evaluations__tender_criterion__criterion__criterion_type='Качественный'),
                distinct=True
            )
        )

    return render(request, 'manager/requests.html', {
        'pending_organizations': pending_organizations,
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

@login_required
def manager_proposal_evaluate(request, proposal_id):
    if request.user.role != 'Менеджер':
        messages.error(request, 'Доступ запрещён')
        return redirect('dashboard')

    proposal = get_object_or_404(
        Proposal.objects.select_related('tender', 'supplier', 'tender__organization')
                       .prefetch_related('documents', 'evaluations__tender_criterion__criterion'),
        id=proposal_id,
        status='Подана'
    )

    # Обновляем автооценки при открытии страницы
    EvaluationService.recalculate_quantitative_scores(proposal.tender)

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'reject':
            proposal.status = 'Отклонена'
            proposal.save()
            messages.success(request, f'Заявка #{proposal.id} отклонена')
            return redirect('manager_requests')

        elif action == 'approve':
            # Проверяем, все ли качественные критерии оценены
            unevaluated = proposal.evaluations.filter(
                tender_criterion__criterion__criterion_type='Качественный',
                score=0
            ).exists()

            if unevaluated:
                messages.error(request, 'Оцените все качественные критерии перед подтверждением!')
            else:
                proposal.status = 'Подтверждена'
                proposal.save()
                messages.success(request, f'Заявка #{proposal.id} успешно подтверждена!')
                return redirect('manager_requests')

    # AJAX — сохранение оценки
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        evaluation_id = request.POST.get('evaluation_id')
        score_str = request.POST.get('score')

        if not evaluation_id or not score_str:
            return JsonResponse({'error': 'Нет данных'}, status=400)

        try:
            score = Decimal(score_str)
            if not (Decimal('1.0') <= score <= Decimal('10.0')):
                raise ValueError
        except:
            return JsonResponse({'error': 'Оценка должна быть числом от 1 до 10'}, status=400)

        evaluation = get_object_or_404(
            Evaluation,
            id=evaluation_id,
            proposal=proposal,
            tender_criterion__criterion__criterion_type='Качественный'
        )

        manager = Manager.objects.get_or_create(user=request.user)[0]
        EvaluationService.set_manual_score(evaluation, score, manager)

        return JsonResponse({'success': True, 'score': float(score)})

    return render(request, 'manager/proposal_evaluate.html', {
        'proposal': proposal,
        'tender': proposal.tender,
    })
    
# ===================== ТЕНДЕРЫ =====================

@login_required
def tender_list(request):
    tenders = Tender.objects.filter(status='Открыт').select_related('organization')

    # Фильтры
    search = request.GET.get('search')
    method = request.GET.get('method')
    ordering = request.GET.get('ordering', '-created_at')

    if search:
        tenders = tenders.filter(title__icontains=search)
    if method:
        tenders = tenders.filter(method=method)

    tenders = tenders.order_by(ordering)

    # Пагинация

    paginator = Paginator(tenders, 9)  # 9 тендеров на страницу
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'page_obj': page_obj,
        'paginator': paginator,
    }

    if request.user.role == 'Фирма' and hasattr(request.user, 'organization'):
        context['my_tenders'] = Tender.objects.filter(organization=request.user.organization)

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


class CriterionForm(forms.ModelForm):
    class Meta:
        model = Criterion
        fields = ['name', 'description', 'criterion_type', 'max_value', 'direction']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'criterion_type': forms.Select(attrs={'class': 'form-select'}),
            'max_value': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'direction': forms.Select(attrs={'class': 'form-select'}),
        }

@login_required
def manager_criteria_list(request):
    if request.user.role != 'Менеджер':
        messages.error(request, 'Доступ запрещён')
        return redirect('dashboard')

    # Получаем параметры фильтрации
    search = request.GET.get('q', '').strip()
    c_type = request.GET.get('type', '').strip()
    direction = request.GET.get('direction', '').strip()

    # Используем сервис!
    criteria = CriterionService.list_criteria(
        search=search or None,
        criterion_type=c_type or None,
        direction=direction or None
    )

    return render(request, 'manager/criteria_list.html', {
        'criteria': criteria,
        'query': search,
        'type_filter': c_type,
        'direction_filter': direction,
    })

@login_required
def manager_criteria_create(request):
    if request.user.role != 'Менеджер':
        return redirect('dashboard')

    if request.method == 'POST':
        form = CriterionForm(request.POST)
        if form.is_valid():
            CriterionService.create_criterion(form.cleaned_data)
            messages.success(request, 'Критерий успешно создан')
            return redirect('manager_criteria_list')
    else:
        form = CriterionForm()

    return render(request, 'manager/criteria_form.html', {
        'form': form,
        'title': 'Создание нового критерия'
    })

@login_required
def manager_criteria_edit(request, pk):
    if request.user.role != 'Менеджер':
        return redirect('dashboard')

    criterion = get_object_or_404(Criterion, pk=pk)

    if request.method == 'POST':
        form = CriterionForm(request.POST, instance=criterion)
        if form.is_valid():
            CriterionService.update_criterion(criterion, form.cleaned_data)
            messages.success(request, 'Критерий обновлён')
            return redirect('manager_criteria_list')
    else:
        form = CriterionForm(instance=criterion)

    return render(request, 'manager/criteria_form.html', {
        'form': form,
        'title': 'Редактирование критерия'
    })

@login_required
def manager_criteria_delete(request, pk):
    if request.user.role != 'Менеджер':
        return redirect('dashboard')

    criterion = get_object_or_404(Criterion, pk=pk)

    if request.method == 'POST':
        CriterionService.delete_criterion(criterion)
        messages.success(request, 'Критерий удалён')
        return redirect('manager_criteria_list')

    return render(request, 'manager/criteria_delete.html', {'criterion': criterion})

# views.py
@login_required
def create_proposal(request, tender_id):
    tender = get_object_or_404(
        Tender.objects.prefetch_related('criteria__criterion'),
        id=tender_id, status='Открыт'
    )

    if (request.user.role != 'Поставщик' or 
        not hasattr(request.user, 'organization') or 
        request.user.organization.verification_status != 'Подтверждено'):
        messages.error(request, 'Доступ запрещён')
        return redirect('tender_detail', tender_id)

    if request.method == 'POST':
        criteria_values = {}
        for key, value in request.POST.items():
            if key.startswith('criterion_'):
                crit_id = key.split('_')[1]
                criteria_values[crit_id] = value

        files = request.FILES.getlist('documents')

        try:
            ProposalService.submit_proposal_with_criteria(
                request.user, tender_id, criteria_values, files
            )
            messages.success(request, 'Заявка успешно подана!')
            return redirect('tender_detail', tender_id)
        except Exception as e:
            messages.error(request, str(e))

    return render(request, 'tenders/create_proposal.html', {'tender': tender})