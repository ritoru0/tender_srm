from typing import List, Optional
from django.db.models import QuerySet
from tenders.models import Tender, TenderCriterion, Criterion


class TenderRepository:
    @staticmethod
    def create(organization, validated_data: dict) -> Tender:
        criteria_data = validated_data.pop("criteria", [])
        tender = Tender.objects.create(organization=organization, **validated_data)
        
        for item in criteria_data:
            criterion = Criterion.objects.get(id=item["criterion_id"])
            TenderCriterion.objects.create(
                tender=tender,
                criterion=criterion,
                weight=item["weight"]
            )
        return tender

    @staticmethod
    def get_open_tenders() -> QuerySet:
        return Tender.objects.filter(status="Открыт") \
            .select_related("organization") \
            .prefetch_related("criteria__criterion")

    @staticmethod
    def get_tender_by_id(tender_id: int) -> Optional[Tender]:
        try:
            return Tender.objects.prefetch_related(
                "criteria__criterion", "proposals__supplier__user"
            ).get(id=tender_id)
        except Tender.DoesNotExist:
            return None

    @staticmethod
    def get_tenders_for_user_organization(org) -> QuerySet:
        return Tender.objects.filter(organization=org) | Tender.objects.filter(status="Открыт")