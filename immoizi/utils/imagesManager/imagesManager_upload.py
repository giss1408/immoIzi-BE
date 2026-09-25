from io import BytesIO
import os
import uuid
from django.core.files import File
from PIL import Image


Image.MAX_IMAGE_PIXELS = 20_000_000


def make_thumbnail(image, size=(100, 100)):
    """Makes thumbnails of given size from given image"""

    # The source may just have been uploaded, leaving it read to the end.
    if hasattr(image, 'seek'):
        image.seek(0)
    im = Image.open(image)
    im = im.convert("RGB") # convert mode
    im.thumbnail(size) # resize image
    thumb_io = BytesIO() # create a BytesIO object
    im.save(thumb_io, "JPEG", quality=85) # save image to BytesIO object
    # Rewind: remote storages (Cloudinary) upload from the current position,
    # which would otherwise be the end of the buffer ("Empty file").
    thumb_io.seek(0)
    basename = os.path.basename(os.path.splitext(image.name)[0])
    filename = f"{uuid.uuid4().hex}-{basename}.jpg"
    thumbnail = File(thumb_io, name=filename) # create a django friendly File object
    return thumbnail


def resize_for_upload(image, max_dimension=1600, quality=82):
    """Downscales a listing photo to a data-friendly size before it is stored.

    Camera photos are often 3000px+ and several MB; mobile users on limited data
    plans shouldn't have to download that just to see a property photo. Keeps the
    aspect ratio and caps the longest side at `max_dimension`.
    """

    im = Image.open(image)
    im = im.convert("RGB")
    im.thumbnail((max_dimension, max_dimension), Image.LANCZOS)
    buffer = BytesIO()
    im.save(buffer, "JPEG", quality=quality, optimize=True)
    buffer.seek(0)
    basename = os.path.basename(os.path.splitext(image.name)[0])
    filename = f"{basename}.jpg"
    return File(buffer, name=filename)