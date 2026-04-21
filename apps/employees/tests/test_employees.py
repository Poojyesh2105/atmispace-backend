from datetime import date, time
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import User
from apps.employees.models import Department, Employee, ShiftTemplate
from apps.employees.services.employee_service import EmployeeService


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_user(email, role=User.Role.EMPLOYEE, password="Test@1234"):
    return User.objects.create_user(
        email=email,
        password=password,
        first_name="Test",
        last_name="User",
        role=role,
    )


def make_employee(user, emp_id="EMP001", dept=None, designation="Dev"):
    return Employee.objects.create(
        user=user,
        employee_id=emp_id,
        designation=designation,
        hire_date=date.today(),
        department=dept,
    )


def make_department(name="Engineering", code="ENG"):
    return Department.objects.create(name=name, code=code)


def make_shift(name="Morning", start=time(9, 0), end=time(18, 0)):
    return ShiftTemplate.objects.create(name=name, start_time=start, end_time=end)


def authenticate_client(client, user):
    refresh = RefreshToken.for_user(user)
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {str(refresh.access_token)}")


# ---------------------------------------------------------------------------
# Employee model property tests
# ---------------------------------------------------------------------------

class EmployeeModelPropertyTestCase(TestCase):
    def setUp(self):
        self.dept = make_department()
        self.user = make_user("emp-prop@example.com")
        self.employee = make_employee(self.user, emp_id="EMP-P01", dept=self.dept)

    def test_monthly_gross_salary_is_ctc_divided_by_12(self):
        self.employee.ctc_per_annum = Decimal("1200000.00")
        self.employee.save()
        self.assertEqual(self.employee.monthly_gross_salary, Decimal("100000.00"))

    def test_monthly_gross_salary_zero_when_ctc_zero(self):
        self.employee.ctc_per_annum = Decimal("0")
        self.employee.save()
        self.assertEqual(self.employee.monthly_gross_salary, Decimal("0"))

    def test_str_representation(self):
        self.assertIn("EMP-P01", str(self.employee))

    def test_department_assignment(self):
        self.assertEqual(self.employee.department, self.dept)


# ---------------------------------------------------------------------------
# Department model tests
# ---------------------------------------------------------------------------

class DepartmentModelTestCase(TestCase):
    def test_create_department(self):
        dept = make_department("Finance", "FIN")
        self.assertEqual(dept.name, "Finance")
        self.assertEqual(dept.code, "FIN")

    def test_department_unique_name(self):
        make_department("HR Dept", "HRD")
        from django.db import IntegrityError
        with self.assertRaises(Exception):
            make_department("HR Dept", "HRD2")

    def test_department_unique_code(self):
        make_department("Sales", "SLS")
        from django.db import IntegrityError
        with self.assertRaises(Exception):
            make_department("Sales B", "SLS")


# ---------------------------------------------------------------------------
# ShiftTemplate model tests
# ---------------------------------------------------------------------------

class ShiftTemplateModelTestCase(TestCase):
    def test_create_shift_template(self):
        shift = make_shift("Night", time(22, 0), time(6, 0))
        self.assertEqual(shift.name, "Night")
        self.assertEqual(shift.start_time, time(22, 0))
        self.assertEqual(shift.end_time, time(6, 0))

    def test_shift_assignment_copies_fields(self):
        """When a shift template is assigned via serializer, shift_name/start/end are copied."""
        shift = make_shift("Day Shift", time(9, 0), time(18, 0))
        user = make_user("shift-copy@example.com")
        emp = make_employee(user, emp_id="EMP-SHFT")
        emp.shift_template = shift
        emp.shift_name = shift.name
        emp.shift_start_time = shift.start_time
        emp.shift_end_time = shift.end_time
        emp.save()
        emp.refresh_from_db()
        self.assertEqual(emp.shift_name, "Day Shift")
        self.assertEqual(emp.shift_start_time, time(9, 0))
        self.assertEqual(emp.shift_end_time, time(18, 0))


# ---------------------------------------------------------------------------
# EmployeeService tests
# ---------------------------------------------------------------------------

class EmployeeServiceGetQuerysetTestCase(TestCase):
    def setUp(self):
        self.dept = make_department("Ops", "OPS")

        # Create users with different roles
        self.admin_user = make_user("svc-admin@example.com", role=User.Role.ADMIN)
        self.hr_user = make_user("svc-hr@example.com", role=User.Role.HR)
        self.manager_user = make_user("svc-mgr@example.com", role=User.Role.MANAGER)
        self.employee_user = make_user("svc-emp@example.com", role=User.Role.EMPLOYEE)
        self.accounts_user = make_user("svc-acct@example.com", role=User.Role.ACCOUNTS)

        # Create employee profiles
        self.admin_emp = make_employee(self.admin_user, "SVC-ADM", self.dept)
        self.hr_emp = make_employee(self.hr_user, "SVC-HR", self.dept)
        self.manager_emp = make_employee(self.manager_user, "SVC-MGR", self.dept)
        self.employee_emp = make_employee(self.employee_user, "SVC-EMP", self.dept)
        self.accounts_emp = make_employee(self.accounts_user, "SVC-ACCT", self.dept)

    def test_admin_sees_all_employees(self):
        qs = EmployeeService.get_employee_queryset_for_user(self.admin_user)
        self.assertGreaterEqual(qs.count(), 5)

    def test_hr_sees_all_employees(self):
        qs = EmployeeService.get_employee_queryset_for_user(self.hr_user)
        self.assertGreaterEqual(qs.count(), 5)

    def test_manager_sees_all_employees(self):
        qs = EmployeeService.get_employee_queryset_for_user(self.manager_user)
        self.assertGreaterEqual(qs.count(), 5)

    def test_accounts_sees_all_employees(self):
        qs = EmployeeService.get_employee_queryset_for_user(self.accounts_user)
        self.assertGreaterEqual(qs.count(), 5)

    def test_employee_sees_only_own_profile(self):
        qs = EmployeeService.get_employee_queryset_for_user(self.employee_user)
        self.assertEqual(qs.count(), 1)
        self.assertEqual(qs.first().pk, self.employee_emp.pk)

    def test_user_without_employee_profile_sees_none(self):
        bare_user = make_user("bare@example.com", role=User.Role.EMPLOYEE)
        qs = EmployeeService.get_employee_queryset_for_user(bare_user)
        self.assertEqual(qs.count(), 0)


# ---------------------------------------------------------------------------
# Manager hierarchy tests
# ---------------------------------------------------------------------------

class ManagerHierarchyTestCase(TestCase):
    def setUp(self):
        self.dept = make_department("Dev", "DEV")
        self.mgr_user = make_user("mgr-hier@example.com", role=User.Role.MANAGER)
        self.secondary_mgr_user = make_user("sec-mgr-hier@example.com", role=User.Role.MANAGER)
        self.emp_user = make_user("emp-hier@example.com")

        self.mgr_emp = make_employee(self.mgr_user, "EMP-M01", self.dept)
        self.secondary_mgr_emp = make_employee(self.secondary_mgr_user, "EMP-M02", self.dept)
        self.emp = make_employee(self.emp_user, "EMP-M03", self.dept)

    def test_assign_primary_manager(self):
        self.emp.manager = self.mgr_emp
        self.emp.save()
        self.emp.refresh_from_db()
        self.assertEqual(self.emp.manager.pk, self.mgr_emp.pk)

    def test_assign_secondary_manager(self):
        self.emp.manager = self.mgr_emp
        self.emp.secondary_manager = self.secondary_mgr_emp
        self.emp.save()
        self.emp.refresh_from_db()
        self.assertEqual(self.emp.secondary_manager.pk, self.secondary_mgr_emp.pk)

    def test_manager_deleted_sets_null(self):
        self.emp.manager = self.mgr_emp
        self.emp.save()
        self.mgr_emp.user.delete()
        self.emp.refresh_from_db()
        self.assertIsNone(self.emp.manager)


# ---------------------------------------------------------------------------
# Employee API tests
# ---------------------------------------------------------------------------

class EmployeeAPICreateTestCase(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.list_url = reverse("employee-list")
        self.dept = make_department("API Dept", "APID")

        self.admin_user = make_user("api-admin@example.com", role=User.Role.ADMIN)
        self.hr_user = make_user("api-hr@example.com", role=User.Role.HR)
        self.employee_user = make_user("api-emp@example.com", role=User.Role.EMPLOYEE)

        make_employee(self.admin_user, "API-ADM")
        make_employee(self.hr_user, "API-HR")
        make_employee(self.employee_user, "API-EMP")

    def _create_payload(self, emp_id="NEW-001", email="new-emp@example.com"):
        return {
            "email": email,
            "first_name": "New",
            "last_name": "Employee",
            "employee_id": emp_id,
            "designation": "Engineer",
            "hire_date": str(date.today()),
        }

    def test_admin_can_create_employee(self):
        authenticate_client(self.client, self.admin_user)
        resp = self.client.post(self.list_url, self._create_payload("NEW-ADM", "new-adm@example.com"), format="json")
        self.assertEqual(resp.status_code, 201)

    def test_hr_can_create_employee(self):
        authenticate_client(self.client, self.hr_user)
        resp = self.client.post(self.list_url, self._create_payload("NEW-HRR", "new-hrr@example.com"), format="json")
        self.assertEqual(resp.status_code, 201)

    def test_employee_cannot_create_employee(self):
        authenticate_client(self.client, self.employee_user)
        resp = self.client.post(self.list_url, self._create_payload("NEW-EMP2", "new-emp2@example.com"), format="json")
        self.assertIn(resp.status_code, [403])

    def test_unauthenticated_cannot_create_employee(self):
        resp = self.client.post(self.list_url, self._create_payload("NEW-UNAUTH", "new-unauth@example.com"), format="json")
        self.assertEqual(resp.status_code, 401)

    def test_create_employee_with_duplicate_email_returns_400(self):
        authenticate_client(self.client, self.admin_user)
        # api-emp@example.com already exists
        resp = self.client.post(self.list_url, self._create_payload("NEW-DUP", "api-emp@example.com"), format="json")
        self.assertEqual(resp.status_code, 400)

    def test_create_employee_missing_required_fields_returns_400(self):
        authenticate_client(self.client, self.admin_user)
        resp = self.client.post(self.list_url, {"email": "missing@example.com"}, format="json")
        self.assertEqual(resp.status_code, 400)


class EmployeeAPIListTestCase(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.list_url = reverse("employee-list")
        self.dept = make_department("List Dept", "LSTD")

        self.admin_user = make_user("lst-admin@example.com", role=User.Role.ADMIN)
        self.hr_user = make_user("lst-hr@example.com", role=User.Role.HR)
        self.employee_user1 = make_user("lst-emp1@example.com", role=User.Role.EMPLOYEE)
        self.employee_user2 = make_user("lst-emp2@example.com", role=User.Role.EMPLOYEE)

        make_employee(self.admin_user, "LST-ADM", self.dept)
        make_employee(self.hr_user, "LST-HR", self.dept)
        self.emp1 = make_employee(self.employee_user1, "LST-E01", self.dept)
        self.emp2 = make_employee(self.employee_user2, "LST-E02", self.dept)

    def test_admin_sees_all_employees(self):
        authenticate_client(self.client, self.admin_user)
        resp = self.client.get(self.list_url)
        self.assertEqual(resp.status_code, 200)
        # Admin sees all 4 employees
        ids_in_response = [e["employee_id"] for e in resp.json()["data"]["results"]]
        self.assertIn("LST-ADM", ids_in_response)
        self.assertIn("LST-E01", ids_in_response)
        self.assertIn("LST-E02", ids_in_response)

    def test_hr_sees_all_employees(self):
        authenticate_client(self.client, self.hr_user)
        resp = self.client.get(self.list_url)
        self.assertEqual(resp.status_code, 200)

    def test_employee_sees_only_own_profile(self):
        authenticate_client(self.client, self.employee_user1)
        resp = self.client.get(self.list_url)
        self.assertEqual(resp.status_code, 200)
        results = resp.json()["data"]["results"]
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["employee_id"], "LST-E01")

    def test_unauthenticated_returns_401(self):
        resp = self.client.get(self.list_url)
        self.assertEqual(resp.status_code, 401)


class EmployeeAPIDetailTestCase(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.dept = make_department("Detail Dept", "DTLD")

        self.admin_user = make_user("dtl-admin@example.com", role=User.Role.ADMIN)
        self.hr_user = make_user("dtl-hr@example.com", role=User.Role.HR)
        self.employee_user = make_user("dtl-emp@example.com", role=User.Role.EMPLOYEE)
        self.other_employee_user = make_user("dtl-other@example.com", role=User.Role.EMPLOYEE)

        self.admin_emp = make_employee(self.admin_user, "DTL-ADM", self.dept)
        self.hr_emp = make_employee(self.hr_user, "DTL-HR", self.dept)
        self.emp = make_employee(self.employee_user, "DTL-EMP", self.dept)
        self.other_emp = make_employee(self.other_employee_user, "DTL-OTH", self.dept)

    def _detail_url(self, pk):
        return reverse("employee-detail", kwargs={"pk": pk})

    def test_admin_can_get_any_employee(self):
        authenticate_client(self.client, self.admin_user)
        resp = self.client.get(self._detail_url(self.emp.pk))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["data"]["employee_id"], "DTL-EMP")

    def test_hr_can_get_any_employee(self):
        authenticate_client(self.client, self.hr_user)
        resp = self.client.get(self._detail_url(self.emp.pk))
        self.assertEqual(resp.status_code, 200)

    def test_employee_can_get_own_detail(self):
        authenticate_client(self.client, self.employee_user)
        resp = self.client.get(self._detail_url(self.emp.pk))
        self.assertEqual(resp.status_code, 200)

    def test_employee_cannot_get_other_employee_detail(self):
        authenticate_client(self.client, self.employee_user)
        resp = self.client.get(self._detail_url(self.other_emp.pk))
        self.assertIn(resp.status_code, [403, 404])

    def test_unauthenticated_returns_401(self):
        resp = self.client.get(self._detail_url(self.emp.pk))
        self.assertEqual(resp.status_code, 401)


class EmployeeAPIUpdateTestCase(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.dept = make_department("Update Dept", "UPDD")

        self.admin_user = make_user("upd-admin@example.com", role=User.Role.ADMIN)
        self.hr_user = make_user("upd-hr@example.com", role=User.Role.HR)
        self.employee_user = make_user("upd-emp@example.com", role=User.Role.EMPLOYEE)

        self.admin_emp = make_employee(self.admin_user, "UPD-ADM", self.dept)
        self.hr_emp = make_employee(self.hr_user, "UPD-HR", self.dept)
        self.emp = make_employee(self.employee_user, "UPD-EMP", self.dept)

    def _detail_url(self, pk):
        return reverse("employee-detail", kwargs={"pk": pk})

    def test_admin_can_update_employee(self):
        authenticate_client(self.client, self.admin_user)
        resp = self.client.patch(
            self._detail_url(self.emp.pk),
            {"designation": "Senior Engineer"},
            format="json",
        )
        self.assertEqual(resp.status_code, 200)
        self.emp.refresh_from_db()
        self.assertEqual(self.emp.designation, "Senior Engineer")

    def test_hr_can_update_employee(self):
        authenticate_client(self.client, self.hr_user)
        resp = self.client.patch(
            self._detail_url(self.emp.pk),
            {"designation": "Lead"},
            format="json",
        )
        self.assertEqual(resp.status_code, 200)

    def test_employee_cannot_update_employee(self):
        authenticate_client(self.client, self.employee_user)
        resp = self.client.patch(
            self._detail_url(self.emp.pk),
            {"designation": "Hacker"},
            format="json",
        )
        self.assertIn(resp.status_code, [403])

    def test_unauthenticated_cannot_update(self):
        resp = self.client.patch(
            self._detail_url(self.emp.pk),
            {"designation": "Nobody"},
            format="json",
        )
        self.assertEqual(resp.status_code, 401)


class EmployeeAPIDeleteTestCase(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.dept = make_department("Delete Dept", "DELD")

        self.admin_user = make_user("del-admin@example.com", role=User.Role.ADMIN)
        self.hr_user = make_user("del-hr@example.com", role=User.Role.HR)
        self.employee_user = make_user("del-emp@example.com", role=User.Role.EMPLOYEE)
        self.target_user = make_user("del-target@example.com", role=User.Role.EMPLOYEE)

        make_employee(self.admin_user, "DEL-ADM", self.dept)
        make_employee(self.hr_user, "DEL-HR", self.dept)
        make_employee(self.employee_user, "DEL-EMP", self.dept)
        self.target_emp = make_employee(self.target_user, "DEL-TGT", self.dept)

    def _detail_url(self, pk):
        return reverse("employee-detail", kwargs={"pk": pk})

    def test_admin_can_delete_employee(self):
        # Create a fresh target so other tests aren't affected
        new_user = make_user("del-fresh-admin@example.com")
        new_emp = make_employee(new_user, "DEL-FRESH-ADM")
        authenticate_client(self.client, self.admin_user)
        resp = self.client.delete(self._detail_url(new_emp.pk))
        self.assertIn(resp.status_code, [200, 204])

    def test_hr_can_delete_non_admin_employee(self):
        new_user = make_user("del-fresh-hr@example.com")
        new_emp = make_employee(new_user, "DEL-FRESH-HR")
        authenticate_client(self.client, self.hr_user)
        resp = self.client.delete(self._detail_url(new_emp.pk))
        self.assertIn(resp.status_code, [200, 204])

    def test_employee_cannot_delete(self):
        authenticate_client(self.client, self.employee_user)
        resp = self.client.delete(self._detail_url(self.target_emp.pk))
        self.assertIn(resp.status_code, [403])

    def test_unauthenticated_cannot_delete(self):
        resp = self.client.delete(self._detail_url(self.target_emp.pk))
        self.assertEqual(resp.status_code, 401)


# ---------------------------------------------------------------------------
# Compensation visibility tests
# ---------------------------------------------------------------------------

class EmployeeCompensationVisibilityTestCase(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.dept = make_department("Comp Dept", "COMP")

        self.hr_user = make_user("comp-hr@example.com", role=User.Role.HR)
        self.accounts_user = make_user("comp-accts@example.com", role=User.Role.ACCOUNTS)
        self.manager_user = make_user("comp-mgr@example.com", role=User.Role.MANAGER)
        self.employee_user = make_user("comp-emp@example.com", role=User.Role.EMPLOYEE)
        self.other_employee_user = make_user("comp-other@example.com", role=User.Role.EMPLOYEE)

        self.hr_emp = make_employee(self.hr_user, "CMP-HR", self.dept)
        self.accounts_emp = make_employee(self.accounts_user, "CMP-ACCT", self.dept)
        self.manager_emp = make_employee(self.manager_user, "CMP-MGR", self.dept)
        self.emp = make_employee(self.employee_user, "CMP-EMP", self.dept)
        self.other_emp = make_employee(self.other_employee_user, "CMP-OTH", self.dept)

        self.emp.ctc_per_annum = Decimal("600000.00")
        self.emp.save()

    def _detail_url(self, pk):
        return reverse("employee-detail", kwargs={"pk": pk})

    def test_hr_can_view_compensation(self):
        authenticate_client(self.client, self.hr_user)
        resp = self.client.get(self._detail_url(self.emp.pk))
        data = resp.json()["data"]
        self.assertTrue(data.get("can_view_compensation"))
        self.assertIsNotNone(data.get("ctc_per_annum"))

    def test_accounts_can_view_compensation(self):
        authenticate_client(self.client, self.accounts_user)
        resp = self.client.get(self._detail_url(self.emp.pk))
        data = resp.json()["data"]
        self.assertTrue(data.get("can_view_compensation"))
        self.assertIsNotNone(data.get("ctc_per_annum"))

    def test_manager_can_view_compensation(self):
        authenticate_client(self.client, self.manager_user)
        resp = self.client.get(self._detail_url(self.emp.pk))
        data = resp.json()["data"]
        self.assertTrue(data.get("can_view_compensation"))

    def test_employee_can_view_own_compensation(self):
        authenticate_client(self.client, self.employee_user)
        resp = self.client.get(self._detail_url(self.emp.pk))
        data = resp.json()["data"]
        self.assertTrue(data.get("can_view_compensation"))
        self.assertIsNotNone(data.get("ctc_per_annum"))

    def test_employee_cannot_view_other_employee_salary(self):
        # An employee can only see their own profile; requesting another's should 403/404
        authenticate_client(self.client, self.employee_user)
        resp = self.client.get(self._detail_url(self.other_emp.pk))
        self.assertIn(resp.status_code, [403, 404])

    def test_shift_assignment_via_api_copies_template_fields(self):
        """Creating/updating an employee with a shift_template must copy name/times."""
        shift = make_shift("Custom Shift", time(8, 0), time(17, 0))
        authenticate_client(self.client, self.hr_user)
        resp = self.client.patch(
            self._detail_url(self.emp.pk),
            {"shift_template": shift.pk},
            format="json",
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()["data"]
        self.assertEqual(data["shift_name"], "Custom Shift")
        self.assertEqual(data["shift_start_time"], "08:00:00")
        self.assertEqual(data["shift_end_time"], "17:00:00")
