from django.db import transaction
from django.db.models import QuerySet
from tenders.models import Evaluation, Tender, TenderCriterion
from decimal import Decimal
from typing import List


class EvaluationRepository:

    @staticmethod
    def get_evaluations_for_tender_criterion(tender_criterion_id: int, tender_id: int) -> QuerySet:
        return Evaluation.objects.filter(
            tender_criterion_id=tender_criterion_id,
            proposal__tender_id=tender_id,
            proposed_value__isnull=False
        ).select_related('proposal')

    @staticmethod
    @transaction.atomic
    def bulk_update_evaluations(evaluations: List[Evaluation], fields: list):
        Evaluation.objects.bulk_update(evaluations, fields)

    @staticmethod
    def get_quantitative_criteria_for_tender(tender: Tender) -> QuerySet:
        return tender.criteria.filter(criterion__criterion_type='Количественный').select_related('criterion')

    @staticmethod
    @transaction.atomic
    def create_evaluation(**kwargs) -> Evaluation:
        return Evaluation.objects.create(**kwargs)

    @staticmethod
    def get_by_id(evaluation_id: int) -> Evaluation | None:
        try:
            return Evaluation.objects.select_related('tender_criterion__tender').get(id=evaluation_id)
        except Evaluation.DoesNotExist:
            return None