"""
异常记录业务服务层
职责：处理异常记录的创建、审核、处理等核心业务逻辑
原则：业务逻辑下沉，处理状态流转和人员关联
"""
from django.utils import timezone
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError

from ..models import ExceptionRecord
from ..utils import generate_exception_no


def create_exception_record(data: dict, user: User) -> ExceptionRecord:
    data['exception_no'] = generate_exception_no()
    data['reported_by'] = user
    data['status'] = 'pending'
    return ExceptionRecord.objects.create(**data)


def audit_exception_record(
    exception: ExceptionRecord,
    user: User,
    status: str,
    handling_suggestion: str | None = None,
    handling_result: str | None = None
) -> ExceptionRecord:
    exception.status = status
    if handling_suggestion is not None:
        exception.handling_suggestion = handling_suggestion
    if handling_result is not None:
        exception.handling_result = handling_result
    exception.audited_by = user
    exception.audited_at = timezone.now()
    if status in ['resolved', 'closed']:
        exception.resolved_at = timezone.now()
        exception.handled_by = user
    exception.save()
    return exception


def resolve_exception_record(
    exception: ExceptionRecord,
    user: User,
    handling_result: str | None = None
) -> ExceptionRecord:
    if exception.status not in ['pending', 'processing']:
        raise ValidationError('只能处理待复核或处理中的异常')
    exception.status = 'resolved'
    if handling_result is not None:
        exception.handling_result = handling_result
    exception.handled_by = user
    exception.resolved_at = timezone.now()
    if not exception.audited_by:
        exception.audited_by = user
        exception.audited_at = timezone.now()
    exception.save()
    return exception
