from django.db import transaction
from typing import List, Optional
from tenders.models import Criterion


class CriterionRepository:
    @staticmethod
    def get_all() -> List[Criterion]:
        return Criterion.objects.all().order_by('name')

    @staticmethod
    def filter_by_name(search: str) -> List[Criterion]:
        return Criterion.objects.filter(name__icontains=search)

    @staticmethod
    def filter_by_type(criterion_type: str) -> List[Criterion]:
        return Criterion.objects.filter(criterion_type=criterion_type)

    @staticmethod
    def filter_by_direction(direction: str) -> List[Criterion]:
        return Criterion.objects.filter(direction=direction)

    @staticmethod
    def get_by_id(pk: int) -> Optional[Criterion]:
        try:
            return Criterion.objects.get(pk=pk)
        except Criterion.DoesNotExist:
            return None

    @staticmethod
    @transaction.atomic
    def create(validated_data: dict) -> Criterion:
        return Criterion.objects.create(**validated_data)

    @staticmethod
    @transaction.atomic
    def update(instance: Criterion, validated_data: dict) -> Criterion:
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance

    @staticmethod
    @transaction.atomic
    def delete(instance: Criterion) -> None:
        instance.delete()