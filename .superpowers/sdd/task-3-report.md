# Task 3 Report: Notifications API (serializers + views + urls + tests)

## What I Implemented

### New Files Created
1. **`notifications/serializers.py`** — Three serializers:
   - `WebhookAddressSerializer`: full fields (id, name, url, platform_type, description, is_active, creator, created_at, updated_at)
   - `WebhookAddressLimitedSerializer`: limited fields for normal users (id, name, is_active only — hides url)
   - `MessageTemplateSerializer`: all fields with `is_system` as read-only

2. **`notifications/views.py`** — Two permission classes + two viewsets:
   - `IsAdminOrReadOnlyName`: admin/superuser can CRUD; normal users can only GET
   - `IsCreatorOrAdmin`: all authenticated users can read/create; only creator or admin can edit/delete
   - `WebhookAddressViewSet`: uses `get_serializer_class()` to switch serializers by user role; `perform_create` sets creator; `test_send` action POSTs a test card to the webhook URL and catches all exceptions (always returns 200)
   - `MessageTemplateViewSet`: `perform_create` sets creator; `perform_destroy` raises `ValidationError` for system templates

3. **`notifications/urls.py`** — DefaultRouter with `webhook-addresses` and `message-templates` routes

4. **`notifications/services.py`** — Minimal stub: `build_feishu_card()` returns a basic interactive card JSON (to be expanded in Task 4)

### Files Modified
5. **`wharttest_django/urls.py`** — Added `path("api/notifications/", include("notifications.urls"))` after the APPUI automation route
6. **`notifications/tests.py`** — Added `APIClient` and `status` imports; appended `WebhookAddressAPITest` (9 tests) and `MessageTemplateAPITest` (8 tests)

## TDD Evidence

### RED (Step 2)
Ran `python manage.py test notifications -v 2 --keepdb` after writing tests but before implementation:
```
FAILED (failures=16, errors=1)
Ran 27 tests in 30.244s
```
All 17 API tests failed with 404 (URL routes didn't exist). 10 model tests passed.

### GREEN (Step 4)
Ran the same command after implementation:
```
OK
Ran 27 tests in 30.888s
```
All 27 tests pass (10 model + 9 WebhookAddress API + 8 MessageTemplate API).

## Files Changed
- `WHartTest_Django/notifications/serializers.py` (new, 35 lines)
- `WHartTest_Django/notifications/views.py` (new, 98 lines)
- `WHartTest_Django/notifications/urls.py` (new, 8 lines)
- `WHartTest_Django/notifications/services.py` (new, 20 lines)
- `WHartTest_Django/notifications/tests.py` (modified, +159 lines)
- `WHartTest_Django/wharttest_django/urls.py` (modified, +2 lines)

Commit: `10f83a0` on branch `feat/task-push-notification`

## Deviations from Task Brief (with justification)

### 1. Added `pagination_class = StandardPagination` to both viewsets
The task brief's test code uses `resp.data.get('results', resp.data)` which assumes `resp.data` is a dict (paginated response). This project does NOT set `DEFAULT_PAGINATION_CLASS` globally in REST_FRAMEWORK settings, so without explicitly setting `pagination_class`, list endpoints return a `ReturnList` (not a dict), causing `AttributeError: 'ReturnList' object has no attribute 'get'`. All other viewsets in this project (api_database_configs, api_testcases, etc.) explicitly set `pagination_class = StandardPagination`. I followed this established project convention.

### 2. Changed two DELETE tests from `assertEqual(204)` to `assertIn([200, 204])`
The project uses a custom `UnifiedResponseRenderer` (`wharttest_django/renderers.py`) that converts HTTP 204 to 200 in its `render()` method (line 45-53). This means `resp.status_code` for DELETE operations is always 200, never 204. All other test files in this project use `self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_204_NO_CONTENT])` for DELETE tests. I followed this established project convention for `test_admin_can_delete` and `test_creator_can_delete_own`.

## Self-Review Findings

1. **Permission logic is sound**: `IsAdminOrReadOnlyName` correctly blocks non-staff from writing WebhookAddress; `IsCreatorOrAdmin` correctly allows any authenticated user to create but restricts edit/delete to creator or admin.
2. **System template protection works**: `perform_destroy` raises `ValidationError` (400) before deletion, verified by `test_system_template_cannot_be_deleted`.
3. **`is_system` is read-only**: The serializer's `read_only_fields` includes `is_system`, verified by `test_is_system_read_only` — even if `is_system=True` is POSTed, the created template has `is_system=False`.
4. **Test action handles network failures gracefully**: The `test_send` action catches all exceptions (including connection errors to the fake URL `https://open.feishu.cn/hook/xxx`) and returns 200 with an error message.
5. **No security concerns**: No secrets are logged; the webhook URL is only visible to admin/staff users via the limited serializer.

## Concerns
None. All adaptations from the brief are justified by the project's existing architecture (UnifiedResponseRenderer, no global pagination, StandardPagination convention).
