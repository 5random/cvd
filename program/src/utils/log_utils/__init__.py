from ..log_service import *  # re-export all symbols

# Optional alias entries for backward compatibility
import sys
module = sys.modules[__name__]
sys.modules.setdefault("src.utils.log_utils", module)
sys.modules.setdefault("src.utils.log_utils.log_service", module)
