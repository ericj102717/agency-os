"""Auto-generated wrapper module for task_appointment_auditor."""

from intelligence_backend import *

audit_tasks = crm_audit_tasks
audit_appointments = crm_audit_appointments
from pipeline_b_data_bridge import get_tasks as _get_tasks
DEMO_TASKS = _get_tasks()
from pipeline_b_data_bridge import get_appointments as _get_appts
DEMO_APPOINTMENTS = _get_appts()
