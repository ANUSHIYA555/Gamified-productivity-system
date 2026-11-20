from django.contrib import admin
from django.urls import path, include, re_path
from django.shortcuts import render

def app_view(request):
    return render(request, 'index.html')

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include('core.urls')),
    path('', app_view, name='home'),
    re_path(r'^(?!api/|admin/|static/).*$', app_view, name='spa_fallback'),
]
