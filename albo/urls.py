
from django.contrib.admin.sites import all_sites

from django.urls import path

urlpatterns = [path(f'{site.name}/', site.urls) for site in all_sites if not site.name == 'admin']
# urlpatterns = i18n_patterns(*urlpatterns)
