"""Limatus is now Humanus: ``import limatus`` returns the ``humanus`` package."""
import sys
import warnings

import humanus

warnings.warn("limatus has been renamed to humanus; import humanus instead.", DeprecationWarning, stacklevel=2)

sys.modules[__name__] = humanus
