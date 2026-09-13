"""CostTier — категоризация стоимости ресурса (S1).

Источник: docs/ECOSYSTEM_FIRST_ARCHITECTURE.md §11, docs/ECOSYSTEM_FIRST_S1_DESIGN.md.
FREE/TRIAL/PAID/UNKNOWN. UNKNOWN ≠ FREE (аналогия с AD-18).
"""
from __future__ import annotations

from enum import Enum


class CostTier(str, Enum):
    """Категория стоимости ресурса (backend / workflow).

    - FREE: нулевая стоимость (local ComfyUI, open-source hosted).
    - TRIAL: нулевая текущая стоимость, без авто-escalation в PAID.
    - PAID: требует оплаты / подписки / billing-enabled API key.
    - UNKNOWN: стоимость не определена. Трактуется как НЕ FREE.
    """

    FREE = "FREE"
    TRIAL = "TRIAL"
    PAID = "PAID"
    UNKNOWN = "UNKNOWN"


# Ranking для сортировки среди допущенных кандидатов (higher = better).
COST_RANKING: dict[CostTier, int] = {
    CostTier.FREE: 3,
    CostTier.TRIAL: 2,
    CostTier.UNKNOWN: 1,
    CostTier.PAID: 0,
}
