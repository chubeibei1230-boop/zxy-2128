"""
预警业务服务层
职责：处理预警检测、生成、状态流转等核心业务逻辑
原则：业务逻辑下沉，处理状态流转和人员关联，确保与现有业务一致性
"""
from django.utils import timezone
from django.db import transaction
from django.db.models import Sum, Max
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from datetime import timedelta
from decimal import Decimal

from ..models import (
    MaterialWarning, MaterialStock, MaterialBatch, 
    MaterialCategory, Zone, Project, MaterialUsage,
    ExceptionRecord
)
from ..utils import generate_warning_no


LONG_UNUSED_DAYS = 90
EXPIRING_WARNING_DAYS = 30
OVERSTOCK_RATIO = Decimal('2.0')


def detect_low_stock_warnings(project_id: int | None = None, user: User | None = None) -> list[MaterialWarning]:
    """检测低库存预警"""
    stocks = MaterialStock.objects.select_related(
        'zone', 'zone__project', 'material_category', 'material_batch'
    ).all()
    if project_id:
        stocks = stocks.filter(zone__project_id=project_id)
    
    warnings = []
    for stock in stocks:
        category = stock.material_category
        safety_threshold = category.safety_threshold
        
        if stock.quantity < safety_threshold:
            existing_warning = MaterialWarning.objects.filter(
                project=stock.zone.project,
                zone=stock.zone,
                material_category=stock.material_category,
                material_batch=stock.material_batch,
                warning_type='low_stock',
                status__in=['pending', 'processing']
            ).first()
            
            if not existing_warning:
                diff = safety_threshold - stock.quantity
                priority = 'low'
                if diff > safety_threshold * Decimal('0.8'):
                    priority = 'urgent'
                elif diff > safety_threshold * Decimal('0.5'):
                    priority = 'high'
                elif diff > safety_threshold * Decimal('0.2'):
                    priority = 'medium'
                
                warning = MaterialWarning.objects.create(
                    warning_no=generate_warning_no(),
                    project=stock.zone.project,
                    zone=stock.zone,
                    floor=stock.floor,
                    material_category=stock.material_category,
                    material_batch=stock.material_batch,
                    material_stock=stock,
                    warning_type='low_stock',
                    priority=priority,
                    description=f'库存数量 {stock.quantity} {category.unit} 低于安全阈值 {safety_threshold} {category.unit}',
                    current_quantity=stock.quantity,
                    threshold_quantity=safety_threshold,
                    created_by=user
                )
                warnings.append(warning)
    return warnings


def detect_expiring_warnings(project_id: int | None = None, user: User | None = None) -> list[MaterialWarning]:
    """检测临期预警"""
    today = timezone.now().date()
    batches = MaterialBatch.objects.select_related(
        'project', 'material_category'
    ).filter(
        status='in_stock',
        production_date__isnull=False
    )
    if project_id:
        batches = batches.filter(project_id=project_id)
    
    warnings = []
    for batch in batches:
        category = batch.material_category
        shelf_life_days = category.shelf_life_days
        if not shelf_life_days or not batch.production_date:
            continue
            
        expiry_date = batch.production_date + timedelta(days=shelf_life_days)
        days_to_expiry = (expiry_date - today).days
        
        if days_to_expiry <= EXPIRING_WARNING_DAYS and days_to_expiry >= 0:
            stocks = MaterialStock.objects.filter(material_batch=batch)
            for stock in stocks:
                existing_warning = MaterialWarning.objects.filter(
                    project=batch.project,
                    zone=stock.zone,
                    material_category=category,
                    material_batch=batch,
                    warning_type='expiring',
                    status__in=['pending', 'processing']
                ).first()
                
                if not existing_warning:
                    priority = 'low'
                    if days_to_expiry <= 7:
                        priority = 'urgent'
                    elif days_to_expiry <= 15:
                        priority = 'high'
                    elif days_to_expiry <= 30:
                        priority = 'medium'
                    
                    warning = MaterialWarning.objects.create(
                        warning_no=generate_warning_no(),
                        project=batch.project,
                        zone=stock.zone,
                        floor=stock.floor,
                        material_category=category,
                        material_batch=batch,
                        material_stock=stock,
                        warning_type='expiring',
                        priority=priority,
                        description=f'批次 {batch.batch_no} 将于 {expiry_date} 到期，剩余 {days_to_expiry} 天',
                        current_quantity=stock.quantity,
                        threshold_quantity=0,
                        warning_days=days_to_expiry,
                        created_by=user
                    )
                    warnings.append(warning)
    return warnings


def detect_long_unused_warnings(project_id: int | None = None, user: User | None = None) -> list[MaterialWarning]:
    """检测长期未使用预警"""
    cutoff_date = timezone.now() - timedelta(days=LONG_UNUSED_DAYS)
    stocks = MaterialStock.objects.select_related(
        'zone', 'zone__project', 'material_category', 'material_batch'
    ).filter(
        updated_at__lte=cutoff_date,
        quantity__gt=0
    )
    if project_id:
        stocks = stocks.filter(zone__project_id=project_id)
    
    warnings = []
    for stock in stocks:
        recent_usage = MaterialUsage.objects.filter(
            material_batch=stock.material_batch,
            zone=stock.zone,
            created_at__gte=cutoff_date
        ).exists()
        
        if not recent_usage:
            existing_warning = MaterialWarning.objects.filter(
                project=stock.zone.project,
                zone=stock.zone,
                material_category=stock.material_category,
                material_batch=stock.material_batch,
                warning_type='long_unused',
                status__in=['pending', 'processing']
            ).first()
            
            if not existing_warning:
                days_unused = (timezone.now() - stock.updated_at).days
                priority = 'medium'
                if days_unused > 180:
                    priority = 'high'
                
                warning = MaterialWarning.objects.create(
                    warning_no=generate_warning_no(),
                    project=stock.zone.project,
                    zone=stock.zone,
                    floor=stock.floor,
                    material_category=stock.material_category,
                    material_batch=stock.material_batch,
                    material_stock=stock,
                    warning_type='long_unused',
                    priority=priority,
                    description=f'材料已闲置 {days_unused} 天未使用',
                    current_quantity=stock.quantity,
                    threshold_quantity=0,
                    warning_days=days_unused,
                    created_by=user
                )
                warnings.append(warning)
    return warnings


def detect_overstock_warnings(project_id: int | None = None, user: User | None = None) -> list[MaterialWarning]:
    """检测库存积压预警"""
    ninety_days_ago = timezone.now() - timedelta(days=90)
    stocks = MaterialStock.objects.select_related(
        'zone', 'zone__project', 'material_category', 'material_batch'
    ).filter(quantity__gt=0)
    if project_id:
        stocks = stocks.filter(zone__project_id=project_id)
    
    warnings = []
    for stock in stocks:
        usage_sum = MaterialUsage.objects.filter(
            material_category=stock.material_category,
            zone=stock.zone,
            created_at__gte=ninety_days_ago,
            status__in=['approved', 'used']
        ).aggregate(total=Sum('quantity'))['total'] or 0
        
        avg_monthly_usage = usage_sum / Decimal('3') if usage_sum > 0 else Decimal('0')
        
        if avg_monthly_usage > 0 and stock.quantity > avg_monthly_usage * OVERSTOCK_RATIO:
            existing_warning = MaterialWarning.objects.filter(
                project=stock.zone.project,
                zone=stock.zone,
                material_category=stock.material_category,
                material_batch=stock.material_batch,
                warning_type='overstock',
                status__in=['pending', 'processing']
            ).first()
            
            if not existing_warning:
                overstock_ratio = round(float(stock.quantity) / float(avg_monthly_usage), 2) if avg_monthly_usage > 0 else 0
                priority = 'low'
                if overstock_ratio > 5:
                    priority = 'high'
                elif overstock_ratio > 3:
                    priority = 'medium'
                
                warning = MaterialWarning.objects.create(
                    warning_no=generate_warning_no(),
                    project=stock.zone.project,
                    zone=stock.zone,
                    floor=stock.floor,
                    material_category=stock.material_category,
                    material_batch=stock.material_batch,
                    material_stock=stock,
                    warning_type='overstock',
                    priority=priority,
                    description=f'库存积压：当前库存 {stock.quantity}，月均使用量 {round(float(avg_monthly_usage), 2)}，积压倍数 {overstock_ratio}x',
                    current_quantity=stock.quantity,
                    threshold_quantity=round(avg_monthly_usage * OVERSTOCK_RATIO, 2),
                    warning_days=0,
                    created_by=user
                )
                warnings.append(warning)
    return warnings


def run_warning_detection(project_id: int | None = None, user: User | None = None) -> dict:
    """运行所有预警检测"""
    with transaction.atomic():
        low_stock = detect_low_stock_warnings(project_id, user)
        expiring = detect_expiring_warnings(project_id, user)
        long_unused = detect_long_unused_warnings(project_id, user)
        overstock = detect_overstock_warnings(project_id, user)
        
        return {
            'low_stock_count': len(low_stock),
            'expiring_count': len(expiring),
            'long_unused_count': len(long_unused),
            'overstock_count': len(overstock),
            'total_count': len(low_stock) + len(expiring) + len(long_unused) + len(overstock)
        }


def start_processing_warning(warning: MaterialWarning, user: User, 
                             handling_opinion: str | None = None,
                             responsible_person_id: int | None = None) -> MaterialWarning:
    """开始处理预警"""
    if warning.status != 'pending':
        raise ValidationError('只能处理待处理状态的预警')
    
    warning.status = 'processing'
    if handling_opinion:
        warning.handling_opinion = handling_opinion
    if responsible_person_id:
        from django.contrib.auth.models import User
        try:
            responsible_person = User.objects.get(id=responsible_person_id)
            warning.responsible_person = responsible_person
        except User.DoesNotExist:
            raise ValidationError('指定的责任人不存在')
    warning.handled_by = user
    warning.save()
    return warning


def process_warning(warning: MaterialWarning, user: User,
                    handling_result: str,
                    handling_opinion: str | None = None,
                    responsible_person_id: int | None = None) -> MaterialWarning:
    """处理预警（标记为已处理）"""
    if warning.status not in ['pending', 'processing']:
        raise ValidationError('只能处理待处理或处理中的预警')
    
    warning.status = 'processed'
    warning.handling_result = handling_result
    if handling_opinion:
        warning.handling_opinion = handling_opinion
    if responsible_person_id:
        from django.contrib.auth.models import User
        try:
            responsible_person = User.objects.get(id=responsible_person_id)
            warning.responsible_person = responsible_person
        except User.DoesNotExist:
            raise ValidationError('指定的责任人不存在')
    warning.handled_by = user
    warning.handled_at = timezone.now()
    warning.save()
    return warning


def ignore_warning(warning: MaterialWarning, user: User,
                   handling_opinion: str | None = None) -> MaterialWarning:
    """忽略预警"""
    if warning.status not in ['pending', 'processing']:
        raise ValidationError('只能忽略待处理或处理中的预警')
    
    warning.status = 'ignored'
    if handling_opinion:
        warning.handling_opinion = handling_opinion
    warning.handled_by = user
    warning.handled_at = timezone.now()
    warning.save()
    return warning


def reopen_warning(warning: MaterialWarning, user: User,
                   handling_opinion: str | None = None) -> MaterialWarning:
    """重新打开预警"""
    if warning.status not in ['processed', 'ignored']:
        raise ValidationError('只能重新打开已处理或已忽略的预警')
    
    warning.status = 'pending'
    if handling_opinion:
        warning.handling_opinion = handling_opinion
    warning.handled_by = None
    warning.handled_at = None
    warning.save()
    return warning


def get_warning_statistics(project_id: int | None = None) -> dict:
    """获取预警统计数据"""
    params = {}
    if project_id:
        params['project_id'] = project_id
    
    warnings = MaterialWarning.objects.filter(**params)
    total = warnings.count()
    pending = warnings.filter(status='pending').count()
    processing = warnings.filter(status='processing').count()
    processed = warnings.filter(status='processed').count()
    ignored = warnings.filter(status='ignored').count()
    
    low_stock = warnings.filter(warning_type='low_stock').count()
    expiring = warnings.filter(warning_type='expiring').count()
    long_unused = warnings.filter(warning_type='long_unused').count()
    overstock = warnings.filter(warning_type='overstock').count()
    
    return {
        'total': total,
        'pending': pending,
        'processing': processing,
        'processed': processed,
        'ignored': ignored,
        'completion_rate': round((processed + ignored) / total * 100, 2) if total > 0 else 0,
        'by_type': {
            'low_stock': low_stock,
            'expiring': expiring,
            'long_unused': long_unused,
            'overstock': overstock
        }
    }
