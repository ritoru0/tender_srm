from tenders.repositories.organization_repository import OrganizationRepository
from tenders.models import Manager


class OrganizationService:
    @staticmethod
    def get_pending_organizations():
        return OrganizationRepository.get_pending_for_verification()

    @staticmethod
    def verify_organization(manager_user, org_id: int, status: str):

        if manager_user.role != "Менеджер":
            raise PermissionError("Только менеджеры могут проверять организации")

        allowed_statuses = ["Подтверждено", "Отклонено"]
        if status not in allowed_statuses:
            raise ValueError(f"Статус должен быть одним из: {allowed_statuses}")

        manager_profile, _ = Manager.objects.get_or_create(
            user=manager_user,
            defaults={'fio': manager_user.get_full_name() or manager_user.username}
        )

        return OrganizationRepository.update_verification_status(
            org_id=org_id,
            status=status,
            manager=manager_profile
        )