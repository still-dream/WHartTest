from django.contrib import admin
from .models import (
    AppUiModule, AppUiScript, AppUiDevice,
    AppUiExecutionRecord, AppUiBatchExecutionRecord
)

admin.site.register(AppUiModule)
admin.site.register(AppUiScript)
admin.site.register(AppUiDevice)
admin.site.register(AppUiExecutionRecord)
admin.site.register(AppUiBatchExecutionRecord)
