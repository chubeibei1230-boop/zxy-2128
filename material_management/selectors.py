"""
查询统计层
职责：封装所有数据查询和统计聚合逻辑
原则：只读操作，不修改数据库，返回 QuerySet 或统计结果
"""
from django.db.models import QuerySet, Sum
from django.contrib.auth.models import User

from .models import (
    UserProfile, Project, MaterialCategory, Zone, Floor,
    ResponsibilityGroup, MaterialBatch, MaterialStock,
    MaterialTransfer, MaterialUsage, ExceptionRecord
)
from .utils import parse_bool_param


def get_user_profile_queryset(request, role: str | None = None) -> QuerySet:
    queryset = UserProfile.objects.select_related('user').all()
    if role:
        queryset = queryset.filter(role=role)
    return queryset


def get_project_queryset(request, is_active: str | None = None) -> QuerySet:
    queryset = Project.objects.all()
    active_flag = parse_bool_param(is_active)
    if active_flag is not None:
        queryset = queryset.filter(is_active=active_flag)
    return queryset


def get_material_category_queryset(
    request,
    parent: str | None = None,
    is_active: str | None = None
) -> QuerySet:
    queryset = MaterialCategory.objects.all()
    if parent is not None:
        if parent == 'null':
            queryset = queryset.filter(parent__isnull=True)
        else:
            queryset = queryset.filter(parent_id=parent)
    active_flag = parse_bool_param(is_active)
    if active_flag is not None:
        queryset = queryset.filter(is_active=active_flag)
    return queryset


def get_material_category_roots() -> QuerySet:
    return MaterialCategory.objects.filter(parent__isnull=True, is_active=True)


def get_zone_queryset(
    request,
    project: str | None = None,
    parent: str | None = None,
    is_active: str | None = None
) -> QuerySet:
    queryset = Zone.objects.select_related('project', 'parent').all()
    if project:
        queryset = queryset.filter(project_id=project)
    if parent is not None:
        if parent == 'null':
            queryset = queryset.filter(parent__isnull=True)
        else:
            queryset = queryset.filter(parent_id=parent)
    active_flag = parse_bool_param(is_active)
    if active_flag is not None:
        queryset = queryset.filter(is_active=active_flag)
    return queryset


def get_zone_roots(project_id: int) -> QuerySet:
    return Zone.objects.filter(project_id=project_id, parent__isnull=True, is_active=True)


def get_zone_stocks(zone: Zone) -> QuerySet:
    all_zone_ids = zone.get_all_child_ids()
    return MaterialStock.objects.filter(zone_id__in=all_zone_ids).select_related(
        'zone', 'material_category', 'material_batch', 'floor'
    )


def get_floor_queryset(
    request,
    project: str | None = None,
    is_active: str | None = None
) -> QuerySet:
    queryset = Floor.objects.all()
    if project:
        queryset = queryset.filter(project_id=project)
    active_flag = parse_bool_param(is_active)
    if active_flag is not None:
        queryset = queryset.filter(is_active=active_flag)
    return queryset


def get_responsibility_group_queryset(request, project: str | None = None) -> QuerySet:
    queryset = ResponsibilityGroup.objects.select_related(
        'project', 'leader'
    ).prefetch_related('members').all()
    if project:
        queryset = queryset.filter(project_id=project)
    return queryset


def get_material_batch_queryset(
    request,
    project: str | None = None,
    material_category: str | None = None,
    status: str | None = None
) -> QuerySet:
    queryset = MaterialBatch.objects.select_related(
        'project', 'material_category', 'created_by'
    ).all()
    if project:
        queryset = queryset.filter(project_id=project)
    if material_category:
        queryset = queryset.filter(material_category_id=material_category)
    if status:
        queryset = queryset.filter(status=status)
    return queryset


def get_material_stock_queryset(
    request,
    zone: str | None = None,
    material_category: str | None = None,
    project: str | None = None
) -> QuerySet:
    queryset = MaterialStock.objects.select_related(
        'zone', 'material_category', 'material_batch', 'floor'
    ).all()
    if zone:
        try:
            zone_obj = Zone.objects.get(id=zone)
            all_zone_ids = zone_obj.get_all_child_ids()
            queryset = queryset.filter(zone_id__in=all_zone_ids)
        except Zone.DoesNotExist:
            queryset = queryset.none()
    if material_category:
        queryset = queryset.filter(material_category_id=material_category)
    if project:
        queryset = queryset.filter(zone__project_id=project)
    return queryset


def get_material_transfer_queryset(
    request,
    from_zone: str | None = None,
    to_zone: str | None = None,
    status: str | None = None
) -> QuerySet:
    queryset = MaterialTransfer.objects.select_related(
        'from_zone', 'to_zone', 'from_floor', 'to_floor',
        'material_category', 'material_batch', 'created_by', 'confirmed_by'
    ).all()
    if from_zone:
        queryset = queryset.filter(from_zone_id=from_zone)
    if to_zone:
        queryset = queryset.filter(to_zone_id=to_zone)
    if status:
        queryset = queryset.filter(status=status)
    return queryset


def get_material_usage_queryset(
    request,
    project: str | None = None,
    zone: str | None = None,
    status: str | None = None
) -> QuerySet:
    queryset = MaterialUsage.objects.select_related(
        'project', 'zone', 'floor', 'material_category',
        'material_batch', 'responsibility_group',
        'created_by', 'approved_by', 'used_by'
    ).all()
    if project:
        queryset = queryset.filter(project_id=project)
    if zone:
        queryset = queryset.filter(zone_id=zone)
    if status:
        queryset = queryset.filter(status=status)
    return queryset


def get_exception_record_queryset(
    request,
    project: str | None = None,
    zone: str | None = None,
    status: str | None = None,
    exception_type: str | None = None
) -> QuerySet:
    queryset = ExceptionRecord.objects.select_related(
        'project', 'zone', 'floor', 'material_category',
        'material_batch', 'reported_by', 'audited_by', 'handled_by'
    ).all()
    if project:
        queryset = queryset.filter(project_id=project)
    if zone:
        try:
            zone_obj = Zone.objects.get(id=zone)
            all_zone_ids = zone_obj.get_all_child_ids()
            queryset = queryset.filter(zone_id__in=all_zone_ids)
        except Zone.DoesNotExist:
            queryset = queryset.none()
    if status:
        queryset = queryset.filter(status=status)
    if exception_type:
        queryset = queryset.filter(exception_type=exception_type)
    return queryset


def get_dashboard_stats(project_id: str | None = None) -> dict:
    query_params = {}
    if project_id:
        query_params['project_id'] = project_id

    total_projects = Project.objects.filter(is_active=True).count()
    total_zones = Zone.objects.filter(**query_params, is_active=True).count()

    stock_params = {k.replace('project_id', 'zone__project_id'): v for k, v in query_params.items()}
    total_stock = MaterialStock.objects.filter(**stock_params).aggregate(
        total=Sum('quantity')
    )['total'] or 0

    pending_usage = MaterialUsage.objects.filter(**query_params, status='pending').count()
    pending_exception = ExceptionRecord.objects.filter(**query_params, status='pending').count()

    transfer_params = {k.replace('project_id', 'from_zone__project_id'): v for k, v in query_params.items()}
    pending_transfer = MaterialTransfer.objects.filter(**transfer_params, status='pending').count()

    return {
        'total_projects': total_projects,
        'total_zones': total_zones,
        'total_stock': total_stock,
        'pending_usage': pending_usage,
        'pending_exception': pending_exception,
        'pending_transfer': pending_transfer
    }


def get_or_create_current_user_profile(user: User) -> UserProfile:
    profile, _ = UserProfile.objects.get_or_create(user=user, defaults={'role': 'operator'})
    return profile
