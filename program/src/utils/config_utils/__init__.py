from ..config_service import *
import sys

module = sys.modules[__name__]
sys.modules.setdefault("src.utils.config_utils.config_service", module)
sys.modules.setdefault("program.src.utils.config_utils.config_service", module)
