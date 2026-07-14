# Task 2 Report: MessageTemplate model + tests

## What I implemented

Appended the `MessageTemplate` model to the existing `notifications` Django app, following TDD (test-first → RED → implement → GREEN). The model represents a message-template library (all users can maintain) with platform type, system-built-in flag, creator FK (CASCADE), and timestamps.

### Model fields (`MessageTemplate`)
- `name` — CharField(max_length=100)
- `content` — TextField (Markdown, supports `{{var}}` placeholders)
- `platform_type` — CharField(max_length=20, choices=feishu, default='feishu')
- `description` — TextField(blank=True, default='')
- `is_system` — BooleanField(default=False)
- `creator` — ForeignKey(User, on_delete=CASCADE, related_name='created_message_templates')
- `created_at` — DateTimeField(auto_now_add=True)
- `updated_at` — DateTimeField(auto_now=True)

Meta: `ordering = ['-is_system', '-created_at']` (system templates first, then newest).

## TDD Evidence

### RED (test written first, verified failing)
Command: `python manage.py test notifications -v 2` (run from `WHartTest_Django` with venv python)

Result — `ImportError` at `notifications/tests.py` line 3 (`from .models import WebhookAddress, MessageTemplate`):
```
ImportError: cannot import name 'MessageTemplate' from 'notifications.models'
```
Exit code 1, FAILED (errors=1).

Note: the brief's exact command `python manage.py test notifications.MessageTemplateModelTest -v 2` produced a `ModuleNotFoundError: No module named 'notifications.MessageTemplateModelTest'` because of how this Django/Python version parses the `app.TestCase` label (the `notifications.tests` module fails to import before discovery). Running the full app test (`python manage.py test notifications -v 2`) produced the expected `ImportError: cannot import name 'MessageTemplate'`. Both confirm the RED state: MessageTemplate did not exist.

### GREEN (after implementation + migration)
Command: `python manage.py test notifications -v 2`

Result — all 10 tests pass:
```
test_create_template (notifications.tests.MessageTemplateModelTest) ... ok
test_creator_cascade_delete (notifications.tests.MessageTemplateModelTest) ... ok
test_ordering_system_first (notifications.tests.MessageTemplateModelTest) ... ok
test_str_representation (notifications.tests.MessageTemplateModelTest) ... ok
test_system_template_flag (notifications.tests.MessageTemplateModelTest) ... ok
test_create_webhook_address (notifications.tests.WebhookAddressModelTest) ... ok
test_creator_set_null_on_delete (notifications.tests.WebhookAddressModelTest) ... ok
test_default_values (notifications.tests.WebhookAddressModelTest) ... ok
test_ordering (notifications.tests.WebhookAddressModelTest) ... ok
test_str_representation (notifications.tests.WebhookAddressModelTest) ... ok

Ran 10 tests in 8.528s
OK
```
Migration applied cleanly during test DB setup: `Applying notifications.0002_messagetemplate... OK`.

## Migration

`makemigrations notifications` produced `notifications/migrations/0002_messagetemplate.py` (CreateModel, depends on `0001_initial` + `AUTH_USER_MODEL` swappable dependency, `on_delete=CASCADE` confirmed).

## Files changed
- `WHartTest_Django/notifications/models.py` — appended `MessageTemplate` model
- `WHartTest_Django/notifications/admin.py` — updated import; appended `MessageTemplateAdmin` (list_display, list_filter, search_fields, readonly_fields)
- `WHartTest_Django/notifications/tests.py` — updated import; appended `MessageTemplateModelTest` (5 tests)
- `WHartTest_Django/notifications/migrations/0002_messagetemplate.py` — new migration (generated)

## Commit
- `783c2a0` — `feat: add MessageTemplate model` (4 files changed, 132 insertions, 2 deletions)

## Self-review findings
- Model code, admin, tests, and migration all match the task brief exactly.
- `creator` uses `on_delete=CASCADE` (deliberately different from `WebhookAddress`'s `SET_NULL`); verified by `test_creator_cascade_delete`.
- Ordering `['-is_system', '-created_at']` verified by `test_ordering_system_first` (system template sorts before user template).
- Default values (`platform_type='feishu'`, `is_system=False`, `description=''`) verified by `test_create_template`.
- `__str__` returns `name`, verified by `test_str_representation`.
- Import lines in both `tests.py` and `admin.py` updated to include `MessageTemplate`.
- No scope creep: only the `notifications` app files were touched; unrelated pre-existing uncommitted changes in the repo (app_ui_automation, Vue files) were left untouched and excluded from the commit.

## Concerns
- **Dev DB missing (pre-existing environment issue, not a code issue):** `python manage.py migrate` failed with `FATAL: database "wharttest_dev" does not exist` because the PostgreSQL dev database is not present in this environment. This does NOT affect the task: the migration file was generated correctly, and the Django test runner creates its own test database (`test_wharttest_dev`) where `0002_messagetemplate` applies cleanly and all 10 tests pass. The dev DB just needs to be created/seeded separately if running the app server locally.
- **Test label parsing:** `python manage.py test notifications.MessageTemplateModelTest` does not resolve in this Django version (ModuleNotFoundError on the label). Use `python manage.py test notifications` (or `notifications.tests.MessageTemplateModelTest`) instead. The brief's expected RED `ImportError` is reproducible via the full-app test command.
