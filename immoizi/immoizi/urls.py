"""immoizi URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/3.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.http import HttpResponse
from django.urls import include, path, re_path
from django.views.static import serve
from django.views.decorators.csrf import csrf_exempt
from graphene_django.views import GraphQLView
from products.schema import schema
from products.views import upload_property_document, upload_property_media
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('healthz', lambda request: HttpResponse('ok'), name='healthz'),
    path('admin/', admin.site.urls),
    path('i18n/', include('django.conf.urls.i18n')),
    path("graphql", csrf_exempt(GraphQLView.as_view(graphiql=settings.DEBUG, schema=schema))),
    path('api/properties/<int:property_id>/media', upload_property_media, name='upload_property_media'),
    path('api/properties/<int:property_id>/documents', upload_property_document, name='upload_property_document'),
    #path('image_upload', hotel_image_view, name='image_upload'),
    #path('success', success, name='success'),
]

if settings.DEBUG:
        urlpatterns += static(settings.MEDIA_URL,
                              document_root=settings.MEDIA_ROOT)
elif not settings.USE_CLOUDINARY:
    # Without Cloudinary, still serve uploads so a test deployment works.
    # Files on Render's disk are lost on every deploy: set CLOUDINARY_URL.
    urlpatterns += [
        re_path(r'^media/(?P<path>.*)$', serve,
                {'document_root': settings.MEDIA_ROOT}),
    ]
# Add path for admin/campaign photo upload? security concern ???