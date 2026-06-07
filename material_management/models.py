from django.db import models
from django.contrib.auth.models import User
from django.db.models import Sum, Count
from django.utils import timezone


class UserProfile(models.Model):
    ROLE_CHOICES = (
        ('admin', '管理员'),
        ('operator', '操作员'),
        ('auditor', '审核员'),
    )
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='operator')
    phone = models.CharField(max_length=20, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'user_profile'

    def __str__(self):
        return f'{self.user.username} - {self.get_role_display()}'


class Project(models.Model):
    name = models.CharField(max_length=200, verbose_name='项目名称')
    description = models.TextField(blank=True, null=True, verbose_name='项目描述')
    address = models.CharField(max_length=500, blank=True, null=True, verbose_name='项目地址')
    start_date = models.DateField(blank=True, null=True, verbose_name='开始日期')
    end_date = models.DateField(blank=True, null=True, verbose_name='结束日期')
    is_active = models.BooleanField(default=True, verbose_name='是否启用')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'project'
        ordering = ['-created_at']

    def __str__(self):
        return self.name


class MaterialCategory(models.Model):
    name = models.CharField(max_length=200, verbose_name='类别名称')
    code = models.CharField(max_length=50, unique=True, verbose_name='类别编码')
    parent = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='children', verbose_name='父级类别')
    unit = models.CharField(max_length=20, verbose_name='计量单位')
    description = models.TextField(blank=True, null=True, verbose_name='描述')
    is_active = models.BooleanField(default=True, verbose_name='是否启用')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'material_category'
        ordering = ['code']

    def __str__(self):
        return f'{self.code} - {self.name}'


class Zone(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='zones', verbose_name='所属项目')
    name = models.CharField(max_length=200, verbose_name='分区名称')
    code = models.CharField(max_length=50, verbose_name='分区编码')
    parent = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='children', verbose_name='父级分区')
    level = models.IntegerField(default=1, verbose_name='层级')
    sort_order = models.IntegerField(default=0, verbose_name='排序')
    description = models.TextField(blank=True, null=True, verbose_name='描述')
    is_active = models.BooleanField(default=True, verbose_name='是否启用')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'zone'
        unique_together = [['project', 'code']]
        ordering = ['project', 'level', 'sort_order']

    def __str__(self):
        return f'{self.code} - {self.name}'

    def get_all_children(self):
        children = []
        for child in self.children.filter(is_active=True):
            children.append(child)
            children.extend(child.get_all_children())
        return children

    def get_all_child_ids(self):
        ids = [self.id]
        for child in self.children.filter(is_active=True):
            ids.extend(child.get_all_child_ids())
        return ids

    def get_statistics(self):
        all_zone_ids = self.get_all_child_ids()
        stocks = MaterialStock.objects.filter(zone_id__in=all_zone_ids)
        total_quantity = stocks.aggregate(total=Sum('quantity'))['total'] or 0
        usage_count = MaterialUsage.objects.filter(zone_id__in=all_zone_ids).count()
        exception_count = ExceptionRecord.objects.filter(zone_id__in=all_zone_ids, status='pending').count()
        return {
            'total_quantity': total_quantity,
            'usage_count': usage_count,
            'exception_count': exception_count,
            'sub_zone_count': self.children.filter(is_active=True).count()
        }


class Floor(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='floors', verbose_name='所属项目')
    name = models.CharField(max_length=100, verbose_name='楼层名称')
    code = models.CharField(max_length=50, verbose_name='楼层编码')
    sort_order = models.IntegerField(default=0, verbose_name='排序')
    is_active = models.BooleanField(default=True, verbose_name='是否启用')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'floor'
        unique_together = [['project', 'code']]
        ordering = ['project', 'sort_order']

    def __str__(self):
        return f'{self.code} - {self.name}'


class ResponsibilityGroup(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='groups', verbose_name='所属项目')
    name = models.CharField(max_length=200, verbose_name='小组名称')
    leader = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='leading_groups', verbose_name='组长')
    members = models.ManyToManyField(User, blank=True, related_name='responsibility_groups', verbose_name='成员')
    description = models.TextField(blank=True, null=True, verbose_name='描述')
    is_active = models.BooleanField(default=True, verbose_name='是否启用')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'responsibility_group'
        ordering = ['-created_at']

    def __str__(self):
        return self.name


class MaterialBatch(models.Model):
    STATUS_CHOICES = (
        ('pending', '待入库'),
        ('in_stock', '已入库'),
        ('partial', '部分入库'),
    )
    batch_no = models.CharField(max_length=100, unique=True, verbose_name='批次号')
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='batches', verbose_name='所属项目')
    material_category = models.ForeignKey(MaterialCategory, on_delete=models.CASCADE, related_name='batches', verbose_name='材料类别')
    supplier = models.CharField(max_length=200, blank=True, null=True, verbose_name='供应商')
    total_quantity = models.DecimalField(max_digits=15, decimal_places=2, verbose_name='总数量')
    received_quantity = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name='已入库数量')
    unit_price = models.DecimalField(max_digits=15, decimal_places=2, blank=True, null=True, verbose_name='单价')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', verbose_name='状态')
    remark = models.TextField(blank=True, null=True, verbose_name='备注')
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_batches', verbose_name='创建人')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'material_batch'
        ordering = ['-created_at']

    def __str__(self):
        return self.batch_no


class MaterialStock(models.Model):
    zone = models.ForeignKey(Zone, on_delete=models.CASCADE, related_name='stocks', verbose_name='所属分区')
    floor = models.ForeignKey(Floor, on_delete=models.SET_NULL, null=True, blank=True, related_name='stocks', verbose_name='楼层位置')
    material_category = models.ForeignKey(MaterialCategory, on_delete=models.CASCADE, related_name='stocks', verbose_name='材料类别')
    material_batch = models.ForeignKey(MaterialBatch, on_delete=models.CASCADE, related_name='stock_items', verbose_name='所属批次')
    quantity = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name='库存数量')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'material_stock'
        unique_together = [['zone', 'material_category', 'material_batch', 'floor']]
        ordering = ['-updated_at']

    def __str__(self):
        return f'{self.zone.name} - {self.material_category.name}: {self.quantity}'


class MaterialTransfer(models.Model):
    STATUS_CHOICES = (
        ('pending', '待确认'),
        ('completed', '已完成'),
        ('cancelled', '已取消'),
    )
    transfer_no = models.CharField(max_length=100, unique=True, verbose_name='转移单号')
    from_zone = models.ForeignKey(Zone, on_delete=models.CASCADE, related_name='out_transfers', verbose_name='源分区')
    to_zone = models.ForeignKey(Zone, on_delete=models.CASCADE, related_name='in_transfers', verbose_name='目标分区')
    from_floor = models.ForeignKey(Floor, on_delete=models.SET_NULL, null=True, blank=True, related_name='out_transfers', verbose_name='源楼层')
    to_floor = models.ForeignKey(Floor, on_delete=models.SET_NULL, null=True, blank=True, related_name='in_transfers', verbose_name='目标楼层')
    material_category = models.ForeignKey(MaterialCategory, on_delete=models.CASCADE, related_name='transfers', verbose_name='材料类别')
    material_batch = models.ForeignKey(MaterialBatch, on_delete=models.CASCADE, related_name='transfers', verbose_name='材料批次')
    quantity = models.DecimalField(max_digits=15, decimal_places=2, verbose_name='转移数量')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', verbose_name='状态')
    remark = models.TextField(blank=True, null=True, verbose_name='备注')
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_transfers', verbose_name='创建人')
    confirmed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='confirmed_transfers', verbose_name='确认人')
    created_at = models.DateTimeField(auto_now_add=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'material_transfer'
        ordering = ['-created_at']

    def __str__(self):
        return self.transfer_no


class MaterialUsage(models.Model):
    STATUS_CHOICES = (
        ('pending', '待审核'),
        ('approved', '已通过'),
        ('rejected', '已拒绝'),
        ('used', '已领用'),
    )
    usage_no = models.CharField(max_length=100, unique=True, verbose_name='领用单号')
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='usages', verbose_name='所属项目')
    zone = models.ForeignKey(Zone, on_delete=models.CASCADE, related_name='usages', verbose_name='领用分区')
    floor = models.ForeignKey(Floor, on_delete=models.SET_NULL, null=True, blank=True, related_name='usages', verbose_name='使用楼层')
    material_category = models.ForeignKey(MaterialCategory, on_delete=models.CASCADE, related_name='usages', verbose_name='材料类别')
    material_batch = models.ForeignKey(MaterialBatch, on_delete=models.CASCADE, related_name='usages', verbose_name='材料批次')
    quantity = models.DecimalField(max_digits=15, decimal_places=2, verbose_name='领用数量')
    responsibility_group = models.ForeignKey(ResponsibilityGroup, on_delete=models.SET_NULL, null=True, blank=True, related_name='usages', verbose_name='责任小组')
    purpose = models.TextField(blank=True, null=True, verbose_name='用途说明')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', verbose_name='状态')
    remark = models.TextField(blank=True, null=True, verbose_name='备注')
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_usages', verbose_name='申请人')
    approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_usages', verbose_name='审核人')
    used_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='used_usages', verbose_name='领用人')
    created_at = models.DateTimeField(auto_now_add=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    used_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'material_usage'
        ordering = ['-created_at']

    def __str__(self):
        return self.usage_no


class ExceptionRecord(models.Model):
    TYPE_CHOICES = (
        ('shortage', '库存不足'),
        ('damage', '材料损坏'),
        ('quality', '质量问题'),
        ('overage', '数量过剩'),
        ('other', '其他异常'),
    )
    STATUS_CHOICES = (
        ('pending', '待复核'),
        ('processing', '处理中'),
        ('resolved', '已解决'),
        ('closed', '已关闭'),
    )
    exception_no = models.CharField(max_length=100, unique=True, verbose_name='异常编号')
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='exceptions', verbose_name='所属项目')
    zone = models.ForeignKey(Zone, on_delete=models.CASCADE, related_name='exceptions', verbose_name='所属分区')
    floor = models.ForeignKey(Floor, on_delete=models.SET_NULL, null=True, blank=True, related_name='exceptions', verbose_name='楼层位置')
    material_category = models.ForeignKey(MaterialCategory, on_delete=models.CASCADE, related_name='exceptions', verbose_name='材料类别')
    material_batch = models.ForeignKey(MaterialBatch, on_delete=models.SET_NULL, null=True, blank=True, related_name='exceptions', verbose_name='材料批次')
    exception_type = models.CharField(max_length=50, choices=TYPE_CHOICES, verbose_name='异常类型')
    description = models.TextField(verbose_name='异常描述')
    quantity = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name='涉及数量')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', verbose_name='状态')
    handling_suggestion = models.TextField(blank=True, null=True, verbose_name='处理建议')
    handling_result = models.TextField(blank=True, null=True, verbose_name='处理结果')
    reported_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='reported_exceptions', verbose_name='上报人')
    audited_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='audited_exceptions', verbose_name='复核人')
    handled_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='handled_exceptions', verbose_name='处理人')
    created_at = models.DateTimeField(auto_now_add=True)
    audited_at = models.DateTimeField(null=True, blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'exception_record'
        ordering = ['-created_at']

    def __str__(self):
        return self.exception_no
