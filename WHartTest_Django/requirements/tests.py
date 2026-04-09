import tempfile
from unittest.mock import MagicMock, patch

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from rest_framework import status
from rest_framework.test import APIClient

from api_keys.models import APIKey
from projects.models import Project

from .models import RequirementDocument, RequirementModule, ReviewReport


@override_settings(MEDIA_ROOT=tempfile.gettempdir())
class RequirementDocumentDocxEditorTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.superuser = User.objects.create_superuser(
            username="docx-admin",
            email="docx@example.com",
            password="Secret123!",
        )
        self.api_key = APIKey.objects.create(
            user=self.superuser,
            name="docx-editor-test-key",
            key="docx-editor-test-key",
            is_active=True,
        )
        self.project = Project.objects.create(
            name="docx-editor-project",
            description="demo",
            creator=self.superuser,
        )
        self.document = RequirementDocument.objects.create(
            project=self.project,
            title="需求文档",
            document_type="docx",
            file=SimpleUploadedFile(
                "requirement.docx",
                b"old file body",
                content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            ),
            content="旧内容",
            status="ready_for_review",
            uploader=self.superuser,
        )
        self.detail_base = f"/api/requirements/documents/{self.document.id}"

    def test_launch_online_editor_returns_not_integrated_when_config_missing(self):
        self.client.force_authenticate(self.superuser)

        with override_settings(DOCX_EDITOR_BASE_URL="", DOCX_EDITOR_SERVICE_KEY=""):
            response = self.client.post(f"{self.detail_base}/launch-online-editor/")

        payload = response.json()
        self.assertEqual(response.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)
        self.assertEqual(
            payload["message"],
            "在线编辑功能未接入，请先在主项目后端配置 DOCX_EDITOR_BASE_URL 和 DOCX_EDITOR_SERVICE_KEY。",
        )

    @override_settings(
        DOCX_EDITOR_BASE_URL="http://127.0.0.1:18080",
        DOCX_EDITOR_PUBLIC_BASE_URL="http://172.16.3.183:18080",
        DOCX_EDITOR_SERVICE_KEY="integration-key",
    )
    @patch("requirements.docx_editor_integration.requests.post")
    def test_launch_online_editor_calls_docx_editor(self, post_mock):
        self.client.force_authenticate(self.superuser)

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "launch_url": "http://172.16.3.183:18080/embed/binding-1?token=test-token",
            "bindingId": "binding-1",
            "documentId": "remote-doc-1",
        }
        post_mock.return_value = mock_response

        response = self.client.post(f"{self.detail_base}/launch-online-editor/")

        payload = response.json()
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            payload["data"]["launch_url"],
            "http://172.16.3.183:18080/embed/binding-1?token=test-token",
        )

        _, kwargs = post_mock.call_args
        self.assertEqual(
            kwargs["headers"]["Authorization"],
            "Bearer integration-key",
        )
        self.assertEqual(
            kwargs["headers"]["X-Docx-Editor-Public-Base-Url"],
            "http://172.16.3.183:18080",
        )
        self.assertEqual(
            kwargs["data"]["pushback_url"],
            f"/api/requirements/documents/{self.document.id}/upload-edited-file/",
        )

    @patch("requirements.docx_editor_integration.DocumentProcessor")
    def test_upload_edited_file_replaces_document_and_resets_review_state(
        self,
        processor_cls,
    ):
        RequirementModule.objects.create(
            document=self.document,
            title="模块1",
            content="旧模块内容",
            order=1,
        )
        ReviewReport.objects.create(
            document=self.document,
            status="completed",
            summary="旧报告",
        )

        mock_processor = processor_cls.return_value
        mock_processor.extract_content.return_value = "更新后的原始内容"
        mock_processor.preprocess_content.return_value = "更新后的处理内容"

        response = self.client.post(
            f"{self.detail_base}/upload-edited-file/",
            data={
                "file": SimpleUploadedFile(
                    "updated.docx",
                    b"new file body",
                    content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                )
            },
            format="multipart",
            HTTP_X_API_KEY=self.api_key.key,
        )

        payload = response.json()
        self.document.refresh_from_db()

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(payload["data"]["status"], "uploaded")
        self.assertEqual(self.document.status, "uploaded")
        self.assertEqual(self.document.content, "更新后的处理内容")
        self.assertEqual(self.document.modules.count(), 0)
        self.assertEqual(self.document.review_reports.count(), 0)
        self.assertTrue(self.document.file.name.endswith("updated.docx"))
        mock_processor.extract_content.assert_called_once()
        mock_processor.preprocess_content.assert_called_once_with("更新后的原始内容")
