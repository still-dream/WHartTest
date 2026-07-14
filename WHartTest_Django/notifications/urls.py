from rest_framework.routers import DefaultRouter
from .views import WebhookAddressViewSet, MessageTemplateViewSet

router = DefaultRouter()
router.register(r'webhook-addresses', WebhookAddressViewSet, basename='webhook-address')
router.register(r'message-templates', MessageTemplateViewSet, basename='message-template')

urlpatterns = router.urls
