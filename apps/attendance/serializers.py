from rest_framework import serializers

from apps.attendance.models import Attendance, AttendanceRegularization


class AttendanceSerializer(serializers.ModelSerializer):
    employee_name = serializers.CharField(source="employee.user.full_name", read_only=True)
    employee_code = serializers.CharField(source="employee.employee_id", read_only=True)
    total_work_hours = serializers.SerializerMethodField()
    active_work_minutes = serializers.SerializerMethodField()
    active_work_hours = serializers.SerializerMethodField()
    expected_shift_minutes = serializers.SerializerMethodField()
    shift_name = serializers.CharField(source="employee.shift_name", read_only=True)
    current_session_check_in = serializers.DateTimeField(read_only=True)
    current_session_break_minutes = serializers.IntegerField(read_only=True)
    break_started_at = serializers.DateTimeField(read_only=True)
    is_on_break = serializers.SerializerMethodField()
    is_checked_in = serializers.SerializerMethodField()

    class Meta:
        model = Attendance
        fields = (
            "id",
            "employee",
            "employee_code",
            "employee_name",
            "attendance_date",
            "check_in",
            "check_out",
            "current_session_check_in",
            "break_started_at",
            "break_minutes",
            "current_session_break_minutes",
            "is_checked_in",
            "is_on_break",
            "status",
            "notes",
            "total_work_minutes",
            "total_work_hours",
            "active_work_minutes",
            "active_work_hours",
            "shift_name",
            "expected_shift_minutes",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "employee",
            "employee_code",
            "employee_name",
            "attendance_date",
            "check_in",
            "check_out",
            "current_session_check_in",
            "break_started_at",
            "break_minutes",
            "current_session_break_minutes",
            "is_checked_in",
            "is_on_break",
            "total_work_minutes",
            "total_work_hours",
            "active_work_minutes",
            "active_work_hours",
            "shift_name",
            "expected_shift_minutes",
            "created_at",
            "updated_at",
        )

    def get_total_work_hours(self, obj):
        return round(self.get_active_work_minutes(obj) / 60, 2)

    def get_active_work_minutes(self, obj):
        from apps.attendance.services.attendance_service import AttendanceService

        return AttendanceService.calculate_work_minutes(obj)

    def get_active_work_hours(self, obj):
        return round(self.get_active_work_minutes(obj) / 60, 2)

    def get_expected_shift_minutes(self, obj):
        from apps.attendance.services.attendance_service import AttendanceService

        return AttendanceService.get_expected_shift_minutes(obj.employee)

    def get_is_on_break(self, obj):
        return bool(obj.break_started_at and obj.current_session_check_in)

    def get_is_checked_in(self, obj):
        return bool(obj.current_session_check_in)


class AttendanceActionSerializer(serializers.Serializer):
    notes = serializers.CharField(required=False, allow_blank=True)
    status = serializers.ChoiceField(choices=Attendance.Status.choices, required=False)


class AttendanceRegularizationSerializer(serializers.ModelSerializer):
    employee_name = serializers.CharField(source="employee.user.full_name", read_only=True)
    employee_code = serializers.CharField(source="employee.employee_id", read_only=True)
    approver_name = serializers.CharField(source="approver.full_name", read_only=True)

    class Meta:
        model = AttendanceRegularization
        fields = (
            "id",
            "employee",
            "employee_name",
            "employee_code",
            "date",
            "requested_check_in",
            "requested_check_out",
            "reason",
            "status",
            "approver",
            "approver_name",
            "approver_note",
            "reviewed_at",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "employee",
            "employee_name",
            "employee_code",
            "status",
            "approver",
            "approver_name",
            "approver_note",
            "reviewed_at",
            "created_at",
            "updated_at",
        )


class AttendanceRegularizationApplySerializer(serializers.Serializer):
    date = serializers.DateField()
    requested_check_in = serializers.DateTimeField()
    requested_check_out = serializers.DateTimeField()
    reason = serializers.CharField()

    def validate(self, attrs):
        if attrs["requested_check_in"].date() != attrs["date"]:
            raise serializers.ValidationError({"requested_check_in": "Requested check-in must start on the selected date."})
        if attrs["requested_check_out"] <= attrs["requested_check_in"]:
            raise serializers.ValidationError({"requested_check_out": "Requested check-out must be after check-in."})
        return attrs


class AttendanceRegularizationDecisionSerializer(serializers.Serializer):
    approver_note = serializers.CharField(required=False, allow_blank=True)
