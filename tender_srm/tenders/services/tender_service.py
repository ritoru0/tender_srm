from django.core.cache import cache
from django.conf import settings
from tenders.repositories.tender_repository import TenderRepository

class TenderService:
    @staticmethod
    def create_tender(user, validated_data):
        if user.role != "Фирма" or not hasattr(user, "organization"):
            raise PermissionError("Только подтверждённые фирмы могут создавать тендеры")
        if user.organization.verification_status != "Подтверждено":
            raise PermissionError("Организация не подтверждена")
        
        return TenderRepository.create(user.organization, validated_data)

    @staticmethod
    def get_list_for_user(user):
        if user.role == "Фирма" and hasattr(user, "organization"):
            return TenderRepository.get_tenders_for_user_organization(user.organization)
        return TenderRepository.get_open_tenders()

    @staticmethod
    def get_detail(tender_id):
        return TenderRepository.get_tender_by_id(tender_id)

    @staticmethod
    def get_criteria_list():
        
        cache_key = "criteria_list"
        criteria = cache.get(cache_key)
        
        if criteria is None:
            from tenders.models import Criterion
            criteria = list(Criterion.objects.all())
            cache.set(cache_key, criteria, settings.CACHE_TTL * 4)
        
        return criteria
    
    @staticmethod
    def clear_criteria_cache():
        """Очистка кеша критериев"""
        cache.delete("criteria_list")