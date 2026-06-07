"""
预警闭环处置中心服务层
职责：处理预警的闭环处置、轨迹记录、自动闭环检测、业务单据关联等核心业务逻辑
原则：确保预警处理链路可追踪，业务单据与预警状态联动
"""
from django.utils import timezone
from django.db import transaction
from django.db.models import Sum
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from datetime import timedelta
from decimal import Decimal

from ..models import (
    MaterialWarning, WarningProcessLog, MaterialStock,
    MaterialUsage, ExceptionRecord, InventoryCheck,
    MaterialBatch, MaterialCategory
)
from .warning_service import (
    OVERSTOCK_RATIO, LONG_UNUSED_DAYS, EXPIRING_WARNING_DAYS
)


def create_process_log(warning: MaterialWarning, action: str, user: User = None,
                       action_detail: str = None, old_status: str = None,
                       new_status: str = None, remark: str = None,
                       related_usage: MaterialUsage = None,
                       related_exception: ExceptionRecord = None,
                       related_inventory_check: InventoryCheck = None) -> WarningProcessLog:
    """创建预警处理轨迹日志"""
    log = WarningProcessLog.objects.create(
        warning=warning,
        action=action,
        action_detail=action_detail,
        old_status=old_status,
        new_status=new_status,
        remark=remark,
        related_usage=related_usage,
        related_exception=related_exception,
        related_inventory_check=related_inventory_check,
        created_by=user
    )
    return log


def assign_responsible_person(warning: MaterialWarning, user: User,
                              responsible_person_id: int,
                              remark: str = None) -> MaterialWarning:
    """指派责任人"""
    if warning.status not in ['pending', 'processing']:
        raise ValidationError('只能指派待处理或处理中的预警')
    
    try:
        responsible_person = User.objects.get(id=responsible_person_id)
    except User.DoesNotExist:
        raise ValidationError('指定的责任人不存在')
    
    old_responsible = warning.responsible_person
    warning.responsible_person = responsible_person
    warning.save()
    
    action_detail = f'指派责任人：{responsible_person.username}'
    if old_responsible:
        action_detail += f'（原责任人：{old_responsible.username}）'
    
    create_process_log(
        warning=warning,
        action='assign',
        user=user,
        action_detail=action_detail,
        old_status=warning.status,
        new_status=warning.status,
        remark=remark
    )
    
    return warning


def relate_business_document(warning: MaterialWarning, user: User,
                             doc_type: str, doc_id: int,
                             remark: str = None) -> MaterialWarning:
    """关联业务单据"""
    if warning.status not in ['pending', 'processing']:
        raise ValidationError('只能关联待处理或处理中的预警')
    
    related_doc = None
    action = None
    action_detail = None
    
    if doc_type == 'usage':
        try:
            related_doc = MaterialUsage.objects.get(id=doc_id)
            warning.related_usage = related_doc
            action = 'relate_usage'
            action_detail = f'关联领用单：{related_doc.usage_no}'
        except MaterialUsage.DoesNotExist:
            raise ValidationError('领用单不存在')
    elif doc_type == 'exception':
        try:
            related_doc = ExceptionRecord.objects.get(id=doc_id)
            warning.related_exception = related_doc
            action = 'relate_exception'
            action_detail = f'关联异常单：{related_doc.exception_no}'
        except ExceptionRecord.DoesNotExist:
            raise ValidationError('异常单不存在')
    elif doc_type == 'inventory':
        try:
            related_doc = InventoryCheck.objects.get(id=doc_id)
            warning.related_inventory_check = related_doc
            action = 'relate_inventory'
            action_detail = f'关联盘点单：{related_doc.check_no}'
        except InventoryCheck.DoesNotExist:
            raise ValidationError('盘点单不存在')
    else:
        raise ValidationError('不支持的单据类型')
    
    warning.save()
    
    create_process_log(
        warning=warning,
        action=action,
        user=user,
        action_detail=action_detail,
        old_status=warning.status,
        new_status=warning.status,
        remark=remark,
        related_usage=related_doc if doc_type == 'usage' else None,
        related_exception=related_doc if doc_type == 'exception' else None,
        related_inventory_check=related_doc if doc_type == 'inventory' else None
    )
    
    return warning


def check_warning_auto_closure(warning: MaterialWarning) -> tuple[bool, str]:
    """
    检查预警是否满足自动闭环条件
    返回：(是否满足闭环条件, 说明信息)
    """
    warning_type = warning.warning_type
    
    if warning_type == 'low_stock':
        if warning.material_stock:
            current_qty = warning.material_stock.quantity
            safety_threshold = warning.material_category.safety_threshold
            if current_qty >= safety_threshold:
                return True, f'库存已恢复至安全阈值以上（当前：{current_qty}，阈值：{safety_threshold}）'
        return False, '库存仍低于安全阈值'
    
    elif warning_type == 'expiring':
        if warning.material_stock and warning.material_stock.quantity <= 0:
            return True, '临期材料库存已清零'
        if warning.related_exception and warning.related_exception.status in ['resolved', 'closed']:
            return True, f'关联异常单已{warning.related_exception.get_status_display()}'
        return False, '临期材料仍有库存或关联异常单未处理完成'
    
    elif warning_type == 'long_unused':
        ninety_days_ago = timezone.now() - timedelta(days=LONG_UNUSED_DAYS)
        recent_usage = MaterialUsage.objects.filter(
            material_batch=warning.material_batch,
            zone=warning.zone,
            created_at__gte=ninety_days_ago,
            status__in=['approved', 'used']
        ).exists()
        if recent_usage:
            return True, '材料近期已有领用记录'
        if warning.related_usage and warning.related_usage.status in ['approved', 'used']:
            return True, f'关联领用单已{warning.related_usage.get_status_display()}'
        return False, '材料仍未使用且无有效领用记录'
    
    elif warning_type == 'overstock':
        ninety_days_ago = timezone.now() - timedelta(days=90)
        usage_sum = MaterialUsage.objects.filter(
            material_category=warning.material_category,
            zone=warning.zone,
            created_at__gte=ninety_days_ago,
            status__in=['approved', 'used']
        ).aggregate(total=Sum('quantity'))['total'] or 0
        avg_monthly_usage = usage_sum / Decimal('3') if usage_sum > 0 else Decimal('0')
        
        if warning.material_stock:
            if avg_monthly_usage > 0 and warning.material_stock.quantity <= avg_monthly_usage * OVERSTOCK_RATIO:
                return True, f'库存已降至合理范围（当前：{warning.material_stock.quantity}，月均用量：{round(float(avg_monthly_usage), 2)}）'
            elif avg_monthly_usage == 0 and warning.material_stock.quantity <= warning.material_category.safety_threshold * Decimal('3'):
                return True, '库存已降至合理范围'
        
        if warning.related_usage and warning.related_usage.status in ['approved', 'used']:
            return True, f'关联领用单已{warning.related_usage.get_status_display()}'
        
        return False, '库存仍处于积压状态'
    
    return False, '未知预警类型'


def check_warning_auto_reopen(warning: MaterialWarning) -> tuple[bool, str]:
    """
    检查已闭环的预警是否需要重新打开（自动恢复待处理）
    返回：(是否需要重新打开, 说明信息)
    """
    warning_type = warning.warning_type
    
    if warning_type == 'low_stock':
        if warning.material_stock:
            current_qty = warning.material_stock.quantity
            safety_threshold = warning.material_category.safety_threshold
            if current_qty < safety_threshold:
                return True, f'库存再次低于安全阈值（当前：{current_qty}，阈值：{safety_threshold}）'
        return False, '库存正常'
    
    elif warning_type == 'expiring':
        today = timezone.now().date()
        if warning.material_batch and warning.material_batch.production_date:
            shelf_life_days = warning.material_category.shelf_life_days
            if shelf_life_days:
                expiry_date = warning.material_batch.production_date + timedelta(days=shelf_life_days)
                days_to_expiry = (expiry_date - today).days
                if days_to_expiry <= EXPIRING_WARNING_DAYS and days_to_expiry >= 0:
                    if warning.material_stock and warning.material_stock.quantity > 0:
                        return True, f'材料仍在临期范围内且有库存（剩余{days_to_expiry}天）'
        return False, '材料已过期或无库存'
    
    elif warning_type == 'long_unused':
        if warning.material_stock and warning.material_stock.quantity > 0:
            days_unused = (timezone.now() - warning.material_stock.updated_at).days
            if days_unused >= LONG_UNUSED_DAYS:
                ninety_days_ago = timezone.now() - timedelta(days=LONG_UNUSED_DAYS)
                recent_usage = MaterialUsage.objects.filter(
                    material_batch=warning.material_batch,
                    zone=warning.zone,
                    created_at__gte=ninety_days_ago,
                    status__in=['approved', 'used']
                ).exists()
                if not recent_usage:
                    return True, f'材料仍长期未使用（已闲置{days_unused}天）'
        return False, '材料近期已有使用'
    
    elif warning_type == 'overstock':
        hundred_and_eighty_days_ago = timezone.now() - timedelta(days=180)
        if warning.material_stock and warning.material_stock.quantity > 0:
            usage_sum = MaterialUsage.objects.filter(
                material_category=warning.material_category,
                zone=warning.zone,
                created_at__gte=hundred_and_eighty_days_ago,
                status__in=['approved', 'used']
            ).aggregate(total=Sum('quantity'))['total'] or 0
            avg_monthly_usage = usage_sum / Decimal('6') if usage_sum > 0 else Decimal('0')
            
            is_overstock = False
            if avg_monthly_usage > 0 and warning.material_stock.quantity > avg_monthly_usage * OVERSTOCK_RATIO:
                is_overstock = True
            elif avg_monthly_usage == 0 and warning.material_stock.quantity > warning.material_category.safety_threshold * Decimal('3'):
                is_overstock = True
            
            if is_overstock:
                return True, '库存再次出现积压'
        return False, '库存处于合理范围'
    
    return False, '无需重新打开'


def auto_close_warning(warning: MaterialWarning, reason: str) -> MaterialWarning:
    """自动闭环预警"""
    if warning.status not in ['pending', 'processing']:
        return warning
    
    old_status = warning.status
    warning.status = 'processed'
    warning.handling_result = f'自动闭环：{reason}'
    warning.handled_at = timezone.now()
    warning.save()
    
    create_process_log(
        warning=warning,
        action='auto_close',
        action_detail=reason,
        old_status=old_status,
        new_status='processed',
        remark='系统自动检测闭环'
    )
    
    return warning


def auto_reopen_warning(warning: MaterialWarning, reason: str) -> MaterialWarning:
    """自动恢复待处理"""
    if warning.status not in ['processed', 'ignored']:
        return warning
    
    old_status = warning.status
    warning.status = 'pending'
    warning.handled_by = None
    warning.handled_at = None
    warning.save()
    
    create_process_log(
        warning=warning,
        action='auto_reopen',
        action_detail=reason,
        old_status=old_status,
        new_status='pending',
        remark='系统自动检测恢复待处理'
    )
    
    return warning


def run_auto_closure_check(project_id: int = None) -> dict:
    """
    运行自动闭环检测
    检查所有待处理/处理中的预警是否满足自动闭环条件
    同时检查已闭环的预警是否需要重新打开
    """
    results = {
        'auto_closed': [],
        'auto_reopened': [],
        'errors': []
    }
    
    warnings = MaterialWarning.objects.all()
    if project_id:
        warnings = warnings.filter(project_id=project_id)
    
    with transaction.atomic():
        for warning in warnings:
            try:
                if warning.status in ['pending', 'processing']:
                    can_close, reason = check_warning_auto_closure(warning)
                    if can_close:
                        auto_close_warning(warning, reason)
                        results['auto_closed'].append({
                            'warning_no': warning.warning_no,
                            'warning_type': warning.warning_type,
                            'reason': reason
                        })
                elif warning.status in ['processed', 'ignored']:
                    need_reopen, reason = check_warning_auto_reopen(warning)
                    if need_reopen:
                        auto_reopen_warning(warning, reason)
                        results['auto_reopened'].append({
                            'warning_no': warning.warning_no,
                            'warning_type': warning.warning_type,
                            'reason': reason
                        })
            except Exception as e:
                results['errors'].append({
                    'warning_no': warning.warning_no,
                    'error': str(e)
                })
    
    return results


def get_warning_closure_overview(project_id: int = None) -> dict:
    """获取预警闭环处置中心概览数据"""
    params = {}
    if project_id:
        params['project_id'] = project_id
    
    warnings = MaterialWarning.objects.filter(**params)
    total = warnings.count()
    
    pending = warnings.filter(status='pending').count()
    processing = warnings.filter(status='processing').count()
    processed = warnings.filter(status='processed').count()
    ignored = warnings.filter(status='ignored').count()
    
    auto_closed = WarningProcessLog.objects.filter(
        action='auto_close',
        warning__project_id=project_id if project_id else None
    ).count()
    
    by_type = {
        'low_stock': warnings.filter(warning_type='low_stock').count(),
        'expiring': warnings.filter(warning_type='expiring').count(),
        'long_unused': warnings.filter(warning_type='long_unused').count(),
        'overstock': warnings.filter(warning_type='overstock').count(),
    }
    
    by_priority = {
        'urgent': warnings.filter(priority='urgent').count(),
        'high': warnings.filter(priority='high').count(),
        'medium': warnings.filter(priority='medium').count(),
        'low': warnings.filter(priority='low').count(),
    }
    
    avg_processing_days = 0
    processed_warnings = warnings.filter(status='processed', handled_at__isnull=False)
    if processed_warnings.exists():
        total_days = 0
        for w in processed_warnings:
            if w.handled_at and w.created_at:
                total_days += (w.handled_at - w.created_at).days
        avg_processing_days = round(total_days / processed_warnings.count(), 1)
    
    return {
        'total': total,
        'pending': pending,
        'processing': processing,
        'processed': processed,
        'ignored': ignored,
        'auto_closed_count': auto_closed,
        'completion_rate': round((processed + ignored) / total * 100, 2) if total > 0 else 0,
        'by_type': by_type,
        'by_priority': by_priority,
        'avg_processing_days': avg_processing_days
    }


def get_related_documents_for_warning(warning: MaterialWarning) -> dict:
    """获取预警关联的所有业务单据详情"""
    result = {
        'related_usage': None,
        'related_exception': None,
        'related_inventory_check': None,
        'available_usages': [],
        'available_exceptions': [],
        'available_inventory_checks': []
    }
    
    if warning.related_usage:
        result['related_usage'] = {
            'id': warning.related_usage.id,
            'usage_no': warning.related_usage.usage_no,
            'status': warning.related_usage.status,
            'status_display': warning.related_usage.get_status_display(),
            'quantity': str(warning.related_usage.quantity),
            'created_at': warning.related_usage.created_at
        }
    
    if warning.related_exception:
        result['related_exception'] = {
            'id': warning.related_exception.id,
            'exception_no': warning.related_exception.exception_no,
            'exception_type': warning.related_exception.exception_type,
            'exception_type_display': warning.related_exception.get_exception_type_display(),
            'status': warning.related_exception.status,
            'status_display': warning.related_exception.get_status_display(),
            'created_at': warning.related_exception.created_at
        }
    
    if warning.related_inventory_check:
        result['related_inventory_check'] = {
            'id': warning.related_inventory_check.id,
            'check_no': warning.related_inventory_check.check_no,
            'status': warning.related_inventory_check.status,
            'status_display': warning.related_inventory_check.get_status_display(),
            'check_date': warning.related_inventory_check.check_date,
            'created_at': warning.related_inventory_check.created_at
        }
    
    available_usages = MaterialUsage.objects.filter(
        project=warning.project,
        zone=warning.zone,
        material_category=warning.material_category,
        status__in=['pending', 'approved', 'used']
    ).exclude(id=warning.related_usage_id if warning.related_usage_id else None)[:20]
    
    result['available_usages'] = [
        {
            'id': u.id,
            'usage_no': u.usage_no,
            'status': u.status,
            'status_display': u.get_status_display(),
            'quantity': str(u.quantity),
            'created_at': u.created_at
        } for u in available_usages
    ]
    
    available_exceptions = ExceptionRecord.objects.filter(
        project=warning.project,
        zone=warning.zone,
        material_category=warning.material_category,
        status__in=['pending', 'processing', 'resolved']
    ).exclude(id=warning.related_exception_id if warning.related_exception_id else None)[:20]
    
    result['available_exceptions'] = [
        {
            'id': e.id,
            'exception_no': e.exception_no,
            'exception_type': e.exception_type,
            'exception_type_display': e.get_exception_type_display(),
            'status': e.status,
            'status_display': e.get_status_display(),
            'created_at': e.created_at
        } for e in available_exceptions
    ]
    
    available_checks = InventoryCheck.objects.filter(
        project=warning.project,
        zone=warning.zone,
        status__in=['submitted', 'approved']
    ).exclude(id=warning.related_inventory_check_id if warning.related_inventory_check_id else None)[:20]
    
    result['available_inventory_checks'] = [
        {
            'id': c.id,
            'check_no': c.check_no,
            'status': c.status,
            'status_display': c.get_status_display(),
            'check_date': c.check_date,
            'created_at': c.created_at
        } for c in available_checks
    ]
    
    return result
