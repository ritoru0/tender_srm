from decimal import Decimal, ROUND_HALF_UP
from django.db import transaction
from tenders.models import Tender, Evaluation
from tenders.repositories.evaluation_repository import EvaluationRepository


class EvaluationService:

    @staticmethod
    @transaction.atomic
    def recalculate_quantitative_scores(tender: Tender):
        """Дискретная нормализация 1–10 с шагом (цена 800→10, 1200→1, 1000→~7)"""
        quant_criteria = EvaluationRepository.get_quantitative_criteria_for_tender(tender)

        for tc in quant_criteria:
            criterion = tc.criterion

            evals = Evaluation.objects.filter(
                tender_criterion=tc,
                proposal__tender=tender,
                proposed_value__isnull=False
            )

            if not evals.exists():
                continue

            values = [e.proposed_value for e in evals]
            max_val = max(values)
            min_val = min(values)

            if max_val == min_val:
                evals.update(score=Decimal('10.0'), is_auto_calculated=True, evaluator=None)
                continue

            step = (max_val - min_val) / Decimal('9')

            updated = []
            for e in evals:
                val = e.proposed_value

                if criterion.direction == 'Максимизирующий':
                    distance = val - min_val
                else:  # Минимизирующий
                    distance = max_val - val

                raw_score = Decimal('1') + distance / step
                score = raw_score.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

                if score < Decimal('1.0'):
                    score = Decimal('1.0')
                if score > Decimal('10.0'):
                    score = Decimal('10.0')

                e.score = score
                e.is_auto_calculated = True
                e.evaluator = None
                updated.append(e)

            Evaluation.objects.bulk_update(updated, ['score', 'is_auto_calculated', 'evaluator'])

    @staticmethod
    @transaction.atomic
    def set_manual_score(evaluation, score: Decimal, manager):
        """Сохраняет ручную оценку качественного критерия"""
        if evaluation.tender_criterion.criterion.criterion_type != 'Качественный':
            raise ValueError("Можно оценивать только качественные критерии")

        evaluation.score = score
        evaluation.evaluator = manager
        evaluation.is_auto_calculated = False
        evaluation.save(update_fields=['score', 'evaluator', 'is_auto_calculated'])