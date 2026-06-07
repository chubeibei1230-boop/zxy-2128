from django.contrib import admin
from .models import (
    UserProfile, Project, MaterialCategory, Zone, Floor,
    ResponsibilityGroup, MaterialBatch, MaterialStock,
    MaterialTransfer, MaterialUsage, ExceptionRecord,
    InventoryCheck, InventoryCheckItem, MaterialWarning, WarningProcessLog
)


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'role', 'phone', 'created_at']
    list_filter = ['role']
    search_fields = ['user__username', 'user__email', 'phone']


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ['name', 'address', 'start_date', 'end_date', 'is_active', 'created_at']
    list_filter = ['is_active']
    search_fields = ['name', 'address']


@admin.register(MaterialCategory)
class MaterialCategoryAdmin(admin.ModelAdmin):
    list_display = ['code', 'name', 'parent', 'unit', 'is_active']
    list_filter = ['is_active']
    search_fields = ['code', 'name']


@admin.register(Zone)
class ZoneAdmin(admin.ModelAdmin):
    list_display = ['code', 'name', 'project', 'parent', 'level', 'is_active']
    list_filter = ['project', 'level', 'is_active']
    search_fields = ['code', 'name']


@admin.register(Floor)
class FloorAdmin(admin.ModelAdmin):
    list_display = ['code', 'name', 'project', 'sort_order', 'is_active']
    list_filter = ['project', 'is_active']
    search_fields = ['code', 'name']


@admin.register(ResponsibilityGroup)
class ResponsibilityGroupAdmin(admin.ModelAdmin):
    list_display = ['name', 'project', 'leader', 'is_active']
    list_filter = ['project', 'is_active']
    search_fields = ['name']


@admin.register(MaterialBatch)
class MaterialBatchAdmin(admin.ModelAdmin):
    list_display = ['batch_no', 'project', 'material_category', 'total_quantity', 'received_quantity', 'status', 'created_at']
    list_filter = ['project', 'status', 'material_category']
    search_fields = ['batch_no', 'supplier']


@admin.register(MaterialStock)
class MaterialStockAdmin(admin.ModelAdmin):
    list_display = ['zone', 'material_category', 'material_batch', 'floor', 'quantity', 'updated_at']
    list_filter = ['zone', 'material_category', 'floor']
    search_fields = ['material_batch__batch_no']


@admin.register(MaterialTransfer)
class MaterialTransferAdmin(admin.ModelAdmin):
    list_display = ['transfer_no', 'from_zone', 'to_zone', 'material_category', 'quantity', 'status', 'created_at']
    list_filter = ['status', 'from_zone', 'to_zone', 'material_category']
    search_fields = ['transfer_no']


@admin.register(MaterialUsage)
class MaterialUsageAdmin(admin.ModelAdmin):
    list_display = ['usage_no', 'project', 'zone', 'material_category', 'quantity', 'status', 'created_at']
    list_filter = ['project', 'status', 'zone', 'material_category']
    search_fields = ['usage_no']


@admin.register(ExceptionRecord)
class ExceptionRecordAdmin(admin.ModelAdmin):
    list_display = ['exception_no', 'project', 'zone', 'material_category', 'exception_type', 'status', 'created_at']
    list_filter = ['project', 'exception_type', 'status', 'zone']
    search_fields = ['exception_no', 'description']


@admin.register(InventoryCheck)
class InventoryCheckAdmin(admin.ModelAdmin):
    list_display = ['check_no', 'project', 'zone', 'check_date', 'status', 'created_at']
    list_filter = ['project', 'status', 'zone']
    search_fields = ['check_no']


@admin.register(MaterialWarning)
class MaterialWarningAdmin(admin.ModelAdmin):
    list_display = ['warning_no', 'project', 'zone', 'material_category', 'warning_type', 'priority', 'status', 'created_at']
    list_filter = ['project', 'warning_type', 'status', 'priority', 'zone']
    search_fields = ['warning_no', 'description']


@admin.register(WarningProcessLog)
class WarningProcessLogAdmin(admin.ModelAdmin):
    list_display = ['warning', 'action', 'old_status', 'new_status', 'created_by', 'created_at']
    list_filter = ['action', 'old_status', 'new_status']
    search_fields = ['warning__warning_no', 'action_detail']
