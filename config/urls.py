from django.conf import settings
from django.contrib import admin
from django.urls import include, path, re_path
from django.views.static import serve

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('biblioteca.urls')),
]

# Portadas subidas. En local siempre; en producción solo si SERVE_MEDIA=True (suficiente para
# una demo en Render; en un proyecto real irían a un almacenamiento externo tipo S3).
if settings.DEBUG or settings.SERVE_MEDIA:
    urlpatterns += [re_path(r'^media/(?P<path>.*)$', serve, {'document_root': settings.MEDIA_ROOT})]
