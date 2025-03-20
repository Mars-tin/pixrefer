"""Interface modules for the pixrefer package."""

from pixrefer.interface.interface_reg_mask import MaskRegionDescriptionCollector
from pixrefer.interface.interface_rel_mask import MaskDescriptionEvaluator

__all__ = [
    'MaskRegionDescriptionCollector',
    'MaskDescriptionEvaluator',
] 