import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'construction_material.settings')
django.setup()

from material_management.models import MaterialStock, MaterialUsage
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal
from django.db.models import Sum

stocks = MaterialStock.objects.filter(quantity__gt=0)
print(f'库存总数: {stocks.count()}')

ninety_days_ago = timezone.now() - timedelta(days=90)
print(f'90天前: {ninety_days_ago}')

for s in stocks:
    usage_sum = MaterialUsage.objects.filter(
        material_category=s.material_category,
        zone=s.zone,
        created_at__gte=ninety_days_ago,
        status__in=['approved', 'used']
    ).aggregate(total=Sum('quantity'))['total'] or 0
    
    avg = usage_sum / Decimal('3') if usage_sum > 0 else Decimal('0')
    threshold = avg * Decimal('2') if avg > 0 else Decimal('0')
    is_overstock = s.quantity > threshold if avg > 0 else False
    
    print(f'  {s.material_category.name}: 库存={s.quantity}, 90天领用={usage_sum}, '
          f'月均={avg}, 积压阈值={threshold}, 是否积压={is_overstock}')
