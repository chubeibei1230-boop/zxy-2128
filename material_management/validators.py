"""
业务校验层
职责：封装业务规则校验逻辑，如参数合法性、状态合法性等
原则：只做校验，不修改数据，抛出 ValidationError 异常
"""
from django.core.exceptions import ValidationError
from .models import Zone, Floor, MaterialBatch, MaterialStock


def validate_zone_parent(zone: Zone, parent_id: int | None) -> None:
    if parent_id is None:
        return
    if parent_id == zone.id:
        raise ValidationError('不能将自己设为父级')
    try:
        parent = Zone.objects.get(id=parent_id)
        child_ids = zone.get_all_child_ids()
        if parent.id in child_ids:
            raise ValidationError('不能将子分区设为父级')
    except Zone.DoesNotExist:
        pass


def validate_zone_move(zone: Zone, new_parent_id: int | None) -> None:
    if new_parent_id is None:
        return
    try:
        new_parent = Zone.objects.get(id=new_parent_id)
        if new_parent.project_id != zone.project_id:
            raise ValidationError('不能移动到其他项目')
        child_ids = zone.get_all_child_ids()
        if new_parent.id in child_ids:
            raise ValidationError('不能移动到自己的子分区下')
    except Zone.DoesNotExist:
        raise ValidationError('目标分区不存在')


def validate_inbound_quantity(batch: MaterialBatch, quantity: float) -> None:
    if quantity <= 0:
        raise ValidationError('入库数量必须大于0')
    if batch.received_quantity + quantity > batch.total_quantity:
        raise ValidationError('入库数量超过批次总数量')


def validate_zone_project(zone: Zone, project_id: int) -> None:
    if zone.project_id != project_id:
        raise ValidationError('分区不属于该项目')


def validate_floor_project(floor: Floor, project_id: int) -> None:
    if floor.project_id != project_id:
        raise ValidationError('楼层不属于该项目')


def validate_stock_availability(
    zone: Zone,
    material_category_id: int,
    material_batch_id: int,
    floor: Floor | None,
    quantity: float
) -> None:
    stock = MaterialStock.objects.filter(
        zone=zone,
        material_category_id=material_category_id,
        material_batch_id=material_batch_id,
        floor=floor
    ).first()
    if not stock or stock.quantity < quantity:
        raise ValidationError('库存不足')


def validate_zone_merge(target_zone_id: int, source_zone_ids: list[int]) -> None:
    if target_zone_id in source_zone_ids:
        raise ValidationError('目标分区不能在源分区列表中')
    try:
        Zone.objects.get(id=target_zone_id)
    except Zone.DoesNotExist:
        raise ValidationError('目标分区不存在')
