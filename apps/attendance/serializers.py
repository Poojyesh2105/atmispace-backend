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
    check_in_distance_meters = serializers.SerializerMethodField()
    work_location = serializers.SerializerMethodField()

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
            "check_in_latitude",
            "check_in_longitude",
            "check_in_accuracy_meters",
            "check_in_distance_meters",
            "work_location",
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
            "check_in_latitude",
            "check_in_longitude",
            "check_in_accuracy_meters",
            "check_in_distance_meters",
            "work_location",
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

    def get_check_in_distance_meters(self, obj):
        from apps.attendance.services.attendance_service import AttendanceService

        distance = AttendanceService.get_check_in_distance_meters(obj)
        return round(distance, 1) if distance is not None else None

    def get_work_location(self, obj):
        from apps.attendance.services.attendance_service import AttendanceService

        return AttendanceService.get_work_location(obj)


class AttendanceActionSerializer(serializers.Serializer):
    notes = serializers.CharField(required=False, allow_blank=True)
    status = serializers.ChoiceField(choices=Attendance.Status.choices, required=False)
    check_in_latitude = serializers.DecimalField(max_digits=9, decimal_places=6, required=False, allow_null=True)
    check_in_longitude = serializers.DecimalField(max_digits=9, decimal_places=6, required=False, allow_null=True)
    check_in_accuracy_meters = serializers.DecimalField(max_digits=8, decimal_places=2, required=False, allow_null=True)

    def validate(self, attrs):
        latitude = attrs.get("check_in_latitude")
        longitude = attrs.get("check_in_longitude")
        if (latitude is None) != (longitude is None):
            raise serializers.ValidationError({"location": "Latitude and longitude must be supplied together."})
        if latitude is not None and not (-90 <= latitude <= 90):
            raise serializers.ValidationError({"check_in_latitude": "Latitude must be between -90 and 90."})
        if longitude is not None and not (-180 <= longitude <= 180):
            raise serializers.ValidationError({"check_in_longitude": "Longitude must be between -180 and 180."})
        accuracy = attrs.get("check_in_accuracy_meters")
        if accuracy is not None and accuracy < 0:
            raise serializers.ValidationError({"check_in_accuracy_meters": "Accuracy cannot be negative."})
        return attrs


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
