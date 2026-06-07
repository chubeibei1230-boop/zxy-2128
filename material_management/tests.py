from django.test import TestCase

from .models import MaterialCategory, Project, Zone
from .selectors import get_dashboard_stats
from .services import merge_zones


class DashboardStatsTests(TestCase):
    def test_dashboard_stats_respects_project_filter_for_total_projects(self):
        included_project = Project.objects.create(name='项目A', is_active=True)
        Project.objects.create(name='项目B', is_active=True)

        stats = get_dashboard_stats(str(included_project.id))

        self.assertEqual(stats['total_projects'], 1)


class ZoneMergeTests(TestCase):
    def test_merge_zones_updates_reparented_children_levels(self):
        project = Project.objects.create(name='项目A', is_active=True)
        category = MaterialCategory.objects.create(
            name='钢材',
            code='STEEL',
            unit='吨',
            is_active=True,
        )
        target_zone = Zone.objects.create(
            project=project,
            name='目标分区',
            code='TARGET',
            level=1,
            is_active=True,
        )
        source_zone = Zone.objects.create(
            project=project,
            name='源分区',
            code='SOURCE',
            level=1,
            is_active=True,
        )
        child_zone = Zone.objects.create(
            project=project,
            name='子分区',
            code='CHILD',
            parent=source_zone,
            level=2,
            is_active=True,
        )
        grandchild_zone = Zone.objects.create(
            project=project,
            name='孙分区',
            code='GRANDCHILD',
            parent=child_zone,
            level=3,
            is_active=True,
        )

        merge_zones(target_zone.id, [source_zone.id])

        child_zone.refresh_from_db()
        grandchild_zone.refresh_from_db()
        source_zone.refresh_from_db()

        self.assertEqual(child_zone.parent_id, target_zone.id)
        self.assertEqual(child_zone.level, target_zone.level + 1)
        self.assertEqual(grandchild_zone.level, child_zone.level + 1)
        self.assertFalse(source_zone.is_active)
