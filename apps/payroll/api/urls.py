from rest_framework.routers import DefaultRouter

from apps.payroll.api.views import (
    EmployeeSalaryComponentTemplateViewSet,
    PayrollAdjustmentViewSet,
    PayrollCycleViewSet,
    PayrollRunViewSet,
    PayslipTemplateViewSet,
    PayslipViewSet,
    SalaryComponentViewSet,
    SalaryComponentTemplateViewSet,
    SalaryRevisionViewSet,
)

router = DefaultRouter()
router.register("payslips", PayslipViewSet, basename="payslip")
router.register("cycles", PayrollCycleViewSet, basename="payroll-cycle")
router.register("runs", PayrollRunViewSet, basename="payroll-run")
router.register("adjustments", PayrollAdjustmentViewSet, basename="payroll-adjustment")
router.register("salary-revisions", SalaryRevisionViewSet, basename="salary-revision")
router.register("component-templates", SalaryComponentTemplateViewSet, basename="salary-component-template")
router.register("component-template-assignments", EmployeeSalaryComponentTemplateViewSet, basename="salary-component-template-assignment")
router.register("components", SalaryComponentViewSet, basename="salary-component")
router.register("templates", PayslipTemplateViewSet, basename="payslip-template")

urlpatterns = router.urls
