from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.utils import timezone
from django.db import transaction
from datetime import timedelta
from material_management.models import (
    Project, MaterialCategory, Zone, Floor,
    MaterialBatch, MaterialStock, UserProfile
)
from material_management.services.warning_service import run_warning_detection


class Command(BaseCommand):
    help = '生成预警功能演示数据：创建材料批次、库存数据，触发各种预警场景'

    def handle(self, *args, **options):
        self.stdout.write(self.style.WARNING('开始生成预警演示数据...'))

        with transaction.atomic():
            self._create_demo_data()

        self.stdout.write(self.style.SUCCESS('演示数据生成完成！'))
        self.stdout.write('  可调用 /api/material-warnings/detect/ 接口生成预警记录')
        self.stdout.write('  可调用 /api/material-warnings/ 接口查看预警列表')

    def _create_demo_data(self):
        self.stdout.write('获取基础数据...')
        project = Project.objects.filter(name='市民中心建设项目').first()
        if not project:
            self.stdout.write(self.style.ERROR('项目不存在，请先运行 init_data'))
            return

        zone = Zone.objects.filter(project=project, code='A-01-01').first()
        if not zone:
            zone = Zone.objects.filter(project=project).first()

        floor = Floor.objects.filter(project=project, code='B2').first()
        operator = User.objects.filter(username='operator').first()

        self.stdout.write('创建低库存预警场景...')
        self._create_low_stock_scenario(project, zone, floor, operator)

        self.stdout.write('创建临期预警场景...')
        self._create_expiring_scenario(project, zone, floor, operator)

        self.stdout.write('创建库存积压预警场景...')
        self._create_overstock_scenario(project, zone, floor, operator)

        self.stdout.write('运行预警检测...')
        run_warning_detection(project_id=project.id, user=operator)

    def _create_low_stock_scenario(self, project, zone, floor, operator):
        rebar_category = MaterialCategory.objects.filter(code='STEEL-REBAR').first()
        if not rebar_category:
            return

        rebar_category.safety_threshold = 50
        rebar_category.save()

        batch1 = MaterialBatch.objects.create(
            batch_no=f'BATCH-LOWSTOCK-{timezone.now().strftime("%Y%m%d%H%M%S")}',
            project=project,
            material_category=rebar_category,
            supplier='鞍钢集团',
            total_quantity=100,
            received_quantity=5,
            unit_price=4500,
            production_date=timezone.now().date() - timedelta(days=30),
            inbound_date=timezone.now().date() - timedelta(days=25),
            status='in_stock',
            created_by=operator
        )

        MaterialStock.objects.create(
            zone=zone,
            floor=floor,
            material_category=rebar_category,
            material_batch=batch1,
            quantity=5
        )

        cement_category = MaterialCategory.objects.filter(code='CEMENT').first()
        if cement_category:
            cement_category.safety_threshold = 20
            cement_category.save()

            batch2 = MaterialBatch.objects.create(
                batch_no=f'BATCH-LOWSTOCK2-{timezone.now().strftime("%Y%m%d%H%M%S")}',
                project=project,
                material_category=cement_category,
                supplier='海螺水泥',
                total_quantity=50,
                received_quantity=3,
                unit_price=380,
                production_date=timezone.now().date() - timedelta(days=10),
                inbound_date=timezone.now().date() - timedelta(days=5),
                status='in_stock',
                created_by=operator
            )

            MaterialStock.objects.create(
                zone=zone,
                floor=floor,
                material_category=cement_category,
                material_batch=batch2,
                quantity=3
            )

    def _create_expiring_scenario(self, project, zone, floor, operator):
        concrete_category = MaterialCategory.objects.filter(code='CONCRETE-C30').first()
        if not concrete_category:
            return

        concrete_category.shelf_life_days = 90
        concrete_category.save()

        batch1 = MaterialBatch.objects.create(
            batch_no=f'BATCH-EXPIRING-{timezone.now().strftime("%Y%m%d%H%M%S")}',
            project=project,
            material_category=concrete_category,
            supplier='中建商砼',
            total_quantity=200,
            received_quantity=150,
            unit_price=420,
            production_date=timezone.now().date() - timedelta(days=75),
            inbound_date=timezone.now().date() - timedelta(days=70),
            status='in_stock',
            created_by=operator
        )

        MaterialStock.objects.create(
            zone=zone,
            floor=floor,
            material_category=concrete_category,
            material_batch=batch1,
            quantity=150
        )

        wood_category = MaterialCategory.objects.filter(code='WOOD').first()
        if wood_category:
            wood_category.shelf_life_days = 180
            wood_category.save()

            batch2 = MaterialBatch.objects.create(
                batch_no=f'BATCH-EXPIRING2-{timezone.now().strftime("%Y%m%d%H%M%S")}',
                project=project,
                material_category=wood_category,
                supplier='大兴安岭林场',
                total_quantity=100,
                received_quantity=80,
                unit_price=1500,
                production_date=timezone.now().date() - timedelta(days=170),
                inbound_date=timezone.now().date() - timedelta(days=165),
                status='in_stock',
                created_by=operator
            )

            MaterialStock.objects.create(
                zone=zone,
                floor=floor,
                material_category=wood_category,
                material_batch=batch2,
                quantity=80
            )

    def _create_overstock_scenario(self, project, zone, floor, operator):
        pipe_category = MaterialCategory.objects.filter(code='STEEL-PIPE').first()
        if not pipe_category:
            return

        pipe_category.safety_threshold = 10
        pipe_category.shelf_life_days = 365
        pipe_category.save()

        batch1 = MaterialBatch.objects.create(
            batch_no=f'BATCH-OVERSTOCK-{timezone.now().strftime("%Y%m%d%H%M%S")}',
            project=project,
            material_category=pipe_category,
            supplier='宝钢股份',
            total_quantity=500,
            received_quantity=500,
            unit_price=6800,
            production_date=timezone.now().date() - timedelta(days=60),
            inbound_date=timezone.now().date() - timedelta(days=55),
            status='in_stock',
            created_by=operator
        )

        MaterialStock.objects.create(
            zone=zone,
            floor=floor,
            material_category=pipe_category,
            material_batch=batch1,
            quantity=500
        )
