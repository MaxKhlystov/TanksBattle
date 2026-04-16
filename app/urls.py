from django.contrib import admin
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from django.conf import settings
from django.conf.urls.static import static
from tanks.views import AllDataView

from tanks.api import (
    NationViewSet, LevelViewSet, CrewmanViewSet, TankViewSet,
    BattleRecordViewSet, UserViewSet
)

router = DefaultRouter()
router.register("nations", NationViewSet, basename="nation")
router.register("levels", LevelViewSet, basename="level")
router.register("crewman", CrewmanViewSet, basename="crewman")
router.register("tanks", TankViewSet, basename="tank")
router.register("battles", BattleRecordViewSet, basename="battle")
router.register("user", UserViewSet, basename="user")

# Основные URL-паттерны
urlpatterns = [
    path('', AllDataView.as_view()),
    path('admin/', admin.site.urls),
    path('api/', include(router.urls)),
]+ static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

