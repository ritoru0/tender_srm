from django.db import transaction
from tenders.models import Proposal, Document  


class ProposalRepository:
    @staticmethod
    def create_proposal(tender, supplier, files=()) -> Proposal:
        with transaction.atomic():
            proposal = Proposal.objects.create(
                tender=tender,
                supplier=supplier,
                status='Подана'  
            )
            for file in files:
                Document.objects.create(
                    proposal=proposal,
                    document_type="proposal",
                    name=file.name,
                    file=file,
                    verification_status="На проверке"
                )
        return proposal

    @staticmethod
    def exists_for_tender_and_supplier(tender, supplier) -> bool:
        return Proposal.objects.filter(tender=tender, supplier=supplier).exists()