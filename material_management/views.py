"""
视图层
职责：只负责接收 HTTP 请求、参数校验、调用 service/selector 层、返回响应
原则：无核心业务逻辑，只做请求/响应处理和异常转换
"""
from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from rest_framework.views import APIView
from django.core.exceptions import ValidationError

from .models import (
    UserProfile, Project, MaterialCategory, Zone, Floor,
    ResponsibilityGroup, MaterialBatch, MaterialStock,
    MaterialTransfer, MaterialUsage, ExceptionRecord,
    InventoryCheck, InventoryCheckItem, MaterialWarning
)
from .serializers import (
    UserProfileSerializer, UserCreateSerializer,
    ProjectSerializer,
    MaterialCategorySerializer, MaterialCategoryTreeSerializer,
    ZoneSerializer, ZoneTreeSerializer, ZoneDetailSerializer, ZoneMergeSerializer,
    FloorSerializer, ResponsibilityGroupSerializer,
    MaterialBatchSerializer, MaterialBatchInboundSerializer,
    MaterialStockSerializer,
    MaterialTransferSerializer,
    MaterialUsageSerializer,
    ExceptionRecordSerializer, AuditExceptionSerializer,
    InventoryCheckSerializer, InventoryCheckDetailSerializer,
    InventoryCheckCreateSerializer,
    InventoryCheckUpdateItemsSerializer,
    AuditInventoryCheckSerializer,
    MaterialWarningSerializer, WarningProcessSerializer,
    WarningReopenSerializer, WarningDetectSerializer
)
from .permissions import IsAdmin, IsOperator, IsAuditor, IsAdminOrOperator, IsAdminOrAuditor
from .selectors import (
    get_user_profile_queryset,
    get_project_queryset,
    get_material_category_queryset,
    get_material_category_roots,
    get_zone_queryset,
    get_zone_roots,
    get_zone_stocks,
    get_floor_queryset,
    get_responsibility_group_queryset,
    get_material_batch_queryset,
    get_material_stock_queryset,
    get_material_transfer_queryset,
    get_material_usage_queryset,
    get_exception_record_queryset,
    get_dashboard_stats,
    get_or_create_current_user_profile,
    get_inventory_check_queryset,
    get_inventory_check_item_queryset,
    get_zone_stocks_for_inventory,
    get_material_warning_queryset,
)
from .services import (
    calculate_zone_level,
    update_zone,
    move_zone,
    merge_zones,
    disable_zone,
    create_material_batch,
    inbound_material_batch,
    create_material_transfer,
    confirm_material_transfer,
    cancel_material_transfer,
    create_material_usage,
    approve_material_usage,
    reject_material_usage,
    use_material,
    create_exception_record,
    audit_exception_record,
    resolve_exception_record,
    create_inventory_check,
    update_inventory_check_items,
    submit_inventory_check,
    audit_inventory_check,
    cancel_inventory_check,
    load_book_quantities,
)
from .services.warning_service import (
    run_warning_detection,
    start_processing_warning,
    process_warning,
    ignore_warning,
    reopen_warning,
    get_warning_statistics,
)


class UserViewSet(viewsets.ModelViewSet):
    queryset = UserProfile.objects.all()
    serializer_class = UserProfileSerializer
    permission_classes = [IsAdmin]

    def get_queryset(self):
        role = self.request.query_params.get('role')
        return get_user_profile_queryset(self.request, role=role)

    @action(detail=False, methods=['post'], permission_classes=[IsAdmin])
    def create_user(self, request):
        serializer = UserCreateSerializer(data=request.data)
        if serializer.is_valid():
            profile = serializer.save()
            return Response(UserProfileSerializer(profile).data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def current_user(request):
    profile = get_or_create_current_user_profile(request.user)
    return Response(UserProfileSerializer(profile).data)


class ProjectViewSet(viewsets.ModelViewSet):
    queryset = Project.objects.all()
    serializer_class = ProjectSerializer

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            permission_classes = [IsAdmin]
        else:
            permission_classes = [permissions.IsAuthenticated]
        return [permission() for permission in permission_classes]

    def get_queryset(self):
        is_active = self.request.query_params.get('is_active')
        return get_project_queryset(self.request, is_active=is_active)


class MaterialCategoryViewSet(viewsets.ModelViewSet):
    queryset = MaterialCategory.objects.all()
    serializer_class = MaterialCategorySerializer

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            permission_classes = [IsAdmin]
        else:
            permission_classes = [permissions.IsAuthenticated]
        return [permission() for permission in permission_classes]

    def get_queryset(self):
        parent = self.request.query_params.get('parent')
        is_active = self.request.query_params.get('is_active')
        return get_material_category_queryset(self.request, parent=parent, is_active=is_active)

    @action(detail=False, methods=['get'])
    def tree(self, request):
        roots = get_material_category_roots()
        serializer = MaterialCategoryTreeSerializer(roots, many=True)
        return Response(serializer.data)


class ZoneViewSet(viewsets.ModelViewSet):
    queryset = Zone.objects.all()
    serializer_class = ZoneSerializer

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy', 'move', 'merge', 'disable']:
            permission_classes = [IsAdmin]
        else:
            permission_classes = [permissions.IsAuthenticated]
        return [permission() for permission in permission_classes]

    def get_queryset(self):
        project = self.request.query_params.get('project')
        parent = self.request.query_params.get('parent')
        is_active = self.request.query_params.get('is_active')
        return get_zone_queryset(self.request, project=project, parent=parent, is_active=is_active)

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return ZoneDetailSerializer
        if self.action == 'tree':
            return ZoneTreeSerializer
        return ZoneSerializer

    def create(self, request, *args, **kwargs):
        parent_id = request.data.get('parent')
        request.data['level'] = calculate_zone_level(parent_id)
        return super().create(request, *args, **kwargs)

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        try:
            updated_zone = update_zone(instance, request.data.copy())
            return Response(ZoneSerializer(updated_zone).data)
        except ValidationError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['get'])
    def tree(self, request):
        project_id = request.query_params.get('project')
        if not project_id:
            return Response({'error': '请指定项目ID'}, status=status.HTTP_400_BAD_REQUEST)
        roots = get_zone_roots(project_id)
        serializer = ZoneTreeSerializer(roots, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'], permission_classes=[IsAdmin])
    def move(self, request, pk=None):
        zone = self.get_object()
        new_parent_id = request.data.get('new_parent')
        if new_parent_id is None:
            return Response({'error': '请指定新的父级分区'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            moved_zone = move_zone(zone, new_parent_id)
            return Response(ZoneSerializer(moved_zone).data)
        except ValidationError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Zone.DoesNotExist:
            return Response({'error': '目标分区不存在'}, status=status.HTTP_404_NOT_FOUND)

    @action(detail=False, methods=['post'], permission_classes=[IsAdmin])
    def merge(self, request):
        serializer = ZoneMergeSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        data = serializer.validated_data
        try:
            target_zone = merge_zones(data['target_zone_id'], data['source_zone_ids'])
            return Response({'message': '合并成功', 'target_zone': ZoneSerializer(target_zone).data})
        except ValidationError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Zone.DoesNotExist:
            return Response({'error': '目标分区不存在'}, status=status.HTTP_404_NOT_FOUND)

    @action(detail=True, methods=['post'], permission_classes=[IsAdmin])
    def disable(self, request, pk=None):
        zone = self.get_object()
        disabled_zone = disable_zone(zone)
        return Response(ZoneSerializer(disabled_zone).data)

    @action(detail=True, methods=['get'])
    def statistics(self, request, pk=None):
        zone = self.get_object()
        return Response(zone.get_statistics())

    @action(detail=True, methods=['get'])
    def stocks(self, request, pk=None):
        zone = self.get_object()
        stocks = get_zone_stocks(zone)
        serializer = MaterialStockSerializer(stocks, many=True)
        return Response(serializer.data)


class FloorViewSet(viewsets.ModelViewSet):
    queryset = Floor.objects.all()
    serializer_class = FloorSerializer

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            permission_classes = [IsAdmin]
        else:
            permission_classes = [permissions.IsAuthenticated]
        return [permission() for permission in permission_classes]

    def get_queryset(self):
        project = self.request.query_params.get('project')
        is_active = self.request.query_params.get('is_active')
        return get_floor_queryset(self.request, project=project, is_active=is_active)


class ResponsibilityGroupViewSet(viewsets.ModelViewSet):
    queryset = ResponsibilityGroup.objects.all()
    serializer_class = ResponsibilityGroupSerializer

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            permission_classes = [IsAdmin]
        else:
            permission_classes = [permissions.IsAuthenticated]
        return [permission() for permission in permission_classes]

    def get_queryset(self):
        project = self.request.query_params.get('project')
        return get_responsibility_group_queryset(self.request, project=project)


class MaterialBatchViewSet(viewsets.ModelViewSet):
    queryset = MaterialBatch.objects.all()
    serializer_class = MaterialBatchSerializer

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy', 'inbound']:
            permission_classes = [IsAdminOrOperator]
        else:
            permission_classes = [permissions.IsAuthenticated]
        return [permission() for permission in permission_classes]

    def get_queryset(self):
        project = self.request.query_params.get('project')
        material_category = self.request.query_params.get('material_category')
        status_filter = self.request.query_params.get('status')
        return get_material_batch_queryset(
            self.request,
            project=project,
            material_category=material_category,
            status=status_filter
        )

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            batch = create_material_batch(serializer.validated_data, request.user)
            return Response(MaterialBatchSerializer(batch).data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'], permission_classes=[IsAdminOrOperator])
    def inbound(self, request, pk=None):
        batch = self.get_object()
        serializer = MaterialBatchInboundSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        data = serializer.validated_data
        try:
            updated_batch, stock = inbound_material_batch(
                batch,
                zone_id=data['zone'],
                quantity=data['quantity'],
                floor_id=data.get('floor')
            )
            return Response({
                'message': '入库成功',
                'batch': MaterialBatchSerializer(updated_batch).data,
                'stock': MaterialStockSerializer(stock).data
            })
        except ValidationError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Zone.DoesNotExist:
            return Response({'error': '分区不存在'}, status=status.HTTP_404_NOT_FOUND)
        except Floor.DoesNotExist:
            return Response({'error': '楼层不存在'}, status=status.HTTP_404_NOT_FOUND)


class MaterialStockViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = MaterialStock.objects.all()
    serializer_class = MaterialStockSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        zone = self.request.query_params.get('zone')
        material_category = self.request.query_params.get('material_category')
        project = self.request.query_params.get('project')
        return get_material_stock_queryset(
            self.request,
            zone=zone,
            material_category=material_category,
            project=project
        )


class MaterialTransferViewSet(viewsets.ModelViewSet):
    queryset = MaterialTransfer.objects.all()
    serializer_class = MaterialTransferSerializer

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            permission_classes = [IsAdminOrOperator]
        elif self.action in ['confirm', 'cancel']:
            permission_classes = [IsAdminOrOperator]
        else:
            permission_classes = [permissions.IsAuthenticated]
        return [permission() for permission in permission_classes]

    def get_queryset(self):
        from_zone = self.request.query_params.get('from_zone')
        to_zone = self.request.query_params.get('to_zone')
        status_filter = self.request.query_params.get('status')
        return get_material_transfer_queryset(
            self.request,
            from_zone=from_zone,
            to_zone=to_zone,
            status=status_filter
        )

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            transfer = create_material_transfer(serializer.validated_data, request.user)
            return Response(MaterialTransferSerializer(transfer).data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'])
    def confirm(self, request, pk=None):
        transfer = self.get_object()
        try:
            confirmed_transfer = confirm_material_transfer(transfer, request.user)
            return Response(MaterialTransferSerializer(confirmed_transfer).data)
        except ValidationError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        transfer = self.get_object()
        try:
            cancelled_transfer = cancel_material_transfer(transfer)
            return Response(MaterialTransferSerializer(cancelled_transfer).data)
        except ValidationError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


class MaterialUsageViewSet(viewsets.ModelViewSet):
    queryset = MaterialUsage.objects.all()
    serializer_class = MaterialUsageSerializer

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy', 'use']:
            permission_classes = [IsAdminOrOperator]
        elif self.action in ['approve', 'reject']:
            permission_classes = [IsAdminOrAuditor]
        else:
            permission_classes = [permissions.IsAuthenticated]
        return [permission() for permission in permission_classes]

    def get_queryset(self):
        project = self.request.query_params.get('project')
        zone = self.request.query_params.get('zone')
        status_filter = self.request.query_params.get('status')
        return get_material_usage_queryset(
            self.request,
            project=project,
            zone=zone,
            status=status_filter
        )

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            usage = create_material_usage(serializer.validated_data, request.user)
            return Response(MaterialUsageSerializer(usage).data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        usage = self.get_object()
        try:
            approved_usage = approve_material_usage(usage, request.user)
            return Response(MaterialUsageSerializer(approved_usage).data)
        except ValidationError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        usage = self.get_object()
        try:
            rejected_usage = reject_material_usage(
                usage,
                request.user,
                remark=request.data.get('remark')
            )
            return Response(MaterialUsageSerializer(rejected_usage).data)
        except ValidationError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'])
    def use(self, request, pk=None):
        usage = self.get_object()
        try:
            used_usage = use_material(usage, request.user)
            return Response(MaterialUsageSerializer(used_usage).data)
        except ValidationError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


class ExceptionRecordViewSet(viewsets.ModelViewSet):
    queryset = ExceptionRecord.objects.all()
    serializer_class = ExceptionRecordSerializer

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            permission_classes = [IsAdminOrOperator]
        elif self.action in ['audit', 'resolve']:
            permission_classes = [IsAdminOrAuditor]
        else:
            permission_classes = [permissions.IsAuthenticated]
        return [permission() for permission in permission_classes]

    def get_queryset(self):
        project = self.request.query_params.get('project')
        zone = self.request.query_params.get('zone')
        status_filter = self.request.query_params.get('status')
        exception_type = self.request.query_params.get('type')
        return get_exception_record_queryset(
            self.request,
            project=project,
            zone=zone,
            status=status_filter,
            exception_type=exception_type
        )

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            record = create_exception_record(serializer.validated_data, request.user)
            return Response(ExceptionRecordSerializer(record).data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'])
    def audit(self, request, pk=None):
        exception = self.get_object()
        serializer = AuditExceptionSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        data = serializer.validated_data
        audited_exception = audit_exception_record(
            exception,
            request.user,
            status=data['status'],
            handling_suggestion=data.get('handling_suggestion'),
            handling_result=data.get('handling_result')
        )
        return Response(ExceptionRecordSerializer(audited_exception).data)

    @action(detail=True, methods=['post'])
    def resolve(self, request, pk=None):
        exception = self.get_object()
        try:
            resolved_exception = resolve_exception_record(
                exception,
                request.user,
                handling_result=request.data.get('handling_result')
            )
            return Response(ExceptionRecordSerializer(resolved_exception).data)
        except ValidationError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


class DashboardView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        project_id = request.query_params.get('project')
        stats = get_dashboard_stats(project_id)
        return Response(stats)


class InventoryCheckViewSet(viewsets.ModelViewSet):
    queryset = InventoryCheck.objects.all()
    serializer_class = InventoryCheckSerializer

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy', 'update_items', 'submit', 'cancel']:
            permission_classes = [IsAdminOrOperator]
        elif self.action in ['audit']:
            permission_classes = [IsAdminOrAuditor]
        else:
            permission_classes = [permissions.IsAuthenticated]
        return [permission() for permission in permission_classes]

    def get_queryset(self):
        project = self.request.query_params.get('project')
        zone = self.request.query_params.get('zone')
        status_filter = self.request.query_params.get('status')
        return get_inventory_check_queryset(
            self.request,
            project=project,
            zone=zone,
            status=status_filter
        )

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return InventoryCheckDetailSerializer
        return InventoryCheckSerializer

    def create(self, request, *args, **kwargs):
        serializer = InventoryCheckCreateSerializer(data=request.data)
        if serializer.is_valid():
            inventory_check = create_inventory_check(serializer.validated_data, request.user)
            return Response(InventoryCheckSerializer(inventory_check).data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'], permission_classes=[IsAdminOrOperator])
    def update_items(self, request, pk=None):
        inventory_check = self.get_object()
        serializer = InventoryCheckUpdateItemsSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        data = serializer.validated_data
        try:
            updated_check = update_inventory_check_items(
                inventory_check,
                data['items']
            )
            return Response(InventoryCheckDetailSerializer(updated_check).data)
        except ValidationError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'], permission_classes=[IsAdminOrOperator])
    def submit(self, request, pk=None):
        inventory_check = self.get_object()
        try:
            submitted_check = submit_inventory_check(
                inventory_check,
                request.user,
                handling_opinion=request.data.get('handling_opinion')
            )
            return Response(InventoryCheckDetailSerializer(submitted_check).data)
        except ValidationError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'], permission_classes=[IsAdminOrAuditor])
    def audit(self, request, pk=None):
        inventory_check = self.get_object()
        serializer = AuditInventoryCheckSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        data = serializer.validated_data
        try:
            audited_check = audit_inventory_check(
                inventory_check,
                request.user,
                status=data['status'],
                audit_opinion=data.get('audit_opinion')
            )
            return Response(InventoryCheckDetailSerializer(audited_check).data)
        except ValidationError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'], permission_classes=[IsAdminOrOperator])
    def cancel(self, request, pk=None):
        inventory_check = self.get_object()
        try:
            cancelled_check = cancel_inventory_check(
                inventory_check,
                request.user
            )
            return Response(InventoryCheckDetailSerializer(cancelled_check).data)
        except ValidationError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['get'])
    def load_books(self, request):
        zone_id = request.query_params.get('zone')
        floor_id = request.query_params.get('floor')
        if not zone_id:
            return Response({'error': '请指定分区ID'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            zone = Zone.objects.get(id=zone_id)
            floor = None
            if floor_id:
                floor = Floor.objects.get(id=floor_id)
            book_quantities = load_book_quantities(zone, floor)
            return Response(book_quantities)
        except Zone.DoesNotExist:
            return Response({'error': '分区不存在'}, status=status.HTTP_404_NOT_FOUND)
        except Floor.DoesNotExist:
            return Response({'error': '楼层不存在'}, status=status.HTTP_404_NOT_FOUND)
        except ValidationError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


class MaterialWarningViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = MaterialWarning.objects.all()
    serializer_class = MaterialWarningSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        project = self.request.query_params.get('project')
        zone = self.request.query_params.get('zone')
        material_category = self.request.query_params.get('material_category')
        status_filter = self.request.query_params.get('status')
        warning_type = self.request.query_params.get('warning_type')
        priority = self.request.query_params.get('priority')
        return get_material_warning_queryset(
            self.request,
            project=project,
            zone=zone,
            material_category=material_category,
            status=status_filter,
            warning_type=warning_type,
            priority=priority
        )

    @action(detail=False, methods=['post'], permission_classes=[IsAdminOrOperator])
    def detect(self, request):
        serializer = WarningDetectSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        data = serializer.validated_data
        result = run_warning_detection(
            project_id=data.get('project'),
            user=request.user
        )
        return Response({
            'message': '预警检测完成',
            **result
        })

    @action(detail=True, methods=['post'], permission_classes=[IsAdminOrOperator])
    def start_processing(self, request, pk=None):
        warning = self.get_object()
        serializer = WarningProcessSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        data = serializer.validated_data
        try:
            updated_warning = start_processing_warning(
                warning,
                request.user,
                handling_opinion=data.get('handling_opinion'),
                responsible_person_id=data.get('responsible_person')
            )
            return Response(MaterialWarningSerializer(updated_warning).data)
        except ValidationError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'], permission_classes=[IsAdminOrOperator])
    def process(self, request, pk=None):
        warning = self.get_object()
        serializer = WarningProcessSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        data = serializer.validated_data
        if not data.get('handling_result'):
            return Response({'error': '请填写处理结果'}, status=status.HTTP_400_BAD_REQUEST)
        
        if data.get('force_close') and not IsAdminOrAuditor().has_permission(request, self):
            return Response({'error': '只有管理员或审核员可以强制关闭预警'}, status=status.HTTP_403_FORBIDDEN)
        
        try:
            updated_warning = process_warning(
                warning,
                request.user,
                handling_result=data['handling_result'],
                handling_opinion=data.get('handling_opinion'),
                responsible_person_id=data.get('responsible_person'),
                force_close=data.get('force_close', False),
                related_usage_id=data.get('related_usage'),
                related_exception_id=data.get('related_exception'),
                related_inventory_check_id=data.get('related_inventory_check')
            )
            return Response(MaterialWarningSerializer(updated_warning).data)
        except ValidationError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'], permission_classes=[IsAdminOrAuditor])
    def ignore(self, request, pk=None):
        warning = self.get_object()
        serializer = WarningReopenSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        data = serializer.validated_data
        try:
            updated_warning = ignore_warning(
                warning,
                request.user,
                handling_opinion=data.get('handling_opinion')
            )
            return Response(MaterialWarningSerializer(updated_warning).data)
        except ValidationError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'], permission_classes=[IsAdminOrAuditor])
    def reopen(self, request, pk=None):
        warning = self.get_object()
        serializer = WarningReopenSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        data = serializer.validated_data
        try:
            updated_warning = reopen_warning(
                warning,
                request.user,
                handling_opinion=data.get('handling_opinion')
            )
            return Response(MaterialWarningSerializer(updated_warning).data)
        except ValidationError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['get'])
    def statistics(self, request):
        project_id = request.query_params.get('project')
        stats = get_warning_statistics(project_id)
        return Response(stats)


class WarningDashboardView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        project_id = request.query_params.get('project')
        warning_stats = get_warning_statistics(project_id)
        dashboard_stats = get_dashboard_stats(project_id)
        return Response({
            **dashboard_stats,
            'warning_stats': warning_stats
        })
