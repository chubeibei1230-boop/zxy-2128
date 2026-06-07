from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework.authtoken.views import obtain_auth_token

from .views import (
    UserViewSet, current_user,
    ProjectViewSet, MaterialCategoryViewSet, ZoneViewSet,
    FloorViewSet, ResponsibilityGroupViewSet, MaterialBatchViewSet,
    MaterialStockViewSet, MaterialTransferViewSet, MaterialUsageViewSet,
    ExceptionRecordViewSet, DashboardView
)

router = DefaultRouter()
router.register(r'users', UserViewSet)
router.register(r'projects', ProjectViewSet)
router.register(r'material-categories', MaterialCategoryViewSet)
router.register(r'zones', ZoneViewSet)
router.register(r'floors', FloorViewSet)
router.register(r'responsibility-groups', ResponsibilityGroupViewSet)
router.register(r'material-batches', MaterialBatchViewSet)
router.register(r'material-stocks', MaterialStockViewSet)
router.register(r'material-transfers', MaterialTransferViewSet)
router.register(r'material-usages', MaterialUsageViewSet)
router.register(r'exception-records', ExceptionRecordViewSet)

urlpatterns = [
    path('', include(router.urls)),
    path('auth/login/', obtain_auth_token, name='api_token_auth'),
    path('auth/current-user/', current_user, name='current_user'),
    path('dashboard/', DashboardView.as_view(), name='dashboard'),
]
