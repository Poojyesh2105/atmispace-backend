from datetime import date

from django.test import TestCase

from apps.accounts.models import User
from apps.documents.models import DocumentType
from apps.documents.services.document_service import EmployeeDocumentService
from apps.employees.models import Department, Employee


class EmployeeDocumentServiceTestCase(TestCase):
    def setUp(self):
        department = Department.objects.create(name="HR", code="HR")
        self.hr_user = User.objects.create_user(email="hr-doc@test.com", password="Hr@12345", first_name="HR", last_name="User", role=User.Role.HR)
        self.employee_user = User.objects.create_user(email="employee-doc@test.com", password="Employee@123", first_name="Employee", last_name="User", role=User.Role.EMPLOYEE)
        self.employee = Employee.objects.create(
            user=self.employee_user,
            employee_id="EMP200",
            designation="Analyst",
            department=department,
            hire_date=date.today(),
        )
        self.document_type = DocumentType.objects.create(name="PAN", category="Tax", requires_expiry=False)

    def test_verify_document_marks_document_verified(self):
        document = EmployeeDocumentService.create_document(
            {
                "employee": self.employee,
                "document_type": self.document_type,
                "title": "PAN Card",
                "file_name": "pan.pdf",
                "file_url": "https://example.com/pan.pdf",
            },
            actor=self.employee_user,
        )
        verified = EmployeeDocumentService.verify_document(self.hr_user, document, "Looks valid")
        self.assertEqual(verified.status, verified.Status.VERIFIED)
        self.assertEqual(verified.verified_by_id, self.hr_user.pk)

