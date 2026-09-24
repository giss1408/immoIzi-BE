from django.conf import settings
from django.core.files.storage import FileSystemStorage, default_storage
import os
import re


if getattr(settings, 'USE_CLOUDINARY', False):
    from cloudinary_storage.storage import MediaCloudinaryStorage

    class _PropertyCloudinaryStorage(MediaCloudinaryStorage):
        TAG = 'immoizi'

        def _tags_for_name(self, name):
            tags = ['immoizi']
            property_match = re.search(r'properties/(\d+)', name)
            if property_match:
                tags.append(f'property_{property_match.group(1)}')
            if '/images/' in name:
                tags.append('images')
            if '/videos/' in name:
                tags.append('videos')
            return tags

        def _upload(self, name, content):
            options = {
                'use_filename': True,
                'resource_type': self._get_resource_type(name),
                'tags': self._tags_for_name(name),
            }
            folder = os.path.dirname(name)
            if folder:
                options['folder'] = folder
            import cloudinary
            return cloudinary.uploader.upload(content, **options)

    class PropertyImageStorage(_PropertyCloudinaryStorage):
        RESOURCE_TYPE = 'image'

    class PropertyVideoStorage(_PropertyCloudinaryStorage):
        RESOURCE_TYPE = 'video'

    property_image_storage = PropertyImageStorage()
    property_video_storage = PropertyVideoStorage()
else:
    class PropertyImageStorage(FileSystemStorage):
        pass

    class PropertyVideoStorage(FileSystemStorage):
        pass

    property_image_storage = default_storage
    property_video_storage = default_storage
