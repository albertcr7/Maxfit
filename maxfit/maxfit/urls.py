from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('booking.urls')),  # 👈 main site
]

from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    # your existing URL patterns...
]

if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
