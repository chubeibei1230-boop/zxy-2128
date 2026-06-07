from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from material_management.models import (
    UserProfile, Project, MaterialCategory, Zone, Floor,
    ResponsibilityGroup
)
from django.db import transaction


class Command(BaseCommand):
    help = '初始化系统数据：创建管理员、操作员、审核员用户，以及示例项目、分区、材料类别等'

    def handle(self, *args, **options):
        self.stdout.write(self.style.WARNING('开始初始化数据...'))

        with transaction.atomic():
            self._create_users()
            self._create_projects()
            self._create_material_categories()
            self._create_zones()
            self._create_floors()
            self._create_responsibility_groups()

        self.stdout.write(self.style.SUCCESS('数据初始化完成！'))
        self.stdout.write('默认账号：')
        self.stdout.write('  管理员: admin / admin123456')
        self.stdout.write('  操作员: operator / operator123')
        self.stdout.write('  审核员: auditor / auditor123')

    def _create_users(self):
        self.stdout.write('创建用户...')

        admin_user, created = User.objects.get_or_create(
            username='admin',
            defaults={
                'email': 'admin@example.com',
                'is_superuser': True,
                'is_staff': True,
                'first_name': '系统',
                'last_name': '管理员'
            }
        )
        if created:
            admin_user.set_password('admin123456')
            admin_user.save()
        UserProfile.objects.get_or_create(
            user=admin_user,
            defaults={'role': 'admin', 'phone': '13800000001'}
        )

        operator_user, created = User.objects.get_or_create(
            username='operator',
            defaults={
                'email': 'operator@example.com',
                'is_staff': False,
                'first_name': '张',
                'last_name': '操作员'
            }
        )
        if created:
            operator_user.set_password('operator123')
            operator_user.save()
        UserProfile.objects.get_or_create(
            user=operator_user,
            defaults={'role': 'operator', 'phone': '13800000002'}
        )

        auditor_user, created = User.objects.get_or_create(
            username='auditor',
            defaults={
                'email': 'auditor@example.com',
                'is_staff': False,
                'first_name': '李',
                'last_name': '审核员'
            }
        )
        if created:
            auditor_user.set_password('auditor123')
            auditor_user.save()
        UserProfile.objects.get_or_create(
            user=auditor_user,
            defaults={'role': 'auditor', 'phone': '13800000003'}
        )

        self.stdout.write(self.style.SUCCESS('  用户创建完成'))

    def _create_projects(self):
        self.stdout.write('创建项目...')

        project1, _ = Project.objects.get_or_create(
            name='市民中心建设项目',
            defaults={
                'description': '集办公、商业、文化于一体的综合性市民中心项目',
                'address': '北京市朝阳区建国路88号',
                'is_active': True
            }
        )

        project2, _ = Project.objects.get_or_create(
            name='地铁5号线延伸段工程',
            defaults={
                'description': '城市轨道交通5号线南延伸段工程',
                'address': '上海市浦东新区',
                'is_active': True
            }
        )

        self.stdout.write(self.style.SUCCESS('  项目创建完成'))

    def _create_material_categories(self):
        self.stdout.write('创建材料类别...')

        steel, _ = MaterialCategory.objects.get_or_create(
            code='STEEL',
            defaults={
                'name': '钢材',
                'unit': '吨',
                'description': '建筑用钢材',
                'is_active': True
            }
        )

        MaterialCategory.objects.get_or_create(
            code='STEEL-REBAR',
            defaults={
                'name': '钢筋',
                'parent': steel,
                'unit': '吨',
                'description': '螺纹钢筋',
                'is_active': True
            }
        )

        MaterialCategory.objects.get_or_create(
            code='STEEL-PIPE',
            defaults={
                'name': '钢管',
                'parent': steel,
                'unit': '吨',
                'description': '无缝钢管',
                'is_active': True
            }
        )

        concrete, _ = MaterialCategory.objects.get_or_create(
            code='CONCRETE',
            defaults={
                'name': '混凝土',
                'unit': '立方米',
                'description': '商品混凝土',
                'is_active': True
            }
        )

        MaterialCategory.objects.get_or_create(
            code='CONCRETE-C30',
            defaults={
                'name': 'C30混凝土',
                'parent': concrete,
                'unit': '立方米',
                'description': '强度等级C30',
                'is_active': True
            }
        )

        MaterialCategory.objects.get_or_create(
            code='WOOD',
            defaults={
                'name': '木材',
                'unit': '立方米',
                'description': '建筑模板用木材',
                'is_active': True
            }
        )

        MaterialCategory.objects.get_or_create(
            code='CEMENT',
            defaults={
                'name': '水泥',
                'unit': '吨',
                'description': '硅酸盐水泥',
                'is_active': True
            }
        )

        self.stdout.write(self.style.SUCCESS('  材料类别创建完成'))

    def _create_zones(self):
        self.stdout.write('创建分区...')

        project = Project.objects.filter(name='市民中心建设项目').first()
        if not project:
            return

        zone_a, _ = Zone.objects.get_or_create(
            project=project,
            code='A',
            defaults={
                'name': 'A区 - 主体建筑',
                'level': 1,
                'sort_order': 1,
                'description': '项目主体建筑区域',
                'is_active': True
            }
        )

        zone_a1, _ = Zone.objects.get_or_create(
            project=project,
            code='A-01',
            defaults={
                'name': 'A-01区 - 地下结构',
                'parent': zone_a,
                'level': 2,
                'sort_order': 1,
                'description': '地下室、基础施工区域',
                'is_active': True
            }
        )

        Zone.objects.get_or_create(
            project=project,
            code='A-01-01',
            defaults={
                'name': 'A-01-01区 - 负三层',
                'parent': zone_a1,
                'level': 3,
                'sort_order': 1,
                'description': '负三层施工区',
                'is_active': True
            }
        )

        Zone.objects.get_or_create(
            project=project,
            code='A-01-02',
            defaults={
                'name': 'A-01-02区 - 负二层',
                'parent': zone_a1,
                'level': 3,
                'sort_order': 2,
                'description': '负二层施工区',
                'is_active': True
            }
        )

        zone_a2, _ = Zone.objects.get_or_create(
            project=project,
            code='A-02',
            defaults={
                'name': 'A-02区 - 地上结构',
                'parent': zone_a,
                'level': 2,
                'sort_order': 2,
                'description': '地上主体结构区域',
                'is_active': True
            }
        )

        Zone.objects.get_or_create(
            project=project,
            code='B',
            defaults={
                'name': 'B区 - 配套设施',
                'level': 1,
                'sort_order': 2,
                'description': '配套设施建设区域',
                'is_active': True
            }
        )

        self.stdout.write(self.style.SUCCESS('  分区创建完成'))

    def _create_floors(self):
        self.stdout.write('创建楼层...')

        project = Project.objects.filter(name='市民中心建设项目').first()
        if not project:
            return

        floors_data = [
            ('B3', '负三层', 1),
            ('B2', '负二层', 2),
            ('B1', '负一层', 3),
            ('F1', '一层', 4),
            ('F2', '二层', 5),
            ('F3', '三层', 6),
            ('F4', '四层', 7),
            ('F5', '五层', 8),
        ]

        for code, name, sort_order in floors_data:
            Floor.objects.get_or_create(
                project=project,
                code=code,
                defaults={
                    'name': name,
                    'sort_order': sort_order,
                    'is_active': True
                }
            )

        self.stdout.write(self.style.SUCCESS('  楼层创建完成'))

    def _create_responsibility_groups(self):
        self.stdout.write('创建责任小组...')

        project = Project.objects.filter(name='市民中心建设项目').first()
        operator = User.objects.filter(username='operator').first()
        if not project:
            return

        group1, _ = ResponsibilityGroup.objects.get_or_create(
            project=project,
            name='主体结构施工一组',
            defaults={
                'leader': operator,
                'description': '负责主体结构钢筋、混凝土施工',
                'is_active': True
            }
        )
        if operator:
            group1.members.add(operator)

        ResponsibilityGroup.objects.get_or_create(
            project=project,
            name='水电安装组',
            defaults={
                'description': '负责水电管线安装施工',
                'is_active': True
            }
        )

        ResponsibilityGroup.objects.get_or_create(
            project=project,
            name='装饰装修组',
            defaults={
                'description': '负责室内外装饰装修工程',
                'is_active': True
            }
        )

        self.stdout.write(self.style.SUCCESS('  责任小组创建完成'))
