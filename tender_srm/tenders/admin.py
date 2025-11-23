from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User, Organization, Manager, Tender, TenderCriterion, Proposal, Document, Evaluation, Contract, Criterion
from tenders.services.tender_service import TenderService

# === ИНЛАЙНЫ ===
class OrganizationInline(admin.StackedInline):
    model = Organization
    can_delete = False
    fields = ('name', 'fio', 'registration_number', 'org_type', 'verification_status')
    extra = 0


class ManagerInline(admin.StackedInline):
    model = Manager
    can_delete = False
    extra = 0


class TenderCriterionInline(admin.TabularInline):
    model = TenderCriterion
    extra = 1


class ProposalInline(admin.TabularInline):
    model = Proposal
    fields = ('supplier', 'status', 'final_score')
    readonly_fields = ('final_score',)
    extra = 0


class DocumentInline(admin.TabularInline):
    model = Document
    extra = 0


class EvaluationInline(admin.TabularInline):
    model = Evaluation
    extra = 0


# === АДМИНКИ ===
@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ('username', 'email', 'role', 'is_active', 'created_at')
    list_filter = ('role', 'is_active', 'created_at')
    search_fields = ('username', 'email')
    readonly_fields = ('created_at',)
    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        ('Personal info', {'fields': ('email',)}),
        ('Permissions', {'fields': ('role', 'is_active', 'is_staff', 'is_superuser')}),
        ('Important dates', {'fields': ('last_login', 'created_at')}),
    )
    inlines = [OrganizationInline, ManagerInline]


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = ('name', 'registration_number', 'org_type', 'verification_status', 'user')
    list_filter = ('verification_status', 'org_type')
    search_fields = ('name', 'registration_number', 'fio')
    readonly_fields = ('verified_at',)
    inlines = [DocumentInline, ProposalInline]

    actions = ['approve_organizations', 'reject_organizations']

    def approve_organizations(self, request, queryset):
        updated = queryset.update(verification_status='Подтверждено')
        # Активация пользователей подтвержденных организаций
        for org in queryset:
            org.user.is_active = True
            org.user.save()
        self.message_user(request, f"Подтверждено организаций: {updated}")

    def reject_organizations(self, request, queryset):
        updated = queryset.update(verification_status='Отклонено')
        # Деакцивация пользователей отклоненных организаций
        for org in queryset:
            org.user.is_active = False
            org.user.save()
        self.message_user(request, f"Отклонено организаций: {updated}")

    approve_organizations.short_description = "Подтвердить выбранные организации"
    reject_organizations.short_description = "Отклонить выбранные организации"


@admin.register(Tender)
class TenderAdmin(admin.ModelAdmin):
    list_display = ('title', 'organization', 'status', 'method', 'start_date', 'end_date', 'budget')
    list_filter = ('status', 'method', 'start_date')
    search_fields = ('title', 'description', 'organization__name')
    readonly_fields = ('created_at',)
    inlines = [TenderCriterionInline, ProposalInline]


@admin.register(Proposal)
class ProposalAdmin(admin.ModelAdmin):
    list_display = ('tender', 'supplier', 'status', 'final_score', 'submitted_at')
    list_filter = ('status', 'submitted_at')
    search_fields = ('tender__title', 'supplier__name')
    readonly_fields = ('submitted_at',)
    inlines = [DocumentInline, EvaluationInline]


@admin.register(Criterion)
class CriterionAdmin(admin.ModelAdmin):
    list_display = ('name', 'criterion_type', 'direction', 'max_value')
    list_filter = ('criterion_type', 'direction')
    search_fields = ('name', 'description')
    
    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        # Очистка кеша при изменении критериев
        TenderService.clear_criteria_cache()
    
    def delete_model(self, request, obj):
        super().delete_model(request, obj)
        # Очистка кеша при удалении критериев
        TenderService.clear_criteria_cache()
    
    def delete_queryset(self, request, queryset):
        # Очистка кеша при массовом удалении
        super().delete_queryset(request, queryset)
        TenderService.clear_criteria_cache()


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = ('name', 'document_type', 'verification_status', 'uploaded_at')
    list_filter = ('document_type', 'verification_status', 'uploaded_at')
    search_fields = ('name',)
    readonly_fields = ('uploaded_at',)


@admin.register(Manager)
class ManagerAdmin(admin.ModelAdmin):
    list_display = ('user', 'fio', 'phone')
    search_fields = ('fio', 'user__username')


@admin.register(TenderCriterion)
class TenderCriterionAdmin(admin.ModelAdmin):
    list_display = ('tender', 'criterion', 'weight')
    list_filter = ('tender',)
    search_fields = ('tender__title', 'criterion__name')


@admin.register(Evaluation)
class EvaluationAdmin(admin.ModelAdmin):
    list_display = ('proposal', 'tender_criterion', 'score', 'evaluator', 'evaluated_at')
    list_filter = ('evaluated_at',)
    readonly_fields = ('evaluated_at',)


@admin.register(Contract)
class ContractAdmin(admin.ModelAdmin):
    list_display = ('contract_number', 'proposal', 'signed_date', 'status')
    list_filter = ('status', 'signed_date')
    search_fields = ('contract_number',)
    readonly_fields = ('signed_date',)