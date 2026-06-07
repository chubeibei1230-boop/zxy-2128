from rest_framework import serializers
from django.contrib.auth.models import User
from .models import (
    UserProfile, Project, MaterialCategory, Zone, Floor,
    ResponsibilityGroup, MaterialBatch, MaterialStock,
    MaterialTransfer, MaterialUsage, ExceptionRecord
)


class UserProfileSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='user.username', read_only=True)
    email = serializers.EmailField(source='user.email', read_only=True)
    first_name = serializers.CharField(source='user.first_name', required=False)
    last_name = serializers.CharField(source='user.last_name', required=False)

    class Meta:
        model = UserProfile
        fields = ['id', 'username', 'email', 'first_name', 'last_name', 'role', 'phone', 'created_at']
        read_only_fields = ['id', 'created_at']


class UserCreateSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=150)
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, min_length=6)
    first_name = serializers.CharField(max_length=150, required=False, allow_blank=True)
    last_name = serializers.CharField(max_length=150, required=False, allow_blank=True)
    role = serializers.ChoiceField(choices=UserProfile.ROLE_CHOICES)
    phone = serializers.CharField(max_length=20, required=False, allow_blank=True)

    def validate_username(self, value):
        if User.objects.filter(username=value).exists():
            raise serializers.ValidationError('用户名已存在')
        return value

    def create(self, validated_data):
        user = User.objects.create_user(
            username=validated_data['username'],
            email=validated_data['email'],
            password=validated_data['password'],
            first_name=validated_data.get('first_name', ''),
            last_name=validated_data.get('last_name', '')
        )
        profile = UserProfile.objects.create(
            user=user,
            role=validated_data['role'],
            phone=validated_data.get('phone', '')
        )
        return profile


class ProjectSerializer(serializers.ModelSerializer):
    class Meta:
        model = Project
        fields = '__all__'
        read_only_fields = ['id', 'created_at', 'updated_at']


class MaterialCategorySerializer(serializers.ModelSerializer):
    parent_name = serializers.CharField(source='parent.name', read_only=True, allow_null=True)

    class Meta:
        model = MaterialCategory
        fields = '__all__'
        read_only_fields = ['id', 'created_at']


class MaterialCategoryTreeSerializer(serializers.ModelSerializer):
    children = serializers.SerializerMethodField()

    class Meta:
        model = MaterialCategory
        fields = ['id', 'name', 'code', 'parent', 'unit', 'description', 'is_active', 'children']

    def get_children(self, obj):
        children = obj.children.filter(is_active=True)
        return MaterialCategoryTreeSerializer(children, many=True).data


class ZoneSerializer(serializers.ModelSerializer):
    parent_name = serializers.CharField(source='parent.name', read_only=True, allow_null=True)
    project_name = serializers.CharField(source='project.name', read_only=True)

    class Meta:
        model = Zone
        fields = '__all__'
        read_only_fields = ['id', 'created_at', 'updated_at', 'level']


class ZoneTreeSerializer(serializers.ModelSerializer):
    children = serializers.SerializerMethodField()
    statistics = serializers.SerializerMethodField()

    class Meta:
        model = Zone
        fields = ['id', 'name', 'code', 'project', 'parent', 'level', 'sort_order',
                  'description', 'is_active', 'children', 'statistics']

    def get_children(self, obj):
        children = obj.children.filter(is_active=True)
        return ZoneTreeSerializer(children, many=True).data

    def get_statistics(self, obj):
        return obj.get_statistics()


class ZoneDetailSerializer(serializers.ModelSerializer):
    statistics = serializers.SerializerMethodField()
    children = serializers.SerializerMethodField()
    project_name = serializers.CharField(source='project.name', read_only=True)
    parent_name = serializers.CharField(source='parent.name', read_only=True, allow_null=True)

    class Meta:
        model = Zone
        fields = '__all__'
        read_only_fields = ['id', 'created_at', 'updated_at']

    def get_statistics(self, obj):
        return obj.get_statistics()

    def get_children(self, obj):
        children = obj.children.filter(is_active=True)
        return ZoneTreeSerializer(children, many=True).data


class FloorSerializer(serializers.ModelSerializer):
    project_name = serializers.CharField(source='project.name', read_only=True)

    class Meta:
        model = Floor
        fields = '__all__'
        read_only_fields = ['id', 'created_at']


class ResponsibilityGroupSerializer(serializers.ModelSerializer):
    project_name = serializers.CharField(source='project.name', read_only=True)
    leader_name = serializers.CharField(source='leader.username', read_only=True, allow_null=True)
    member_names = serializers.SerializerMethodField()

    class Meta:
        model = ResponsibilityGroup
        fields = '__all__'
        read_only_fields = ['id', 'created_at']

    def get_member_names(self, obj):
        return [user.username for user in obj.members.all()]


class MaterialBatchSerializer(serializers.ModelSerializer):
    project_name = serializers.CharField(source='project.name', read_only=True)
    material_category_name = serializers.CharField(source='material_category.name', read_only=True)
    material_category_code = serializers.CharField(source='material_category.code', read_only=True)
    created_by_name = serializers.CharField(source='created_by.username', read_only=True, allow_null=True)

    class Meta:
        model = MaterialBatch
        fields = '__all__'
        read_only_fields = ['id', 'created_at', 'updated_at', 'received_quantity', 'status']


class MaterialBatchInboundSerializer(serializers.Serializer):
    zone = serializers.IntegerField()
    floor = serializers.IntegerField(required=False, allow_null=True)
    quantity = serializers.DecimalField(max_digits=15, decimal_places=2)


class MaterialStockSerializer(serializers.ModelSerializer):
    zone_name = serializers.CharField(source='zone.name', read_only=True)
    zone_code = serializers.CharField(source='zone.code', read_only=True)
    floor_name = serializers.CharField(source='floor.name', read_only=True, allow_null=True)
    material_category_name = serializers.CharField(source='material_category.name', read_only=True)
    material_category_code = serializers.CharField(source='material_category.code', read_only=True)
    material_batch_no = serializers.CharField(source='material_batch.batch_no', read_only=True)

    class Meta:
        model = MaterialStock
        fields = '__all__'
        read_only_fields = ['id', 'created_at', 'updated_at']


class MaterialTransferSerializer(serializers.ModelSerializer):
    from_zone_name = serializers.CharField(source='from_zone.name', read_only=True)
    to_zone_name = serializers.CharField(source='to_zone.name', read_only=True)
    from_floor_name = serializers.CharField(source='from_floor.name', read_only=True, allow_null=True)
    to_floor_name = serializers.CharField(source='to_floor.name', read_only=True, allow_null=True)
    material_category_name = serializers.CharField(source='material_category.name', read_only=True)
    material_batch_no = serializers.CharField(source='material_batch.batch_no', read_only=True)
    created_by_name = serializers.CharField(source='created_by.username', read_only=True, allow_null=True)
    confirmed_by_name = serializers.CharField(source='confirmed_by.username', read_only=True, allow_null=True)

    class Meta:
        model = MaterialTransfer
        fields = '__all__'
        read_only_fields = ['id', 'transfer_no', 'created_at', 'confirmed_at', 'status']


class MaterialUsageSerializer(serializers.ModelSerializer):
    project_name = serializers.CharField(source='project.name', read_only=True)
    zone_name = serializers.CharField(source='zone.name', read_only=True)
    floor_name = serializers.CharField(source='floor.name', read_only=True, allow_null=True)
    material_category_name = serializers.CharField(source='material_category.name', read_only=True)
    material_batch_no = serializers.CharField(source='material_batch.batch_no', read_only=True)
    responsibility_group_name = serializers.CharField(source='responsibility_group.name', read_only=True, allow_null=True)
    created_by_name = serializers.CharField(source='created_by.username', read_only=True, allow_null=True)
    approved_by_name = serializers.CharField(source='approved_by.username', read_only=True, allow_null=True)
    used_by_name = serializers.CharField(source='used_by.username', read_only=True, allow_null=True)

    class Meta:
        model = MaterialUsage
        fields = '__all__'
        read_only_fields = ['id', 'usage_no', 'created_at', 'approved_at', 'used_at', 'status']


class ExceptionRecordSerializer(serializers.ModelSerializer):
    project_name = serializers.CharField(source='project.name', read_only=True)
    zone_name = serializers.CharField(source='zone.name', read_only=True)
    floor_name = serializers.CharField(source='floor.name', read_only=True, allow_null=True)
    material_category_name = serializers.CharField(source='material_category.name', read_only=True)
    material_batch_no = serializers.CharField(source='material_batch.batch_no', read_only=True, allow_null=True)
    reported_by_name = serializers.CharField(source='reported_by.username', read_only=True, allow_null=True)
    audited_by_name = serializers.CharField(source='audited_by.username', read_only=True, allow_null=True)
    handled_by_name = serializers.CharField(source='handled_by.username', read_only=True, allow_null=True)

    class Meta:
        model = ExceptionRecord
        fields = '__all__'
        read_only_fields = ['id', 'exception_no', 'created_at', 'audited_at', 'resolved_at']


class AuditExceptionSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=['processing', 'resolved', 'closed'])
    handling_suggestion = serializers.CharField(required=False, allow_blank=True)
    handling_result = serializers.CharField(required=False, allow_blank=True)


class ZoneMergeSerializer(serializers.Serializer):
    source_zone_ids = serializers.ListField(child=serializers.IntegerField())
    target_zone_id = serializers.IntegerField()
