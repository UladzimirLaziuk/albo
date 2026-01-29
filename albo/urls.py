
from django.contrib.admin.sites import all_sites
from django.conf.urls.static import static
from django.urls import path
from django.conf import settings

urlpatterns = [path(f'{site.name}/', site.urls) for site in all_sites] #if not site.name == 'admin'
urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
# urlpatterns = i18n_patterns(*urlpatterns)
