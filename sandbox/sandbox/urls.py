from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('', include('core.urls')),
    path('rooms/', include('rooms.urls')),
    path('admin/', admin.site.urls),
    path('events/', include('ds_broadcaster.urls')),
]
