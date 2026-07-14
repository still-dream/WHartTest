# Task 1 Report: Create notifications app + WebhookAddress model + tests

## What I Implemented

Created the `notifications` Django app scaffold and the `WebhookAddress` model following the task brief exactly:

1. **App directory structure**: `notifications/__init__.py` (empty), `notifications/migrations/__init__.py` (empty)
2. **`notifications/apps.py`**: `NotificationsConfig` with `verbose_name = '推送通知'`
3. **`notifications/models.py`**: `WebhookAddress` model with fields: `name`, `url`, `platform_type` (default 'feishu'), `description`, `is_active`, `creator` (FK to User, SET_NULL), `created_at`, `updated_at`. Meta ordering `['-created_at']`. `__str__` returns `name`.
4. **`notifications/admin.py`**: `WebhookAddressAdmin` with list_display, list_filter, search_fields, readonly_fields.
5. **`notifications/tests.py`**: 5 test cases (create, str, defaults, ordering, creator SET_NULL on delete).
6. **`notifications/migrations/0001_initial.py`**: Auto-generated migration for WebhookAddress model.
7. **`wharttest_django/settings.py`**: Added `'notifications'` after `'task_center'` in INSTALLED_APPS.

## What I Tested and Test Results

All 5 tests pass:
- `test_create_webhook_address` - verifies field values and defaults on create
- `test_str_representation` - verifies `__str__` returns name
- `test_default_values` - verifies platform_type='feishu', is_active=True, creator=None, description=''
- `test_ordering` - verifies ordering by `-created_at` (newest first)
- `test_creator_set_null_on_delete` - verifies creator set to NULL when User deleted

## TDD Evidence

### RED (test fails before implementation)

Command: `cd WHartTest_Django && venv\Scripts\python.exe manage.py test notifications -v 2`

```
ImportError: Failed to import test module: notifications.tests
Traceback (most recent call last):
  File "C:\app\WHartTest\WHartTest_Django\notifications\tests.py", line 3, in <module>
    from .models import WebhookAddress
ModuleNotFoundError: No module named 'notifications.models'

Ran 1 test in 0.000s
FAILED (errors=1)
```

### GREEN (test passes after implementation)

Command: `cd WHartTest_Django && venv\Scripts\python.exe manage.py test notifications -v 2`

```
Creating test database for alias 'default' ('test_wharttest_dev')...
Found 5 test(s).
...
  Applying notifications.0001_initial... OK
...
test_create_webhook_address (notifications.tests.WebhookAddressModelTest.test_create_webhook_address) ... ok
test_creator_set_null_on_delete (notifications.tests.WebhookAddressModelTest.test_creator_set_null_on_delete) ... ok
test_default_values (notifications.tests.WebhookAddressModelTest.test_default_values) ... ok
test_ordering (notifications.tests.WebhookAddressModelTest.test_ordering) ... ok
test_str_representation (notifications.tests.WebhookAddressModelTest.test_str_representation) ... ok

----------------------------------------------------------------------
Ran 5 tests in 2.762s

OK
Destroying test database for alias 'default' ('test_wharttest_dev')...
```

## Files Changed

- `WHartTest_Django/notifications/__init__.py` (new, empty)
- `WHartTest_Django/notifications/apps.py` (new)
- `WHartTest_Django/notifications/models.py` (new)
- `WHartTest_Django/notifications/admin.py` (new)
- `WHartTest_Django/notifications/tests.py` (new)
- `WHartTest_Django/notifications/migrations/__init__.py` (new, empty)
- `WHartTest_Django/notifications/migrations/0001_initial.py` (new, auto-generated)
- `WHartTest_Django/wharttest_django/settings.py` (modified, +1 line)

Commit: `dde559d` - "feat: add notifications app with WebhookAddress model" (8 files, 142 insertions)

## Self-Review Findings

- All files match the task brief exactly (code copied verbatim from brief).
- TDD cycle followed: wrote test first, verified RED, implemented, verified GREEN.
- Migration `0001_initial` auto-generated correctly with all model fields.
- Commit contains only the 8 intended files; no unrelated changes included.
- The test command uses the venv Python (`venv\Scripts\python.exe`) as specified in the task context.

## Concerns

1. **Environment: missing venv packages (pre-existing)**. The venv at `WHartTest_Django/venv/` was missing `django-celery-beat` and `pymysql` (both listed in `requirements.txt`). I installed them to make the test runner work. Installing `django-celery-beat==2.8.1` downgraded Django from 6.0.4 to 5.2 (which matches `requirements.txt`'s `Django==5.2` — the venv had an incorrect Django 6.0.4). This is a pre-existing environment inconsistency, not caused by this task.

2. **Dev database unavailable (pre-existing)**. The `migrate` command fails because the PostgreSQL database `wharttest_dev` does not exist at `127.0.0.1:8919`. This does not affect tests — the Django test runner creates and destroys its own `test_wharttest_dev` database successfully.
