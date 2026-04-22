from rest_framework import serializers

from apps.attendance.models import Attendance, AttendanceRegularization, BiometricAttendanceEvent, BiometricDevice


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
            "break_count",
            "current_session_break_minutes",
            "is_checked_in",
            "is_on_break",
            "status",
            "source",
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
            "break_count",
            "current_session_break_minutes",
            "is_checked_in",
            "is_on_break",
            "source",
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


class BiometricDeviceSerializer(serializers.ModelSerializer):
    secret_key = serializers.CharField(write_only=True, required=False, allow_blank=False)

    class Meta:
        model = BiometricDevice
        fields = (
            "id",
            "name",
            "device_code",
            "secret_key",
            "location_name",
            "is_active",
            "last_seen_at",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "last_seen_at", "created_at", "updated_at")

    def validate(self, attrs):
        if not self.instance and not attrs.get("secret_key"):
            raise serializers.ValidationError({"secret_key": "Secret key is required when creating a biometric device."})
        return attrs


class BiometricAttendanceEventSerializer(serializers.ModelSerializer):
    device_name = serializers.CharField(source="device.name", read_only=True)
    device_code = serializers.CharField(source="device.device_code", read_only=True)
    employee_name = serializers.SerializerMethodField()
    employee_code = serializers.SerializerMethodField()

    class Meta:
        model = BiometricAttendanceEvent
        fields = (
            "id",
            "device",
            "device_name",
            "device_code",
            "employee",
            "employee_name",
            "employee_code",
            "attendance",
            "device_user_id",
            "external_event_id",
            "event_type",
            "occurred_at",
            "status",
            "message",
            "processed_at",
            "raw_payload",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields

    def get_employee_name(self, obj):
        return obj.employee.user.full_name if obj.employee_id and obj.employee else None

    def get_employee_code(self, obj):
        return obj.employee.employee_id if obj.employee_id and obj.employee else None


class BiometricAttendanceIngestSerializer(serializers.Serializer):
    device_code = serializers.CharField()
    secret_key = serializers.CharField(write_only=True)
    biometric_id = serializers.CharField()
    event_type = serializers.CharField()
    occurred_at = serializers.DateTimeField()
    external_event_id = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    raw_payload = serializers.JSONField(required=False, default=dict)

    def validate_biometric_id(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Biometric ID is required.")
        return value

    def validate_event_type(self, value):
        from apps.attendance.services.biometric_service import BiometricAttendanceService

        return BiometricAttendanceService.normalize_event_type(value)

    def validate_external_event_id(self, value):
        if not value:
            return None
        return value.strip() or None


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
