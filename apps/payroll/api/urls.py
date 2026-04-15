from rest_framework.routers import DefaultRouter

from apps.payroll.api.views import DeductionRuleViewSet, PayrollAdjustmentViewSet, PayrollCycleViewSet, PayrollRunViewSet, PayslipViewSet, SalaryRevisionViewSet

router = DefaultRouter()
router.register("payslips", PayslipViewSet, basename="payslip")
router.register("cycles", PayrollCycleViewSet, basename="payroll-cycle")
router.register("runs", PayrollRunViewSet, basename="payroll-run")
router.register("adjustments", PayrollAdjustmentViewSet, basename="payroll-adjustment")
router.register("deduction-rules", DeductionRuleViewSet, basename="deduction-rule")
router.register("salary-revisions", SalaryRevisionViewSet, basename="salary-revision")

urlpatterns = router.urls

