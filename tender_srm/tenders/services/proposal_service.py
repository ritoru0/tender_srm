from decimal import Decimal, InvalidOperation
from django.db import transaction
from django.core.exceptions import PermissionDenied, ValidationError
from tenders.models import Tender, Document
from tenders.repositories.proposal_repository import ProposalRepository
from tenders.repositories.evaluation_repository import EvaluationRepository
from tenders.services.evaluation_service import EvaluationService


class ProposalService:

    @staticmethod
    @transaction.atomic
    def submit_proposal_with_criteria(user, tender_id: int, criteria_values: dict, files=None):
        """
        Подача заявки с значениями по критериям.
        ВАЖНО: пересчёт автооценок происходит ПОСЛЕ создания всех Evaluation!
        """
        if files is None:
            files = []

        try:
            tender = Tender.objects.select_related('organization').prefetch_related(
                'criteria__criterion'
            ).get(id=tender_id, status='Открыт')
        except Tender.DoesNotExist:
            raise ValidationError("Тендер не найден или уже закрыт.")

        supplier = getattr(user, 'organization', None)
        if not supplier:
            raise PermissionDenied("У вас нет привязанной организации.")
        if supplier.verification_status != 'Подтверждено':
            raise PermissionDenied("Ваша организация не подтверждена менеджером.")
        if tender.organization == supplier:
            raise PermissionDenied("Нельзя подавать заявку на свой тендер.")
        if ProposalRepository.exists_for_tender_and_supplier(tender, supplier):
            raise ValidationError("Вы уже подали заявку на этот тендер ранее.")

        proposal = ProposalRepository.create_proposal(
            tender=tender,
            supplier=supplier,
            files=files
        )

        for tender_criterion in tender.criteria.all():
            criterion = tender_criterion.criterion
            raw_value = criteria_values.get(str(criterion.id), "").strip()

            proposed_value = None
            if criterion.criterion_type == 'Количественный':
                if not raw_value:
                    raise ValidationError(f"Укажите значение для критерия: {criterion.name}")
                try:
                    proposed_value = Decimal(raw_value)
                    if proposed_value < 0:
                        raise ValidationError(f"Значение не может быть отрицательным: {criterion.name}")
                except (InvalidOperation, ValueError):
                    raise ValidationError(f"Некорректное число в поле '{criterion.name}'")

            EvaluationRepository.create_evaluation(
                proposal=proposal,
                tender_criterion=tender_criterion,
                proposed_value=proposed_value,
                score=Decimal('0.0'),
                is_auto_calculated=(criterion.criterion_type == 'Количественный')
            )

        EvaluationService.recalculate_quantitative_scores(tender)

        return proposal