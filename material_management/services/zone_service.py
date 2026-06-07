"""
分区业务服务层
职责：处理分区相关的核心业务逻辑，包括创建、更新、移动、合并、禁用等
原则：业务逻辑下沉，事务控制在此层，调用 validators 和 models
"""
from django.db import transaction
from django.core.exceptions import ValidationError

from ..models import Zone, MaterialStock, MaterialTransfer, MaterialUsage, ExceptionRecord
from ..validators import validate_zone_parent, validate_zone_move, validate_zone_merge


def calculate_zone_level(parent_id: int | None) -> int:
    if not parent_id:
        return 1
    try:
        parent = Zone.objects.get(id=parent_id)
        return parent.level + 1
    except Zone.DoesNotExist:
        return 1


def update_zone_children_level(zone: Zone, new_level: int) -> None:
    children = zone.children.all()
    for child in children:
        child.level = new_level + 1
        child.save()
        update_zone_children_level(child, child.level)


def create_zone(data: dict) -> Zone:
    parent_id = data.get('parent')
    data['level'] = calculate_zone_level(parent_id)
    zone = Zone.objects.create(**data)
    return zone


def update_zone(zone: Zone, data: dict) -> Zone:
    parent_id = data.get('parent')
    level_changed = False
    new_level = zone.level

    if parent_id is not None:
        validate_zone_parent(zone, parent_id)
        if parent_id:
            try:
                parent = Zone.objects.get(id=parent_id)
                new_level = parent.level + 1
                level_changed = True
            except Zone.DoesNotExist:
                new_level = 1
                level_changed = True
        else:
            new_level = 1
            level_changed = True
        data['level'] = new_level

    for key, value in data.items():
        setattr(zone, key, value)
    zone.save()

    if level_changed:
        zone.refresh_from_db()
        update_zone_children_level(zone, zone.level)

    return zone


def move_zone(zone: Zone, new_parent_id: int | None) -> Zone:
    validate_zone_move(zone, new_parent_id)

    if new_parent_id:
        new_parent = Zone.objects.get(id=new_parent_id)
        zone.parent = new_parent
        zone.level = new_parent.level + 1
    else:
        zone.parent = None
        zone.level = 1

    zone.save()
    update_zone_children_level(zone, zone.level)
    return zone


def merge_zones(target_zone_id: int, source_zone_ids: list[int]) -> Zone:
    validate_zone_merge(target_zone_id, source_zone_ids)
    target_zone = Zone.objects.get(id=target_zone_id)

    with transaction.atomic():
        for source_id in source_zone_ids:
            try:
                source_zone = Zone.objects.get(id=source_id)
                if source_zone.project_id != target_zone.project_id:
                    continue

                source_stocks = MaterialStock.objects.filter(zone=source_zone)
                for source_stock in source_stocks:
                    try:
                        target_stock = MaterialStock.objects.get(
                            zone=target_zone,
                            material_category=source_stock.material_category,
                            material_batch=source_stock.material_batch,
                            floor=source_stock.floor
                        )
                        target_stock.quantity += source_stock.quantity
                        target_stock.save()
                        source_stock.delete()
                    except MaterialStock.DoesNotExist:
                        source_stock.zone = target_zone
                        source_stock.save()

                MaterialTransfer.objects.filter(from_zone=source_zone).update(from_zone=target_zone)
                MaterialTransfer.objects.filter(to_zone=source_zone).update(to_zone=target_zone)
                MaterialUsage.objects.filter(zone=source_zone).update(zone=target_zone)
                ExceptionRecord.objects.filter(zone=source_zone).update(zone=target_zone)

                # Re-parent child zones one by one so their stored levels stay consistent.
                for child_zone in Zone.objects.filter(parent=source_zone):
                    child_zone.parent = target_zone
                    child_zone.level = target_zone.level + 1
                    child_zone.save()
                    update_zone_children_level(child_zone, child_zone.level)

                source_zone.is_active = False
                source_zone.save()
            except Zone.DoesNotExist:
                continue

    return target_zone


def disable_zone(zone: Zone) -> Zone:
    zone.is_active = False
    zone.save()
    return zone
