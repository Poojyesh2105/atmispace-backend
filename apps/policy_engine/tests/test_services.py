from datetime import date

from django.test import TestCase

from apps.accounts.models import User
from apps.employees.models import Department, Employee
from apps.policy_engine.models import PolicyRule
from apps.policy_engine.services.policy_rule_service import PolicyRuleService


class PolicyRuleServiceTestCase(TestCase):
    def setUp(self):
        department = Department.objects.create(name="Policy", code="POL")
        user = User.objects.create_user(
            email="policy@test.com",
            password="Policy@123",
            first_name="Policy",
            last_name="Owner",
            role=User.Role.HR,
        )
        self.employee = Employee.objects.create(
            user=user,
            employee_id="EMP-POL",
            designation="HR",
            department=department,
            hire_date=date.today(),
        )
        self.rule = PolicyRule.objects.create(
            name="High CTC Flag",
            module=PolicyRule.Module.PAYROLL,
            condition_field="ctc_per_annum",
            condition_operator=PolicyRule.Operator.GREATER_THAN_EQUAL,
            condition_value="1000000",
            effect_type=PolicyRule.EffectType.FLAG,
        )

    def test_evaluate_returns_triggered_rule(self):
        self.employee.ctc_per_annum = "1500000"
        results = PolicyRuleService.evaluate(PolicyRule.Module.PAYROLL, self.employee)
        self.assertTrue(results[0]["triggered"])
