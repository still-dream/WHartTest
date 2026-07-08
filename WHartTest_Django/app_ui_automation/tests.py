import io
import zipfile

from django.test import TestCase
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from projects.models import Project
from app_ui_automation.models import AppUiModule, AppUiScript


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


class AppUiScriptModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='testpass')
        self.project = Project.objects.create(name='Test Project', creator=self.user)
        self.module = AppUiModule.objects.create(
            project=self.project, name='Test Module', creator=self.user
        )

    def _make_air_zip(self):
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, 'w') as zf:
            zf.writestr('test.air/test.py',
                '# -*- encoding=utf8 -*-\nfrom airtest.core.api import *\nauto_setup(__file__)\n')
            zf.writestr('test.air/tpl123.png', b'fake_png_data')
        buf.seek(0)
        return SimpleUploadedFile('test.air.zip', buf.read(), content_type='application/zip')

    def test_create_script(self):
        script = AppUiScript.objects.create(
            project=self.project, module=self.module, name='Test Script',
            platform='android', script_file=self._make_air_zip(), creator=self.user
        )
        self.assertEqual(script.name, 'Test Script')
        self.assertEqual(script.status, 'idle')
        self.assertTrue(script.script_file.name.startswith('app_ui_scripts/'))
