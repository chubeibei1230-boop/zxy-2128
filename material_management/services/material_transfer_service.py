"""
材料转移业务服务层
职责：处理材料转移单的创建、确认、取消等核心业务逻辑
原则：业务逻辑下沉，事务控制在此层，处理库存流转
"""
from django.db import transaction
from django.utils import timezone
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError

from ..models import MaterialTransfer, MaterialStock
from ..utils import generate_transfer_no


def create_material_transfer(data: dict, user: User) -> MaterialTransfer:
    data['transfer_no'] = generate_transfer_no()
    data['created_by'] = user
    data['status'] = 'pending'
    return MaterialTransfer.objects.create(**data)


def confirm_material_transfer(transfer: MaterialTransfer, user: User) -> MaterialTransfer:
    if transfer.status != 'pending':
        raise ValidationError('只有待确认的转移单才能确认')

    with transaction.atomic():
        from_stock = MaterialStock.objects.filter(
            zone=transfer.from_zone,
            material_category=transfer.material_category,
            material_batch=transfer.material_batch,
            floor=transfer.from_floor
        ).first()
        if not from_stock or from_stock.quantity < transfer.quantity:
            raise ValidationError('源分区库存不足')

        from_stock.quantity -= transfer.quantity
        from_stock.save()

        to_stock, created = MaterialStock.objects.get_or_create(
            zone=transfer.to_zone,
            material_category=transfer.material_category,
            material_batch=transfer.material_batch,
            floor=transfer.to_floor,
            defaults={'quantity': transfer.quantity}
        )
        if not created:
            to_stock.quantity += transfer.quantity
            to_stock.save()

        transfer.status = 'completed'
        transfer.confirmed_by = user
        transfer.confirmed_at = timezone.now()
        transfer.save()

    return transfer


def cancel_material_transfer(transfer: MaterialTransfer) -> MaterialTransfer:
    if transfer.status != 'pending':
        raise ValidationError('只有待确认的转移单才能取消')
    transfer.status = 'cancelled'
    transfer.save()
    return transfer
