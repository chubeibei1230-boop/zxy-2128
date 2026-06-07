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
    safety_threshold = models.DecimalField(max_digits=15, decimal_places=2, default=10, verbose_name='安全库存阈值')
    shelf_life_days = models.IntegerField(default=180, verbose_name='保质期(天)')
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
        warning_count = MaterialWarning.objects.filter(zone_id__in=all_zone_ids, status__in=['pending', 'processing']).count()
        return {
            'total_quantity': total_quantity,
            'usage_count': usage_count,
            'exception_count': exception_count,
            'warning_count': warning_count,
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
    production_date = models.DateField(blank=True, null=True, verbose_name='生产日期')
    inbound_date = models.DateField(blank=True, null=True, verbose_name='入库日期')
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


class InventoryCheck(models.Model):
    STATUS_CHOICES = (
        ('draft', '草稿'),
        ('submitted', '待审核'),
        ('approved', '审核通过'),
        ('rejected', '审核拒绝'),
        ('cancelled', '已取消'),
    )
    check_no = models.CharField(max_length=100, unique=True, verbose_name='盘点单号')
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='inventory_checks', verbose_name='所属项目')
    zone = models.ForeignKey(Zone, on_delete=models.CASCADE, related_name='inventory_checks', verbose_name='盘点分区')
    floor = models.ForeignKey(Floor, on_delete=models.SET_NULL, null=True, blank=True, related_name='inventory_checks', verbose_name='盘点楼层')
    check_range = models.TextField(blank=True, null=True, verbose_name='盘点范围说明')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft', verbose_name='状态')
    handling_opinion = models.TextField(blank=True, null=True, verbose_name='处理意见')
    audit_opinion = models.TextField(blank=True, null=True, verbose_name='审核意见')
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_inventory_checks', verbose_name='盘点人')
    checked_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='checked_inventory_checks', verbose_name='复盘人')
    audited_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='audited_inventory_checks', verbose_name='审核人')
    check_date = models.DateField(verbose_name='盘点日期')
    created_at = models.DateTimeField(auto_now_add=True)
    checked_at = models.DateTimeField(null=True, blank=True)
    audited_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'inventory_check'
        ordering = ['-created_at']

    def __str__(self):
        return self.check_no


class InventoryCheckItem(models.Model):
    DIFF_TYPE_CHOICES = (
        ('no_diff', '无差异'),
        ('overage', '盘盈'),
        ('shortage', '盘亏'),
    )
    inventory_check = models.ForeignKey(InventoryCheck, on_delete=models.CASCADE, related_name='items', verbose_name='关联盘点单')
    material_category = models.ForeignKey(MaterialCategory, on_delete=models.CASCADE, related_name='inventory_check_items', verbose_name='材料类别')
    material_batch = models.ForeignKey(MaterialBatch, on_delete=models.CASCADE, related_name='inventory_check_items', verbose_name='材料批次')
    book_quantity = models.DecimalField(max_digits=15, decimal_places=2, verbose_name='账面数量')
    actual_quantity = models.DecimalField(max_digits=15, decimal_places=2, verbose_name='实盘数量')
    diff_quantity = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name='差异数量')
    diff_type = models.CharField(max_length=20, choices=DIFF_TYPE_CHOICES, default='no_diff', verbose_name='差异类型')
    remark = models.TextField(blank=True, null=True, verbose_name='备注')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'inventory_check_item'
        ordering = ['id']

    def __str__(self):
        return f'{self.inventory_check.check_no} - {self.material_category.name}'

    def save(self, *args, **kwargs):
        self.diff_quantity = self.actual_quantity - self.book_quantity
        if self.diff_quantity > 0:
            self.diff_type = 'overage'
        elif self.diff_quantity < 0:
            self.diff_type = 'shortage'
        else:
            self.diff_type = 'no_diff'
        super().save(*args, **kwargs)


class MaterialWarning(models.Model):
    TYPE_CHOICES = (
        ('low_stock', '低库存预警'),
        ('expiring', '临期预警'),
        ('long_unused', '长期未使用预警'),
        ('overstock', '库存积压预警'),
    )
    STATUS_CHOICES = (
        ('pending', '待处理'),
        ('processing', '处理中'),
        ('processed', '已处理'),
        ('ignored', '已忽略'),
    )
    PRIORITY_CHOICES = (
        ('low', '低'),
        ('medium', '中'),
        ('high', '高'),
        ('urgent', '紧急'),
    )
    warning_no = models.CharField(max_length=100, unique=True, verbose_name='预警编号')
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='warnings', verbose_name='所属项目')
    zone = models.ForeignKey(Zone, on_delete=models.CASCADE, related_name='warnings', verbose_name='所属分区')
    floor = models.ForeignKey(Floor, on_delete=models.SET_NULL, null=True, blank=True, related_name='warnings', verbose_name='楼层位置')
    material_category = models.ForeignKey(MaterialCategory, on_delete=models.CASCADE, related_name='warnings', verbose_name='材料类别')
    material_batch = models.ForeignKey(MaterialBatch, on_delete=models.CASCADE, related_name='warnings', verbose_name='材料批次')
    material_stock = models.ForeignKey(MaterialStock, on_delete=models.SET_NULL, null=True, blank=True, related_name='warnings', verbose_name='关联库存')
    warning_type = models.CharField(max_length=50, choices=TYPE_CHOICES, verbose_name='预警类型')
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default='medium', verbose_name='优先级')
    description = models.TextField(verbose_name='预警描述')
    current_quantity = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name='当前数量')
    threshold_quantity = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name='阈值数量')
    warning_days = models.IntegerField(default=0, verbose_name='预警天数')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', verbose_name='状态')
    handling_opinion = models.TextField(blank=True, null=True, verbose_name='处理意见')
    handling_result = models.TextField(blank=True, null=True, verbose_name='处理结果')
    related_usage = models.ForeignKey(MaterialUsage, on_delete=models.SET_NULL, null=True, blank=True, related_name='warnings', verbose_name='关联领用单')
    related_exception = models.ForeignKey(ExceptionRecord, on_delete=models.SET_NULL, null=True, blank=True, related_name='warnings', verbose_name='关联异常单')
    related_inventory_check = models.ForeignKey(InventoryCheck, on_delete=models.SET_NULL, null=True, blank=True, related_name='warnings', verbose_name='关联盘点单')
    responsible_person = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='responsible_warnings', verbose_name='责任人')
    force_close = models.BooleanField(default=False, verbose_name='是否强制关闭')
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_warnings', verbose_name='创建人')
    handled_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='handled_warnings', verbose_name='处理人')
    created_at = models.DateTimeField(auto_now_add=True)
    handled_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'material_warning'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.warning_no} - {self.get_warning_type_display()}'

    def get_project_statistics(self):
        warnings = MaterialWarning.objects.filter(project=self.project)
        total = warnings.count()
        pending = warnings.filter(status='pending').count()
        processing = warnings.filter(status='processing').count()
        processed = warnings.filter(status='processed').count()
        ignored = warnings.filter(status='ignored').count()
        return {
            'total': total,
            'pending': pending,
            'processing': processing,
            'processed': processed,
            'ignored': ignored,
            'completion_rate': round((processed + ignored) / total * 100, 2) if total > 0 else 0
        }


class WarningProcessLog(models.Model):
    ACTION_CHOICES = (
        ('create', '创建预警'),
        ('assign', '指派责任人'),
        ('start_process', '开始处理'),
        ('update_opinion', '更新处理意见'),
        ('relate_usage', '关联领用单'),
        ('relate_exception', '关联异常单'),
        ('relate_inventory', '关联盘点单'),
        ('auto_close', '自动闭环'),
        ('auto_reopen', '自动恢复待处理'),
        ('process', '标记已处理'),
        ('force_close', '强制关闭'),
        ('ignore', '忽略'),
        ('reopen', '重新打开'),
    )
    warning = models.ForeignKey(MaterialWarning, on_delete=models.CASCADE, related_name='process_logs', verbose_name='关联预警')
    action = models.CharField(max_length=50, choices=ACTION_CHOICES, verbose_name='操作类型')
    action_detail = models.TextField(blank=True, null=True, verbose_name='操作详情')
    old_status = models.CharField(max_length=20, blank=True, null=True, verbose_name='变更前状态')
    new_status = models.CharField(max_length=20, blank=True, null=True, verbose_name='变更后状态')
    remark = models.TextField(blank=True, null=True, verbose_name='备注')
    related_usage = models.ForeignKey(MaterialUsage, on_delete=models.SET_NULL, null=True, blank=True, verbose_name='关联领用单')
    related_exception = models.ForeignKey(ExceptionRecord, on_delete=models.SET_NULL, null=True, blank=True, verbose_name='关联异常单')
    related_inventory_check = models.ForeignKey(InventoryCheck, on_delete=models.SET_NULL, null=True, blank=True, verbose_name='关联盘点单')
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='warning_logs', verbose_name='操作人')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='操作时间')

    class Meta:
        db_table = 'warning_process_log'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.warning.warning_no} - {self.get_action_display()}'
