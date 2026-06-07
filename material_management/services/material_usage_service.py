"""
材料领用业务服务层
职责：处理材料领用单的创建、审核、领用等核心业务逻辑
原则：业务逻辑下沉，事务控制在此层，处理库存流转和状态变更
"""
from django.db import transaction
from django.utils import timezone
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError

from ..models import MaterialUsage, MaterialStock
from ..utils import generate_usage_no


def create_material_usage(data: dict, user: User) -> MaterialUsage:
    data['usage_no'] = generate_usage_no()
    data['created_by'] = user
    data['status'] = 'pending'
    return MaterialUsage.objects.create(**data)


def approve_material_usage(usage: MaterialUsage, user: User) -> MaterialUsage:
    if usage.status != 'pending':
        raise ValidationError('只有待审核的领用单才能通过')
    usage.status = 'approved'
    usage.approved_by = user
    usage.approved_at = timezone.now()
    usage.save()
    return usage


def reject_material_usage(
    usage: MaterialUsage,
    user: User,
    remark: str | None = None
) -> MaterialUsage:
    if usage.status != 'pending':
        raise ValidationError('只有待审核的领用单才能拒绝')
    usage.status = 'rejected'
    usage.approved_by = user
    usage.approved_at = timezone.now()
    if remark is not None:
        usage.remark = remark
    usage.save()
    return usage


def use_material(usage: MaterialUsage, user: User) -> MaterialUsage:
    if usage.status != 'approved':
        raise ValidationError('只有已通过的领用单才能领用')

    with transaction.atomic():
        stock = MaterialStock.objects.filter(
            zone=usage.zone,
            material_category=usage.material_category,
            material_batch=usage.material_batch,
            floor=usage.floor
        ).first()
        if not stock or stock.quantity < usage.quantity:
            raise ValidationError('库存不足')

        stock.quantity -= usage.quantity
        stock.save()

        usage.status = 'used'
        usage.used_by = user
        usage.used_at = timezone.now()
        usage.save()

    return usage
