"""
盘点业务服务层
职责：处理盘点任务的创建、明细维护、提交、审核、库存更新等核心业务逻辑
原则：业务逻辑下沉，处理状态流转和人员关联
"""
from django.utils import timezone
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import transaction

from ..models import (
    InventoryCheck, InventoryCheckItem,
    Zone, Floor, MaterialCategory, MaterialBatch,
    MaterialStock, Project
)
from ..utils import generate_inventory_check_no


def create_inventory_check(data: dict, user: User) -> InventoryCheck:
    data['check_no'] = generate_inventory_check_no()
    data['created_by'] = user
    data['status'] = 'draft'
    return InventoryCheck.objects.create(**data)


def update_inventory_check_items(
    inventory_check: InventoryCheck,
    items_data: list[dict]
) -> InventoryCheck:
    if inventory_check.status not in ['draft', 'rejected']:
        raise ValidationError('只能修改草稿或审核拒绝状态的盘点单')

    inventory_check.items.all().delete()

    for item_data in items_data:
        InventoryCheckItem.objects.create(
            inventory_check=inventory_check,
            material_category_id=item_data['material_category'],
            material_batch_id=item_data['material_batch'],
            book_quantity=item_data['book_quantity'],
            actual_quantity=item_data['actual_quantity'],
            remark=item_data.get('remark', '')
        )

    return inventory_check


def submit_inventory_check(
    inventory_check: InventoryCheck,
    user: User,
    handling_opinion: str | None = None
) -> InventoryCheck:
    if inventory_check.status not in ['draft', 'rejected']:
        raise ValidationError('只能提交草稿或审核拒绝状态的盘点单')

    if not inventory_check.items.exists():
        raise ValidationError('盘点明细不能为空')

    inventory_check.status = 'submitted'
    if handling_opinion is not None:
        inventory_check.handling_opinion = handling_opinion
    inventory_check.checked_by = user
    inventory_check.checked_at = timezone.now()
    inventory_check.save()
    return inventory_check


def audit_inventory_check(
    inventory_check: InventoryCheck,
    user: User,
    status: str,
    audit_opinion: str | None = None
) -> InventoryCheck:
    if inventory_check.status != 'submitted':
        raise ValidationError('只能审核待审核状态的盘点单')

    if status not in ['approved', 'rejected']:
        raise ValidationError('审核状态无效')

    inventory_check.status = status
    if audit_opinion is not None:
        inventory_check.audit_opinion = audit_opinion
    inventory_check.audited_by = user
    inventory_check.audited_at = timezone.now()

    if status == 'approved':
        with transaction.atomic():
            _update_stock_from_inventory_check(inventory_check)

    inventory_check.save()
    return inventory_check


def _update_stock_from_inventory_check(inventory_check: InventoryCheck):
    for item in inventory_check.items.all():
        if item.diff_quantity == 0:
            continue

        stock = MaterialStock.objects.filter(
            zone=inventory_check.zone,
            floor=inventory_check.floor,
            material_category=item.material_category,
            material_batch=item.material_batch
        ).first()

        if item.diff_type == 'overage':
            if stock:
                stock.quantity += item.diff_quantity
                stock.save()
            else:
                MaterialStock.objects.create(
                    zone=inventory_check.zone,
                    floor=inventory_check.floor,
                    material_category=item.material_category,
                    material_batch=item.material_batch,
                    quantity=item.diff_quantity
                )
        elif item.diff_type == 'shortage':
            if stock:
                if stock.quantity + item.diff_quantity < 0:
                    raise ValidationError(
                        f'材料 {item.material_category.name} 库存不足，无法处理盘亏'
                    )
                stock.quantity += item.diff_quantity
                stock.save()
            else:
                raise ValidationError(
                    f'材料 {item.material_category.name} 无库存记录，无法处理盘亏'
                )


def cancel_inventory_check(
    inventory_check: InventoryCheck,
    user: User
) -> InventoryCheck:
    if inventory_check.status in ['approved', 'cancelled']:
        raise ValidationError('该状态的盘点单无法取消')

    inventory_check.status = 'cancelled'
    inventory_check.save()
    return inventory_check


def load_book_quantities(zone: Zone, floor: Floor | None = None) -> list[dict]:
    all_zone_ids = zone.get_all_child_ids()
    stocks = MaterialStock.objects.filter(zone_id__in=all_zone_ids)
    if floor:
        stocks = stocks.filter(floor=floor)

    stocks = stocks.select_related(
        'material_category', 'material_batch'
    )

    result = []
    for stock in stocks:
        result.append({
            'material_category': stock.material_category_id,
            'material_category_name': stock.material_category.name,
            'material_category_code': stock.material_category.code,
            'material_batch': stock.material_batch_id,
            'material_batch_no': stock.material_batch.batch_no,
            'book_quantity': str(stock.quantity),
            'floor': stock.floor_id if stock.floor else None,
            'floor_name': stock.floor.name if stock.floor else None
        })
    return result
