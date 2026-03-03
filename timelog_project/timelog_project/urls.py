from django.contrib import admin
from django.contrib.admin import AdminSite
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

# 後台只允許平台級 superuser，前台店家帳號無法進入 /admin/
AdminSite.has_permission = lambda self, request: (
    request.user.is_active and request.user.is_superuser
)

admin.site.site_header = "時間日誌管理系統"
admin.site.site_title = "時間日誌"
admin.site.index_title = "歡迎使用時間日誌管理"

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("core.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
