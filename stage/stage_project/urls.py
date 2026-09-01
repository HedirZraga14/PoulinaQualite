from django.contrib import admin
from django.urls import include, path
from django.conf import settings
from django.conf.urls.static import static
from user.monitoring import health_view, metrics_view

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/auth/', include('user.urls')),
    path('monitoring/health/', health_view),
    path('monitoring/metrics/', metrics_view),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
