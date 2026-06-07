from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from rest_framework.views import APIView
from django.contrib.auth.models import User
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone
import uuid

from .models import (
    UserProfile, Project, MaterialCategory, Zone, Floor,
    ResponsibilityGroup, MaterialBatch, MaterialStock,
    MaterialTransfer, MaterialUsage, ExceptionRecord
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
    ExceptionRecordSerializer, AuditExceptionSerializer
)
from .permissions import IsAdmin, IsOperator, IsAuditor, IsAdminOrOperator, IsAdminOrAuditor


class UserViewSet(viewsets.ModelViewSet):
    queryset = UserProfile.objects.all()
    serializer_class = UserProfileSerializer
    permission_classes = [IsAdmin]

    def get_queryset(self):
        queryset = UserProfile.objects.select_related('user').all()
        role = self.request.query_params.get('role')
        if role:
            queryset = queryset.filter(role=role)
        return queryset

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
    profile, _ = UserProfile.objects.get_or_create(user=request.user, defaults={'role': 'operator'})
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
        queryset = Project.objects.all()
        is_active = self.request.query_params.get('is_active')
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active.lower() == 'true')
        return queryset


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
        queryset = MaterialCategory.objects.all()
        parent = self.request.query_params.get('parent')
        if parent is not None:
            if parent == 'null':
                queryset = queryset.filter(parent__isnull=True)
            else:
                queryset = queryset.filter(parent_id=parent)
        is_active = self.request.query_params.get('is_active')
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active.lower() == 'true')
        return queryset

    @action(detail=False, methods=['get'])
    def tree(self, request):
        roots = MaterialCategory.objects.filter(parent__isnull=True, is_active=True)
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
        queryset = Zone.objects.select_related('project', 'parent').all()
        project = self.request.query_params.get('project')
        if project:
            queryset = queryset.filter(project_id=project)
        parent = self.request.query_params.get('parent')
        if parent is not None:
            if parent == 'null':
                queryset = queryset.filter(parent__isnull=True)
            else:
                queryset = queryset.filter(parent_id=parent)
        is_active = self.request.query_params.get('is_active')
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active.lower() == 'true')
        return queryset

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return ZoneDetailSerializer
        if self.action == 'tree':
            return ZoneTreeSerializer
        return ZoneSerializer

    def create(self, request, *args, **kwargs):
        parent_id = request.data.get('parent')
        level = 1
        if parent_id:
            try:
                parent = Zone.objects.get(id=parent_id)
                level = parent.level + 1
            except Zone.DoesNotExist:
                pass
        request.data['level'] = level
        return super().create(request, *args, **kwargs)

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        parent_id = request.data.get('parent')
        level_changed = False
        new_level = instance.level
        if parent_id is not None:
            if parent_id == instance.id:
                return Response({'error': '不能将自己设为父级'}, status=status.HTTP_400_BAD_REQUEST)
            if parent_id:
                try:
                    parent = Zone.objects.get(id=parent_id)
                    child_ids = instance.get_all_child_ids()
                    if parent.id in child_ids:
                        return Response({'error': '不能将子分区设为父级'}, status=status.HTTP_400_BAD_REQUEST)
                    new_level = parent.level + 1
                    level_changed = True
                except Zone.DoesNotExist:
                    new_level = 1
                    level_changed = True
            else:
                new_level = 1
                level_changed = True
            request.data['level'] = new_level
        response = super().update(request, *args, **kwargs)
        if level_changed:
            instance.refresh_from_db()
            self._update_children_level(instance, instance.level)
        return response

    @action(detail=False, methods=['get'])
    def tree(self, request):
        project_id = request.query_params.get('project')
        if not project_id:
            return Response({'error': '请指定项目ID'}, status=status.HTTP_400_BAD_REQUEST)
        roots = Zone.objects.filter(project_id=project_id, parent__isnull=True, is_active=True)
        serializer = ZoneTreeSerializer(roots, many=True)
        return Response(serializer.data)

    def _update_children_level(self, zone, new_level):
        children = zone.children.all()
        for child in children:
            child.level = new_level + 1
            child.save()
            self._update_children_level(child, child.level)

    @action(detail=True, methods=['post'], permission_classes=[IsAdmin])
    def move(self, request, pk=None):
        zone = self.get_object()
        new_parent_id = request.data.get('new_parent')
        if new_parent_id is None:
            return Response({'error': '请指定新的父级分区'}, status=status.HTTP_400_BAD_REQUEST)
        if new_parent_id:
            try:
                new_parent = Zone.objects.get(id=new_parent_id)
                if new_parent.project_id != zone.project_id:
                    return Response({'error': '不能移动到其他项目'}, status=status.HTTP_400_BAD_REQUEST)
                child_ids = zone.get_all_child_ids()
                if new_parent.id in child_ids:
                    return Response({'error': '不能移动到自己的子分区下'}, status=status.HTTP_400_BAD_REQUEST)
                zone.parent = new_parent
                zone.level = new_parent.level + 1
            except Zone.DoesNotExist:
                return Response({'error': '目标分区不存在'}, status=status.HTTP_404_NOT_FOUND)
        else:
            zone.parent = None
            zone.level = 1
        zone.save()
        self._update_children_level(zone, zone.level)
        return Response(ZoneSerializer(zone).data)

    @action(detail=False, methods=['post'], permission_classes=[IsAdmin])
    def merge(self, request):
        serializer = ZoneMergeSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        data = serializer.validated_data
        target_zone_id = data['target_zone_id']
        source_zone_ids = data['source_zone_ids']
        try:
            target_zone = Zone.objects.get(id=target_zone_id)
        except Zone.DoesNotExist:
            return Response({'error': '目标分区不存在'}, status=status.HTTP_404_NOT_FOUND)
        if target_zone_id in source_zone_ids:
            return Response({'error': '目标分区不能在源分区列表中'}, status=status.HTTP_400_BAD_REQUEST)
        with transaction.atomic():
            for source_id in source_zone_ids:
                try:
                    source_zone = Zone.objects.get(id=source_id)
                    if source_zone.project_id != target_zone.project_id:
                        continue
                    source_stocks = MaterialStock.objects.filter(zone=source_zone)
                    for source_stock in source_stocks:
                        try:
                            target_stock = MaterialStock.objects.get(
                                zone=target_zone,
                                material_category=source_stock.material_category,
                                material_batch=source_stock.material_batch,
                                floor=source_stock.floor
                            )
                            target_stock.quantity += source_stock.quantity
                            target_stock.save()
                            source_stock.delete()
                        except MaterialStock.DoesNotExist:
                            source_stock.zone = target_zone
                            source_stock.save()
                    MaterialTransfer.objects.filter(from_zone=source_zone).update(from_zone=target_zone)
                    MaterialTransfer.objects.filter(to_zone=source_zone).update(to_zone=target_zone)
                    MaterialUsage.objects.filter(zone=source_zone).update(zone=target_zone)
                    ExceptionRecord.objects.filter(zone=source_zone).update(zone=target_zone)
                    Zone.objects.filter(parent=source_zone).update(parent=target_zone)
                    source_zone.is_active = False
                    source_zone.save()
                except Zone.DoesNotExist:
                    continue
        return Response({'message': '合并成功', 'target_zone': ZoneSerializer(target_zone).data})

    @action(detail=True, methods=['post'], permission_classes=[IsAdmin])
    def disable(self, request, pk=None):
        zone = self.get_object()
        zone.is_active = False
        zone.save()
        return Response(ZoneSerializer(zone).data)

    @action(detail=True, methods=['get'])
    def statistics(self, request, pk=None):
        zone = self.get_object()
        return Response(zone.get_statistics())

    @action(detail=True, methods=['get'])
    def stocks(self, request, pk=None):
        zone = self.get_object()
        all_zone_ids = zone.get_all_child_ids()
        stocks = MaterialStock.objects.filter(zone_id__in=all_zone_ids).select_related(
            'zone', 'material_category', 'material_batch', 'floor'
        )
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
        queryset = Floor.objects.all()
        project = self.request.query_params.get('project')
        if project:
            queryset = queryset.filter(project_id=project)
        is_active = self.request.query_params.get('is_active')
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active.lower() == 'true')
        return queryset


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
        queryset = ResponsibilityGroup.objects.select_related('project', 'leader').prefetch_related('members').all()
        project = self.request.query_params.get('project')
        if project:
            queryset = queryset.filter(project_id=project)
        return queryset


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
        queryset = MaterialBatch.objects.select_related('project', 'material_category', 'created_by').all()
        project = self.request.query_params.get('project')
        if project:
            queryset = queryset.filter(project_id=project)
        material_category = self.request.query_params.get('material_category')
        if material_category:
            queryset = queryset.filter(material_category_id=material_category)
        status = self.request.query_params.get('status')
        if status:
            queryset = queryset.filter(status=status)
        return queryset

    def create(self, request, *args, **kwargs):
        request.data['batch_no'] = f'BATCH{timezone.now().strftime("%Y%m%d%H%M%S")}{uuid.uuid4().hex[:4].upper()}'
        request.data['created_by'] = request.user.id
        request.data['status'] = 'pending'
        return super().create(request, *args, **kwargs)

    @action(detail=True, methods=['post'], permission_classes=[IsAdminOrOperator])
    def inbound(self, request, pk=None):
        batch = self.get_object()
        serializer = MaterialBatchInboundSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        data = serializer.validated_data
        quantity = data['quantity']
        zone_id = data['zone']
        floor_id = data.get('floor')
        if quantity <= 0:
            return Response({'error': '入库数量必须大于0'}, status=status.HTTP_400_BAD_REQUEST)
        if batch.received_quantity + quantity > batch.total_quantity:
            return Response({'error': '入库数量超过批次总数量'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            zone = Zone.objects.get(id=zone_id)
            if zone.project_id != batch.project_id:
                return Response({'error': '分区不属于该项目'}, status=status.HTTP_400_BAD_REQUEST)
        except Zone.DoesNotExist:
            return Response({'error': '分区不存在'}, status=status.HTTP_404_NOT_FOUND)
        floor = None
        if floor_id:
            try:
                floor = Floor.objects.get(id=floor_id)
                if floor.project_id != batch.project_id:
                    return Response({'error': '楼层不属于该项目'}, status=status.HTTP_400_BAD_REQUEST)
            except Floor.DoesNotExist:
                return Response({'error': '楼层不存在'}, status=status.HTTP_404_NOT_FOUND)
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
        return Response({
            'message': '入库成功',
            'batch': MaterialBatchSerializer(batch).data,
            'stock': MaterialStockSerializer(stock).data
        })


class MaterialStockViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = MaterialStock.objects.all()
    serializer_class = MaterialStockSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        queryset = MaterialStock.objects.select_related(
            'zone', 'material_category', 'material_batch', 'floor'
        ).all()
        zone = self.request.query_params.get('zone')
        if zone:
            try:
                zone_obj = Zone.objects.get(id=zone)
                all_zone_ids = zone_obj.get_all_child_ids()
                queryset = queryset.filter(zone_id__in=all_zone_ids)
            except Zone.DoesNotExist:
                queryset = queryset.none()
        material_category = self.request.query_params.get('material_category')
        if material_category:
            queryset = queryset.filter(material_category_id=material_category)
        project = self.request.query_params.get('project')
        if project:
            queryset = queryset.filter(zone__project_id=project)
        return queryset


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
        queryset = MaterialTransfer.objects.select_related(
            'from_zone', 'to_zone', 'from_floor', 'to_floor',
            'material_category', 'material_batch', 'created_by', 'confirmed_by'
        ).all()
        from_zone = self.request.query_params.get('from_zone')
        if from_zone:
            queryset = queryset.filter(from_zone_id=from_zone)
        to_zone = self.request.query_params.get('to_zone')
        if to_zone:
            queryset = queryset.filter(to_zone_id=to_zone)
        status = self.request.query_params.get('status')
        if status:
            queryset = queryset.filter(status=status)
        return queryset

    def create(self, request, *args, **kwargs):
        request.data['transfer_no'] = f'TRANSFER{timezone.now().strftime("%Y%m%d%H%M%S")}{uuid.uuid4().hex[:4].upper()}'
        request.data['created_by'] = request.user.id
        request.data['status'] = 'pending'
        return super().create(request, *args, **kwargs)

    @action(detail=True, methods=['post'])
    def confirm(self, request, pk=None):
        transfer = self.get_object()
        if transfer.status != 'pending':
            return Response({'error': '只有待确认的转移单才能确认'}, status=status.HTTP_400_BAD_REQUEST)
        with transaction.atomic():
            from_stock = MaterialStock.objects.filter(
                zone=transfer.from_zone,
                material_category=transfer.material_category,
                material_batch=transfer.material_batch,
                floor=transfer.from_floor
            ).first()
            if not from_stock or from_stock.quantity < transfer.quantity:
                return Response({'error': '源分区库存不足'}, status=status.HTTP_400_BAD_REQUEST)
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
            transfer.confirmed_by = request.user
            transfer.confirmed_at = timezone.now()
            transfer.save()
        return Response(MaterialTransferSerializer(transfer).data)

    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        transfer = self.get_object()
        if transfer.status != 'pending':
            return Response({'error': '只有待确认的转移单才能取消'}, status=status.HTTP_400_BAD_REQUEST)
        transfer.status = 'cancelled'
        transfer.save()
        return Response(MaterialTransferSerializer(transfer).data)


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
        queryset = MaterialUsage.objects.select_related(
            'project', 'zone', 'floor', 'material_category',
            'material_batch', 'responsibility_group',
            'created_by', 'approved_by', 'used_by'
        ).all()
        project = self.request.query_params.get('project')
        if project:
            queryset = queryset.filter(project_id=project)
        zone = self.request.query_params.get('zone')
        if zone:
            queryset = queryset.filter(zone_id=zone)
        status = self.request.query_params.get('status')
        if status:
            queryset = queryset.filter(status=status)
        return queryset

    def create(self, request, *args, **kwargs):
        request.data['usage_no'] = f'USAGE{timezone.now().strftime("%Y%m%d%H%M%S")}{uuid.uuid4().hex[:4].upper()}'
        request.data['created_by'] = request.user.id
        request.data['status'] = 'pending'
        return super().create(request, *args, **kwargs)

    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        usage = self.get_object()
        if usage.status != 'pending':
            return Response({'error': '只有待审核的领用单才能通过'}, status=status.HTTP_400_BAD_REQUEST)
        usage.status = 'approved'
        usage.approved_by = request.user
        usage.approved_at = timezone.now()
        usage.save()
        return Response(MaterialUsageSerializer(usage).data)

    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        usage = self.get_object()
        if usage.status != 'pending':
            return Response({'error': '只有待审核的领用单才能拒绝'}, status=status.HTTP_400_BAD_REQUEST)
        usage.status = 'rejected'
        usage.approved_by = request.user
        usage.approved_at = timezone.now()
        usage.remark = request.data.get('remark', usage.remark)
        usage.save()
        return Response(MaterialUsageSerializer(usage).data)

    @action(detail=True, methods=['post'])
    def use(self, request, pk=None):
        usage = self.get_object()
        if usage.status != 'approved':
            return Response({'error': '只有已通过的领用单才能领用'}, status=status.HTTP_400_BAD_REQUEST)
        with transaction.atomic():
            stock = MaterialStock.objects.filter(
                zone=usage.zone,
                material_category=usage.material_category,
                material_batch=usage.material_batch,
                floor=usage.floor
            ).first()
            if not stock or stock.quantity < usage.quantity:
                return Response({'error': '库存不足'}, status=status.HTTP_400_BAD_REQUEST)
            stock.quantity -= usage.quantity
            stock.save()
            usage.status = 'used'
            usage.used_by = request.user
            usage.used_at = timezone.now()
            usage.save()
        return Response(MaterialUsageSerializer(usage).data)


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
        queryset = ExceptionRecord.objects.select_related(
            'project', 'zone', 'floor', 'material_category',
            'material_batch', 'reported_by', 'audited_by', 'handled_by'
        ).all()
        project = self.request.query_params.get('project')
        if project:
            queryset = queryset.filter(project_id=project)
        zone = self.request.query_params.get('zone')
        if zone:
            try:
                zone_obj = Zone.objects.get(id=zone)
                all_zone_ids = zone_obj.get_all_child_ids()
                queryset = queryset.filter(zone_id__in=all_zone_ids)
            except Zone.DoesNotExist:
                queryset = queryset.none()
        status = self.request.query_params.get('status')
        if status:
            queryset = queryset.filter(status=status)
        exception_type = self.request.query_params.get('type')
        if exception_type:
            queryset = queryset.filter(exception_type=exception_type)
        return queryset

    def create(self, request, *args, **kwargs):
        request.data['exception_no'] = f'EXCEPTION{timezone.now().strftime("%Y%m%d%H%M%S")}{uuid.uuid4().hex[:4].upper()}'
        request.data['reported_by'] = request.user.id
        request.data['status'] = 'pending'
        return super().create(request, *args, **kwargs)

    @action(detail=True, methods=['post'])
    def audit(self, request, pk=None):
        exception = self.get_object()
        serializer = AuditExceptionSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        data = serializer.validated_data
        exception.status = data['status']
        exception.handling_suggestion = data.get('handling_suggestion', exception.handling_suggestion)
        exception.handling_result = data.get('handling_result', exception.handling_result)
        exception.audited_by = request.user
        exception.audited_at = timezone.now()
        if data['status'] in ['resolved', 'closed']:
            exception.resolved_at = timezone.now()
            exception.handled_by = request.user
        exception.save()
        return Response(ExceptionRecordSerializer(exception).data)

    @action(detail=True, methods=['post'])
    def resolve(self, request, pk=None):
        exception = self.get_object()
        if exception.status not in ['pending', 'processing']:
            return Response({'error': '只能处理待复核或处理中的异常'}, status=status.HTTP_400_BAD_REQUEST)
        exception.status = 'resolved'
        exception.handling_result = request.data.get('handling_result', exception.handling_result)
        exception.handled_by = request.user
        exception.resolved_at = timezone.now()
        if not exception.audited_by:
            exception.audited_by = request.user
            exception.audited_at = timezone.now()
        exception.save()
        return Response(ExceptionRecordSerializer(exception).data)


class DashboardView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        project_id = request.query_params.get('project')
        query_params = {}
        if project_id:
            query_params['project_id'] = project_id
        total_projects = Project.objects.filter(is_active=True).count()
        total_zones = Zone.objects.filter(**query_params, is_active=True).count()
        total_stock = MaterialStock.objects.filter(**{k.replace('project_id', 'zone__project_id'): v for k, v in query_params.items()}).aggregate(
            total=Sum('quantity')
        )['total'] or 0
        pending_usage = MaterialUsage.objects.filter(**query_params, status='pending').count()
        pending_exception = ExceptionRecord.objects.filter(**query_params, status='pending').count()
        pending_transfer = MaterialTransfer.objects.filter(**{k.replace('project_id', 'from_zone__project_id'): v for k, v in query_params.items()}, status='pending').count()
        return Response({
            'total_projects': total_projects,
            'total_zones': total_zones,
            'total_stock': total_stock,
            'pending_usage': pending_usage,
            'pending_exception': pending_exception,
            'pending_transfer': pending_transfer
        })
