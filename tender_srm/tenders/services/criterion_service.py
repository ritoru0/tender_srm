from typing import List, Dict, Optional
from tenders.repositories.criterion_repository import CriterionRepository
from tenders.models import Criterion


class CriterionService:
    @staticmethod
    def list_criteria(
        search: str = None,
        criterion_type: str = None,
        direction: str = None
    ) -> List[Criterion]:
        queryset = CriterionRepository.get_all()

        if search:
            queryset = CriterionRepository.filter_by_name(search)
        if criterion_type:
            queryset = CriterionRepository.filter_by_type(criterion_type)
        if direction:
            queryset = CriterionRepository.filter_by_direction(direction)

        return queryset

    @staticmethod
    def create_criterion(validated_data: dict) -> Criterion:
        return CriterionRepository.create(validated_data)

    @staticmethod
    def update_criterion(criterion: Criterion, validated_data: dict) -> Criterion:
        return CriterionRepository.update(criterion, validated_data)

    @staticmethod
    def delete_criterion(criterion: Criterion) -> None:
        CriterionRepository.delete(criterion)

    @staticmethod
    def get_criterion_by_id(pk: int) -> Optional[Criterion]:
        return CriterionRepository.get_by_id(pk)