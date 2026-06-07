"""
材料批次业务服务层
职责：处理材料批次创建、入库等核心业务逻辑
原则：业务逻辑下沉，事务控制在此层，处理库存流转
"""
from django.db import transaction
from django.contrib.auth.models import User

from ..models import MaterialBatch, MaterialStock, Zone, Floor
from ..validators import (
    validate_inbound_quantity,
    validate_zone_project,
    validate_floor_project
)
from ..utils import generate_batch_no


def create_material_batch(data: dict, user: User) -> MaterialBatch:
    data['batch_no'] = generate_batch_no()
    data['created_by'] = user
    data['status'] = 'pending'
    return MaterialBatch.objects.create(**data)


def inbound_material_batch(
    batch: MaterialBatch,
    zone_id: int,
    quantity: float,
    floor_id: int | None = None
) -> tuple[MaterialBatch, MaterialStock]:
    validate_inbound_quantity(batch, quantity)

    zone = Zone.objects.get(id=zone_id)
    validate_zone_project(zone, batch.project_id)

    floor = None
    if floor_id:
        floor = Floor.objects.get(id=floor_id)
        validate_floor_project(floor, batch.project_id)

    with transaction.atomic():
        stock, created = MaterialStock.objects.get_or_create(
            zone=zone,
            material_category=batch.material_category,
            material_batch=batch,
            floor=floor,
            defaults={'quantity': quantity}
        )
        if not created:
            stock.quantity += quantity
            stock.save()

        batch.received_quantity += quantity
        if batch.received_quantity >= batch.total_quantity:
            batch.status = 'in_stock'
        else:
            batch.status = 'partial'
        batch.save()

    return batch, stock
