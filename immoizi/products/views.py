from django.core.exceptions import ValidationError
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods, require_POST

from .models import Description, PropertyDocument, validate_property_image, validate_property_video
from utils.imagesManager.imagesManager_upload import resize_for_upload

# Only these upload slots may be written by a landlord through this endpoint.
IMAGE_SLOTS = {'main_image', *(f'image_{index}' for index in range(1, 10))}
VIDEO_SLOTS = {'video', 'video_2', 'video_3', 'video_4', 'video_5'}


def _landlord_owns(user, description):
    if user.is_staff or user.is_superuser:
        return True
    if description.landlord_id and description.landlord.user_id == user.id:
        return True
    if description.created_by_id == user.id:
        return True
    return False


@csrf_exempt
@require_http_methods(['POST', 'DELETE'])
def upload_property_media(request, property_id):
    user = request.user
    if not user.is_authenticated:
        return JsonResponse({'error': 'Authentication is required.'}, status=401)

    try:
        description = Description.objects.select_related('landlord').get(pk=property_id)
    except Description.DoesNotExist:
        return JsonResponse({'error': 'Property not found.'}, status=404)

    if not _landlord_owns(user, description):
        return JsonResponse({'error': 'You can only upload media for your own listings.'}, status=403)

    if request.method == 'DELETE':
        slot = request.GET.get('slot') or request.POST.get('slot')
        if slot in VIDEO_SLOTS:
            field_name = 'description_video' if slot == 'video' else f'description_{slot}'
            field = getattr(description, field_name)
        elif slot in IMAGE_SLOTS:
            field = getattr(description, slot)
        else:
            return JsonResponse({'error': 'Invalid media slot.'}, status=400)

        if field:
            field.delete(save=False)
            description.save()
        return _media_response(request, description)

    slot = request.POST.get('slot', 'main_image')
    video_file = request.FILES.get('video')
    image_file = request.FILES.get('image')

    if not image_file and not video_file:
        return JsonResponse({'error': 'Provide an "image" or "video" file.'}, status=400)

    if image_file:
        if slot not in IMAGE_SLOTS:
            return JsonResponse({'error': f'Invalid slot. Use one of {sorted(IMAGE_SLOTS)}.'}, status=400)
        try:
            validate_property_image(image_file)
        except ValidationError as exc:
            return JsonResponse({'error': '; '.join(exc.messages)}, status=400)
        resized = resize_for_upload(image_file)
        getattr(description, slot).save(resized.name, resized, save=False)

    if video_file:
        try:
            validate_property_video(video_file)
        except ValidationError as exc:
            return JsonResponse({'error': '; '.join(exc.messages)}, status=400)
        video_slot = slot if slot in VIDEO_SLOTS else 'video'
        video_field_name = 'description_video' if video_slot == 'video' else f'description_{video_slot}'
        getattr(description, video_field_name).save(video_file.name, video_file, save=False)

    description.save()

    return _media_response(request, description)


def _media_response(request, description):
    video_fields = [
        description.description_video, description.description_video_2, description.description_video_3,
        description.description_video_4, description.description_video_5,
    ]
    image_fields = [
        (f'image_{index}', getattr(description, f'image_{index}'))
        for index in range(1, 10)
    ]
    return JsonResponse({
        'mainImageUrl': request.build_absolute_uri(description.main_image.url) if description.main_image else None,
        'galleryImageUrls': [
            request.build_absolute_uri(field.url) for _, field in image_fields if field
        ],
        'galleryImageSlots': [slot for slot, field in image_fields if field],
        'videoUrl': request.build_absolute_uri(video_fields[0].url) if video_fields[0] else None,
        'videoUrls': [request.build_absolute_uri(f.url) for f in video_fields if f],
    })


@csrf_exempt
@require_POST
def upload_property_document(request, property_id):
    user = request.user
    if not user.is_authenticated:
        return JsonResponse({'error': 'Authentication is required.'}, status=401)

    try:
        description = Description.objects.select_related('landlord').get(pk=property_id)
    except Description.DoesNotExist:
        return JsonResponse({'error': 'Property not found.'}, status=404)

    if not _landlord_owns(user, description):
        return JsonResponse({'error': 'You can only upload documents for your own listings.'}, status=403)

    document_file = request.FILES.get('file')
    title = request.POST.get('title', '').strip()
    if not document_file or not title:
        return JsonResponse({'error': 'Provide a title and a document file.'}, status=400)

    document = PropertyDocument.objects.create(
        property=description,
        organization=description.organization,
        title=title,
        document_type=PropertyDocument.DOCUMENT_LEASE,
        visibility=PropertyDocument.VISIBILITY_TENANT,
        file=document_file,
        uploaded_by=user,
    )
    return JsonResponse({
        'id': document.pk,
        'title': document.title,
        'documentType': document.document_type,
        'visibility': document.visibility,
        'fileUrl': request.build_absolute_uri(document.file.url),
        'propertyId': description.pk,
    }, status=201)

