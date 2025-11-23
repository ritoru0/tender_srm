from tenders.repositories.proposal_repository import ProposalRepository
from tenders.repositories.tender_repository import TenderRepository


class ProposalService:
    @staticmethod
    def submit_proposal(user, tender_id: int, files):
        if user.role != "Поставщик" or not hasattr(user, "organization"):
            raise PermissionError("Только поставщики могут подавать заявки")

        tender = TenderRepository.get_tender_by_id(tender_id)
        if not tender or tender.status != "Открыт":
            raise ValueError("Тендер недоступен")

        if tender.organization == user.organization:
            raise ValueError("Нельзя участвовать в своём тендере")

        if ProposalRepository.exists_for_tender_and_supplier(tender, user.organization):
            raise ValueError("Вы уже подали заявку")

        return ProposalRepository.create_proposal(tender, user.organization, files)