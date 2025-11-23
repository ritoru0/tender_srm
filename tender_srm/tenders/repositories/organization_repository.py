from django.db import transaction
from django.utils import timezone
from tenders.models import Organization, Manager


class OrganizationRepository:
    @staticmethod
    def get_pending_for_verification():
        return Organization.objects.filter(verification_status="На проверке") \
            .prefetch_related("user", "verification_documents")

    @staticmethod
    @transaction.atomic
    def update_verification_status(org_id: int, status: str, manager=None):

        org = Organization.objects.select_for_update().get(id=org_id)
        
        org.verification_status = status
        org.verified_at = timezone.now()
        org.verified_by = manager

        if status == "Подтверждено":
            org.user.is_active = True
            org.user.save(update_fields=["is_active"])
            org.verification_documents.all().update(
                verification_status="Подтвержден",
                verified_by=manager
            )
        elif status == "Отклонено":
            org.user.is_active = False
            org.user.save(update_fields=["is_active"])
            org.verification_documents.all().update(
                verification_status="Отклонен",
                verified_by=manager
            )

        org.save(update_fields=[
            "verification_status",
            "verified_at",
            "verified_by"
        ])

        return org