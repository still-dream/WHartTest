from django.test import TestCase
from django.contrib.auth.models import User
from projects.models import Project
from app_ui_automation.models import AppUiModule


class AppUiModuleModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='testpass')
        self.project = Project.objects.create(name='Test Project', creator=self.user)

    def test_create_root_module(self):
        module = AppUiModule.objects.create(
            project=self.project, name='Root Module', creator=self.user
        )
        self.assertEqual(module.level, 1)
        self.assertIsNone(module.parent)

    def test_create_child_module(self):
        parent = AppUiModule.objects.create(
            project=self.project, name='Parent', creator=self.user
        )
        child = AppUiModule.objects.create(
            project=self.project, name='Child', parent=parent, creator=self.user
        )
        self.assertEqual(child.level, 2)

    def test_module_level_max_5(self):
        parent = AppUiModule.objects.create(
            project=self.project, name='L1', creator=self.user
        )
        for i in range(4):
            parent = AppUiModule.objects.create(
                project=self.project, name=f'L{i+2}', parent=parent, creator=self.user
            )
        self.assertEqual(parent.level, 5)
