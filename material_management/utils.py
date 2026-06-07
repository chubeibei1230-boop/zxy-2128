"""
工具函数层
职责：提供通用的辅助函数，如编号生成、参数解析等
原则：无业务逻辑，纯函数，可被所有层级调用
"""
import uuid
from django.utils import timezone


def generate_batch_no() -> str:
    return f'BATCH{timezone.now().strftime("%Y%m%d%H%M%S")}{uuid.uuid4().hex[:4].upper()}'


def generate_transfer_no() -> str:
    return f'TRANSFER{timezone.now().strftime("%Y%m%d%H%M%S")}{uuid.uuid4().hex[:4].upper()}'


def generate_usage_no() -> str:
    return f'USAGE{timezone.now().strftime("%Y%m%d%H%M%S")}{uuid.uuid4().hex[:4].upper()}'


def generate_exception_no() -> str:
    return f'EXCEPTION{timezone.now().strftime("%Y%m%d%H%M%S")}{uuid.uuid4().hex[:4].upper()}'


def parse_bool_param(value: str) -> bool | None:
    if value is None:
        return None
    return value.lower() == 'true'
