from datetime import date

from celery import shared_task


@shared_task
def process_monthly_leave_carry_forward():
    """
    Monthly task that runs on the 1st of each month.
    Processes leave carry forward for all active employees.
    """
    from apps.leave_management.services.carry_forward_service import LeaveCarryForwardService

    today = date.today()
    target_month = today.replace(day=1)
    count = LeaveCarryForwardService.process_carry_forward(target_month)
    return f"Carry forward processed for {count} employee(s) for {target_month.strftime('%Y-%m')}."
