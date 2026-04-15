from rest_framework import serializers

from apps.accounts.models import User
from apps.employees.models import Department, Employee, OrganizationSettings, ShiftTemplate


class DepartmentSerializer(serializers.ModelSerializer):
    employee_count = serializers.IntegerField(source="employees.count", read_only=True)

    class Meta:
        model = Department
        fields = ("id", "name", "code", "description", "employee_count", "created_at", "updated_at")
        read_only_fields = ("id", "created_at", "updated_at", "employee_count")


class OrganizationSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrganizationSettings
        fields = ("id", "organization_name", "company_policies", "created_at", "updated_at")
        read_only_fields = ("id", "created_at", "updated_at")


class ShiftTemplateSerializer(serializers.ModelSerializer):
    class Meta:
        model = ShiftTemplate
        fields = ("id", "name", "start_time", "end_time", "description", "is_active", "created_at", "updated_at")
        read_only_fields = ("id", "created_at", "updated_at")

    def validate(self, attrs):
        start_time = attrs.get("start_time", getattr(self.instance, "start_time", None))
        end_time = attrs.get("end_time", getattr(self.instance, "end_time", None))
        if start_time and end_time and start_time == end_time:
            raise serializers.ValidationError({"end_time": "Shift start and end time cannot be identical."})
        return attrs


class EmployeeSerializer(serializers.ModelSerializer):
    user_id = serializers.IntegerField(source="user.id", read_only=True)
    email = serializers.EmailField(source="user.email")
    first_name = serializers.CharField(source="user.first_name")
    last_name = serializers.CharField(source="user.last_name")
    role = serializers.ChoiceField(source="user.role", choices=User.Role.choices, required=False)
    shift_template = serializers.PrimaryKeyRelatedField(
        queryset=ShiftTemplate.objects.filter(is_active=True),
        required=False,
        allow_null=True,
    )
    password = serializers.CharField(write_only=True, required=False, allow_blank=False)
    full_name = serializers.CharField(source="user.full_name", read_only=True)
    department_name = serializers.CharField(source="department.name", read_only=True)
    manager_name = serializers.CharField(source="manager.user.full_name", read_only=True)
    secondary_manager_name = serializers.CharField(source="secondary_manager.user.full_name", read_only=True)
    shift_template_name = serializers.CharField(source="shift_template.name", read_only=True)
    monthly_gross_salary = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    estimated_monthly_net_salary = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    can_view_compensation = serializers.SerializerMethodField()

    class Meta:
        model = Employee
        fields = (
            "id",
            "user_id",
            "employee_id",
            "email",
            "first_name",
            "last_name",
            "full_name",
            "role",
            "password",
            "department",
            "department_name",
            "manager",
            "manager_name",
            "secondary_manager",
            "secondary_manager_name",
            "designation",
            "phone_number",
            "date_of_birth",
            "hire_date",
            "employment_type",
            "department_role",
            "shift_template",
            "shift_template_name",
            "shift_name",
            "shift_start_time",
            "shift_end_time",
            "ctc_per_annum",
            "monthly_fixed_deductions",
            "monthly_gross_salary",
            "estimated_monthly_net_salary",
            "can_view_compensation",
            "address",
            "emergency_contact_name",
            "emergency_contact_phone",
            "is_active",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "created_at",
            "updated_at",
            "full_name",
            "department_name",
            "manager_name",
            "secondary_manager_name",
            "shift_template_name",
            "monthly_gross_salary",
            "estimated_monthly_net_salary",
            "can_view_compensation",
        )

    def _validate_reporting_manager(self, reporting_manager, field_name):
        if not reporting_manager:
            return

        if (
            reporting_manager.user.role not in {User.Role.MANAGER, User.Role.HR, User.Role.ADMIN}
            and reporting_manager.department_role != Employee.DepartmentRole.TEAM_LEAD
        ):
            raise serializers.ValidationError(
                {field_name: "Select a manager, HR/Admin user, or a team lead as the reporting manager."}
            )

    def _get_requested_role(self, attrs):
        user_data = attrs.get("user", {})
        if "role" in user_data:
            return user_data["role"]
        if self.instance:
            return self.instance.user.role
        return User.Role.EMPLOYEE

    def _validate_role_access(self, requested_role):
        request = self.context.get("request")
        actor = getattr(request, "user", None)
        if not actor or not getattr(actor, "is_authenticated", False):
            return

        if actor.role != User.Role.HR:
            return

        if self.instance and self.instance.user.role == User.Role.ADMIN:
            raise serializers.ValidationError({"role": "HR users cannot modify Admin employee records."})

        if requested_role == User.Role.ADMIN:
            raise serializers.ValidationError({"role": "HR users cannot assign the Admin role."})

    def validate_email(self, value):
        queryset = User.objects.filter(email__iexact=value)
        if self.instance:
            queryset = queryset.exclude(pk=self.instance.user_id)
        if queryset.exists():
            raise serializers.ValidationError("A user with this email already exists.")
        return value

    def validate(self, attrs):
        manager = attrs.get("manager", getattr(self.instance, "manager", None))
        secondary_manager = attrs.get("secondary_manager", getattr(self.instance, "secondary_manager", None))
        requested_role = self._get_requested_role(attrs)
        shift_template = attrs.get("shift_template", getattr(self.instance, "shift_template", None))
        shift_start_time = attrs.get("shift_start_time", getattr(self.instance, "shift_start_time", None))
        shift_end_time = attrs.get("shift_end_time", getattr(self.instance, "shift_end_time", None))
        self._validate_role_access(requested_role)
        if shift_template:
            attrs["shift_name"] = shift_template.name
            attrs["shift_start_time"] = shift_template.start_time
            attrs["shift_end_time"] = shift_template.end_time
            shift_start_time = shift_template.start_time
            shift_end_time = shift_template.end_time
        if "manager" in attrs:
            self._validate_reporting_manager(attrs.get("manager"), "manager")
        if "secondary_manager" in attrs:
            self._validate_reporting_manager(attrs.get("secondary_manager"), "secondary_manager")
        if self.instance and manager and manager.pk == self.instance.pk:
            raise serializers.ValidationError({"manager": "An employee cannot report to themselves."})
        if self.instance and secondary_manager and secondary_manager.pk == self.instance.pk:
            raise serializers.ValidationError({"secondary_manager": "An employee cannot be their own second reporting manager."})
        if manager and secondary_manager and manager.pk == secondary_manager.pk:
            raise serializers.ValidationError({"secondary_manager": "Second reporting manager must differ from primary manager."})
        if shift_start_time and shift_end_time and shift_start_time == shift_end_time:
            raise serializers.ValidationError({"shift_end_time": "Shift start and end time cannot be identical."})
        return attrs

    def get_can_view_compensation(self, obj):
        request = self.context.get("request")
        user = getattr(request, "user", None)
        if not user or not getattr(user, "is_authenticated", False):
            return False
        if user.role in {User.Role.MANAGER, User.Role.HR, User.Role.ACCOUNTS, User.Role.ADMIN}:
            return True
        return obj.user_id == user.pk

    def to_representation(self, instance):
        data = super().to_representation(instance)
        if not self.get_can_view_compensation(instance):
            data["ctc_per_annum"] = None
            data["monthly_fixed_deductions"] = None
            data["monthly_gross_salary"] = None
            data["estimated_monthly_net_salary"] = None
        return data
