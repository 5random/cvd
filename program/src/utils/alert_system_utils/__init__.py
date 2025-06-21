from ..email_alert_service import *  # re-export everything
import sys
module = sys.modules[__name__]
sys.modules.setdefault("src.utils.alert_system_utils.email_alert_service", module)
sys.modules.setdefault("program.src.utils.alert_system_utils.email_alert_service", module)
