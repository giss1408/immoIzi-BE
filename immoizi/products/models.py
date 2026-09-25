from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator
import builtins
import datetime
import os
import uuid
from decimal import Decimal
from PIL import Image
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from utils.imagesManager.imagesManager_upload import make_thumbnail
from .storage import property_image_storage, property_video_storage


MAX_IMAGE_UPLOAD_SIZE = 5 * 1024 * 1024
ALLOWED_IMAGE_EXTENSIONS = ['jpg', 'jpeg', 'png', 'webp']
MAX_VIDEO_UPLOAD_SIZE = 10 * 1024 * 1024
ALLOWED_VIDEO_EXTENSIONS = ['mp4', 'webm', 'mov']
ALLOWED_VIDEO_CONTENT_TYPES = ['video/mp4', 'video/webm', 'video/quicktime']


def property_image_upload_path(instance, filename):
    extension = os.path.splitext(filename)[1].lower()
    property_id = instance.pk or 'unassigned'
    return f"properties/{property_id}/images/{uuid.uuid4().hex}{extension}"


def property_video_upload_path(instance, filename):
    extension = os.path.splitext(filename)[1].lower()
    property_id = instance.pk or 'unassigned'
    return f"properties/{property_id}/videos/{uuid.uuid4().hex}{extension}"


def property_media_upload_path(instance, filename):
    extension = os.path.splitext(filename)[1].lower()
    return f"properties/media/{uuid.uuid4().hex}{extension}"


def property_document_upload_path(instance, filename):
    extension = os.path.splitext(filename)[1].lower()
    return f"properties/documents/{uuid.uuid4().hex}{extension}"


def validate_property_image(image):
    if image.size > MAX_IMAGE_UPLOAD_SIZE:
        raise ValidationError(_('Image files must be 5 MB or smaller.'))

    current_position = image.tell()
    try:
        with Image.open(image) as opened_image:
            opened_image.verify()
    except Exception as exc:
        raise ValidationError(_('Upload a valid image file.')) from exc
    finally:
        image.seek(current_position)


def validate_property_video(video):
    if video.size > MAX_VIDEO_UPLOAD_SIZE:
        raise ValidationError(_('Video files must be 10 MB or smaller.'))

    extension = os.path.splitext(getattr(video, 'name', ''))[1].lower().lstrip('.')
    if extension not in ALLOWED_VIDEO_EXTENSIONS:
        raise ValidationError(_('Upload a valid MP4, WebM, or MOV video file.'))

    content_type = getattr(video, 'content_type', '')
    if content_type and content_type not in ALLOWED_VIDEO_CONTENT_TYPES and content_type != 'application/octet-stream':
        raise ValidationError(_('Upload a valid MP4, WebM, or MOV video file.'))


property_image_validators = [
    FileExtensionValidator(allowed_extensions=ALLOWED_IMAGE_EXTENSIONS),
    validate_property_image,
]

property_video_validators = [
    FileExtensionValidator(allowed_extensions=ALLOWED_VIDEO_EXTENSIONS),
    validate_property_video,
]

# Model Category, immo categories like residence, Business, Commerce, Industrie...[ Miete - Kaufen ]
class Category(models.Model):
    title = models.CharField(max_length=50)

    class Meta:
        verbose_name_plural = 'Categories'

    def __str__(self):
        return self.title

# Model Tenant, nom et prenoms, ID, nbr de maisons, status payment, expire date. 
class Tenant(models.Model): # grocery
    user = models.ForeignKey(settings.AUTH_USER_MODEL, blank=True, null=True, on_delete=models.CASCADE)
    organization = models.ForeignKey('Organization', blank=True, null=True, on_delete=models.CASCADE, related_name='tenants')
    nomPrenoms = models.CharField(max_length=150)
    isbn = models.CharField(max_length=13)
    quantity = models.IntegerField()# nbr de maisons
    status_payment = models.BooleanField(default=False)
    expire_date = models.DateField(default=datetime.date.today)
    date_created = models.DateField(auto_now_add=True)


    class Meta:
        ordering = [ '-date_created' ]

    def __str__(self):
        return self.nomPrenoms


class Organization(models.Model):
    name = models.CharField(max_length=150)
    slug = models.SlugField(max_length=160, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class UserProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='real_estate_profile')
    phone = models.CharField(max_length=30, blank=True)
    preferred_city = models.CharField(max_length=100, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['user__username']

    def __str__(self):
        return str(self.user)


class LandlordProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='landlord_profile')
    organization = models.ForeignKey(Organization, blank=True, null=True, on_delete=models.CASCADE, related_name='landlords')
    display_name = models.CharField(max_length=150)
    phone = models.CharField(max_length=30, blank=True)
    is_verified = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['display_name']

    def __str__(self):
        return self.display_name


class TenantProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='tenant_profile')
    display_name = models.CharField(max_length=150)
    phone = models.CharField(max_length=30, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['display_name']

    def __str__(self):
        return self.display_name


class OrganizationMembership(models.Model):
    ROLE_OWNER = 'owner'
    ROLE_ADMIN = 'admin'
    ROLE_MANAGER = 'manager'
    ROLE_ACCOUNTANT = 'accountant'
    ROLE_AGENT = 'agent'
    ROLE_CHOICES = [
        (ROLE_OWNER, 'Owner'),
        (ROLE_ADMIN, 'Admin'),
        (ROLE_MANAGER, 'Property manager'),
        (ROLE_ACCOUNTANT, 'Accountant'),
        (ROLE_AGENT, 'Agent'),
    ]

    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='memberships')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='organization_memberships')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default=ROLE_MANAGER)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('organization', 'user')
        ordering = ['organization__name', 'user__username']

    def __str__(self):
        return f'{self.user} - {self.organization} ({self.role})'

# Model Descrition prix, surface, nbr de chambres
class Description(models.Model):  # book
    LISTING_DRAFT = 'draft'
    LISTING_AVAILABLE = 'available'
    LISTING_RESERVED = 'reserved'
    LISTING_RENTED = 'rented'
    LISTING_MAINTENANCE = 'maintenance'
    LISTING_ARCHIVED = 'archived'
    LISTING_SOLD = 'sold'
    RENTAL_LONG_TERM = 'long_term'
    RENTAL_SHORT_TERM = 'short_term'
    RENTAL_TYPE_CHOICES = [
        (RENTAL_LONG_TERM, 'Long term (monthly rent)'),
        (RENTAL_SHORT_TERM, 'Short term (per night / week)'),
    ]
    LISTING_STATUS_CHOICES = [
        (LISTING_DRAFT, 'Draft'),
        (LISTING_AVAILABLE, 'Available'),
        (LISTING_RESERVED, 'Reserved'),
        (LISTING_RENTED, 'Rented'),
        (LISTING_MAINTENANCE, 'Under maintenance'),
        (LISTING_ARCHIVED, 'Archived'),
        (LISTING_SOLD, 'Sold'),
    ]

    organization = models.ForeignKey(Organization, blank=True, null=True, on_delete=models.CASCADE, related_name='properties')
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, blank=True, null=True, on_delete=models.SET_NULL, related_name='created_properties')
    landlord = models.ForeignKey(LandlordProfile, blank=True, null=True, on_delete=models.PROTECT, related_name='properties')
    current_tenant = models.ForeignKey(TenantProfile, blank=True, null=True, on_delete=models.SET_NULL, related_name='current_properties')
    title = models.CharField(max_length=150)  # description du proprietaire
    country = models.CharField(max_length=100, default="Côte d'Ivoire")  # pays
    city = models.CharField(max_length=100, default='Abidjan')  # ville
    district = models.CharField(max_length=100, default='Marcory')  # quartier
    tenant = models.CharField(max_length=100, default='Anonyme')  # Nom du proprietaire ou agence
    isbn = models.CharField(max_length=13)  # numero d'inscription du tenant
    rooms = models.IntegerField()  # nbr de pieces
    surface_m2 = models.IntegerField(default=0)
    price = models.IntegerField()  # prix mensuel/ rent
    description = models.TextField()  # description detaillee du proprietaire
    status = models.BooleanField()  # oqp / libre
    listing_status = models.CharField(max_length=20, choices=LISTING_STATUS_CHOICES, default=LISTING_DRAFT)
    # Long term: `price` is the monthly rent. Short term (furnished stays of a
    # few nights or weeks): `price` is per night, `weekly_price` for 7 nights.
    rental_type = models.CharField(max_length=20, choices=RENTAL_TYPE_CHOICES, default=RENTAL_LONG_TERM, db_index=True)
    weekly_price = models.IntegerField(blank=True, null=True)
    date_created = models.DateField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    date_toEnter = models.DateField(default=datetime.date.today)  # Libre a partir de 
    category = models.ForeignKey(Category, related_name='description', on_delete=models.CASCADE)
    imageurl = models.URLField()
    product_tag = models.CharField(max_length=10)
    bailleur = models.ForeignKey(Tenant, blank=True, null=True, on_delete=models.CASCADE)

    # New fields for images
    main_image = models.ImageField(max_length=255, storage=property_image_storage, upload_to=property_image_upload_path, validators=property_image_validators, blank=True, null=True)
    thumbnail = models.ImageField(max_length=255, upload_to='descriptions/thumbnails/', blank=True, null=True)
    image_1 = models.ImageField(max_length=255, storage=property_image_storage, upload_to=property_image_upload_path, validators=property_image_validators, blank=True, null=True)
    image_2 = models.ImageField(max_length=255, storage=property_image_storage, upload_to=property_image_upload_path, validators=property_image_validators, blank=True, null=True)
    image_3 = models.ImageField(max_length=255, storage=property_image_storage, upload_to=property_image_upload_path, validators=property_image_validators, blank=True, null=True)
    image_4 = models.ImageField(max_length=255, storage=property_image_storage, upload_to=property_image_upload_path, validators=property_image_validators, blank=True, null=True)
    image_5 = models.ImageField(max_length=255, storage=property_image_storage, upload_to=property_image_upload_path, validators=property_image_validators, blank=True, null=True)
    image_6 = models.ImageField(max_length=255, storage=property_image_storage, upload_to=property_image_upload_path, validators=property_image_validators, blank=True, null=True)
    image_7 = models.ImageField(max_length=255, storage=property_image_storage, upload_to=property_image_upload_path, validators=property_image_validators, blank=True, null=True)
    image_8 = models.ImageField(max_length=255, storage=property_image_storage, upload_to=property_image_upload_path, validators=property_image_validators, blank=True, null=True)
    image_9 = models.ImageField(max_length=255, storage=property_image_storage, upload_to=property_image_upload_path, validators=property_image_validators, blank=True, null=True)
    description_video = models.FileField(max_length=255, storage=property_video_storage, upload_to=property_video_upload_path, validators=property_video_validators, blank=True, null=True)
    description_video_2 = models.FileField(max_length=255, storage=property_video_storage, upload_to=property_video_upload_path, validators=property_video_validators, blank=True, null=True)
    description_video_3 = models.FileField(max_length=255, storage=property_video_storage, upload_to=property_video_upload_path, validators=property_video_validators, blank=True, null=True)
    description_video_4 = models.FileField(max_length=255, storage=property_video_storage, upload_to=property_video_upload_path, validators=property_video_validators, blank=True, null=True)
    description_video_5 = models.FileField(max_length=255, storage=property_video_storage, upload_to=property_video_upload_path, validators=property_video_validators, blank=True, null=True)
    is_archived = models.BooleanField(default=False)
    archived_at = models.DateTimeField(blank=True, null=True)
    deleted_at = models.DateTimeField(blank=True, null=True)
    is_test_data = models.BooleanField(default=False, help_text=_('Marks this listing as demo/test data for QA.'))

    class Meta:
        ordering = ['-date_created']

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if self.main_image and not self.thumbnail:
            self.thumbnail = make_thumbnail(self.main_image, size=(300, 200))
        super().save(*args, **kwargs)


class PropertyMedia(models.Model):
    MEDIA_IMAGE = 'image'
    MEDIA_VIDEO = 'video'
    MEDIA_EXTERNAL_VIDEO = 'external_video'
    MEDIA_TYPE_CHOICES = [
        (MEDIA_IMAGE, 'Image'),
        (MEDIA_VIDEO, 'Video'),
        (MEDIA_EXTERNAL_VIDEO, 'External video'),
    ]

    property = models.ForeignKey(Description, on_delete=models.CASCADE, related_name='media')
    organization = models.ForeignKey(Organization, blank=True, null=True, on_delete=models.CASCADE, related_name='property_media')
    media_type = models.CharField(max_length=20, choices=MEDIA_TYPE_CHOICES)
    file = models.FileField(max_length=255, upload_to=property_media_upload_path, blank=True, null=True)
    external_url = models.URLField(blank=True, null=True)
    caption = models.CharField(max_length=180, blank=True)
    position = models.PositiveIntegerField(default=0)
    is_primary = models.BooleanField(default=False)
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, blank=True, null=True, on_delete=models.SET_NULL, related_name='uploaded_property_media')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['position', 'created_at']

    def clean(self):
        if self.media_type == self.MEDIA_EXTERNAL_VIDEO and not self.external_url:
            raise ValidationError({'external_url': _('External video media requires a URL.')})
        if self.media_type in [self.MEDIA_IMAGE, self.MEDIA_VIDEO] and not self.file:
            raise ValidationError({'file': _('Uploaded media requires a file.')})
        if self.file and self.media_type == self.MEDIA_VIDEO:
            validate_property_video(self.file)
        if self.file and self.media_type == self.MEDIA_IMAGE:
            validate_property_image(self.file)

    def __str__(self):
        return f'{self.property} - {self.media_type}'


class PropertyDocument(models.Model):
    DOCUMENT_LEASE = 'lease'
    DOCUMENT_INVOICE = 'invoice'
    DOCUMENT_RECEIPT = 'receipt'
    DOCUMENT_INSPECTION = 'inspection'
    DOCUMENT_ID = 'identity'
    DOCUMENT_OTHER = 'other'
    DOCUMENT_TYPE_CHOICES = [
        (DOCUMENT_LEASE, 'Lease'),
        (DOCUMENT_INVOICE, 'Invoice'),
        (DOCUMENT_RECEIPT, 'Receipt'),
        (DOCUMENT_INSPECTION, 'Inspection'),
        (DOCUMENT_ID, 'Identity'),
        (DOCUMENT_OTHER, 'Other'),
    ]
    VISIBILITY_INTERNAL = 'internal'
    VISIBILITY_OWNER = 'owner'
    VISIBILITY_TENANT = 'tenant'
    VISIBILITY_CHOICES = [
        (VISIBILITY_INTERNAL, 'Internal'),
        (VISIBILITY_OWNER, 'Owner'),
        (VISIBILITY_TENANT, 'Tenant'),
    ]

    property = models.ForeignKey(Description, on_delete=models.CASCADE, related_name='documents')
    organization = models.ForeignKey(Organization, blank=True, null=True, on_delete=models.CASCADE, related_name='property_documents')
    title = models.CharField(max_length=160)
    document_type = models.CharField(max_length=30, choices=DOCUMENT_TYPE_CHOICES, default=DOCUMENT_OTHER)
    visibility = models.CharField(max_length=20, choices=VISIBILITY_CHOICES, default=VISIBILITY_INTERNAL)
    file = models.FileField(max_length=255, upload_to=property_document_upload_path)
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, blank=True, null=True, on_delete=models.SET_NULL, related_name='uploaded_property_documents')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.title


class Lease(models.Model):
    STATUS_DRAFT = 'draft'
    STATUS_ACTIVE = 'active'
    STATUS_ENDED = 'ended'
    STATUS_TERMINATED = 'terminated'
    STATUS_CHOICES = [
        (STATUS_DRAFT, 'Draft'),
        (STATUS_ACTIVE, 'Active'),
        (STATUS_ENDED, 'Ended'),
        (STATUS_TERMINATED, 'Terminated'),
    ]

    property = models.ForeignKey(Description, on_delete=models.CASCADE, related_name='leases')
    organization = models.ForeignKey(Organization, blank=True, null=True, on_delete=models.CASCADE, related_name='leases')
    tenant = models.ForeignKey(Tenant, on_delete=models.PROTECT, related_name='leases')
    tenant_profile = models.ForeignKey(TenantProfile, blank=True, null=True, on_delete=models.PROTECT, related_name='leases')
    start_date = models.DateField()
    end_date = models.DateField(blank=True, null=True)
    rent_amount = models.DecimalField(max_digits=12, decimal_places=2)
    deposit_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_DRAFT)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-start_date']

    def clean(self):
        if self.end_date and self.end_date < self.start_date:
            raise ValidationError({'end_date': _('End date must be after start date.')})

    def __str__(self):
        return f'{self.property} - {self.tenant}'


class RentPayment(models.Model):
    STATUS_PENDING = 'pending'
    STATUS_PAID = 'paid'
    STATUS_LATE = 'late'
    STATUS_CANCELLED = 'cancelled'
    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pending'),
        (STATUS_PAID, 'Paid'),
        (STATUS_LATE, 'Late'),
        (STATUS_CANCELLED, 'Cancelled'),
    ]

    lease = models.ForeignKey(Lease, on_delete=models.CASCADE, related_name='payments')
    organization = models.ForeignKey(Organization, blank=True, null=True, on_delete=models.CASCADE, related_name='rent_payments')
    due_date = models.DateField()
    paid_at = models.DateTimeField(blank=True, null=True)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    reference = models.CharField(max_length=120, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-due_date']

    def __str__(self):
        return f'{self.lease} - {self.amount}'


class MaintenanceRequest(models.Model):
    PRIORITY_LOW = 'low'
    PRIORITY_NORMAL = 'normal'
    PRIORITY_HIGH = 'high'
    PRIORITY_URGENT = 'urgent'
    PRIORITY_CHOICES = [
        (PRIORITY_LOW, 'Low'),
        (PRIORITY_NORMAL, 'Normal'),
        (PRIORITY_HIGH, 'High'),
        (PRIORITY_URGENT, 'Urgent'),
    ]
    STATUS_OPEN = 'open'
    STATUS_IN_PROGRESS = 'in_progress'
    STATUS_RESOLVED = 'resolved'
    STATUS_CANCELLED = 'cancelled'
    STATUS_CHOICES = [
        (STATUS_OPEN, 'Open'),
        (STATUS_IN_PROGRESS, 'In progress'),
        (STATUS_RESOLVED, 'Resolved'),
        (STATUS_CANCELLED, 'Cancelled'),
    ]

    property = models.ForeignKey(Description, on_delete=models.CASCADE, related_name='maintenance_requests')
    organization = models.ForeignKey(Organization, blank=True, null=True, on_delete=models.CASCADE, related_name='maintenance_requests')
    title = models.CharField(max_length=160)
    description = models.TextField()
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default=PRIORITY_NORMAL)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_OPEN)
    reported_by = models.ForeignKey(settings.AUTH_USER_MODEL, blank=True, null=True, on_delete=models.SET_NULL, related_name='reported_maintenance_requests')
    assigned_to = models.ForeignKey(settings.AUTH_USER_MODEL, blank=True, null=True, on_delete=models.SET_NULL, related_name='assigned_maintenance_requests')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.title


class PropertyInterestRequest(models.Model):
    STATUS_PENDING = 'pending'
    STATUS_REVIEWING = 'reviewing'
    STATUS_ACCEPTED = 'accepted'
    STATUS_REJECTED = 'rejected'
    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pending'),
        (STATUS_REVIEWING, 'Reviewing'),
        (STATUS_ACCEPTED, 'Accepted'),
        (STATUS_REJECTED, 'Rejected'),
    ]

    property = models.ForeignKey(Description, on_delete=models.CASCADE, related_name='interest_requests')
    applicant = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='property_interest_requests')
    profession = models.CharField(max_length=120)
    salary_range = models.CharField(max_length=80)
    employer = models.CharField(max_length=160, blank=True)
    occupants_count = models.PositiveIntegerField(default=1)
    lease_start_date = models.DateField()
    message = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.property} - {self.applicant}'

    # An unanswered request stops blocking a new one after this delay.
    EXPIRY_DAYS = 6
    OPEN_STATUSES = (STATUS_PENDING, STATUS_REVIEWING)

    # builtins.property: the `property` field above shadows the decorator.
    @builtins.property
    def expires_at(self):
        return self.created_at + datetime.timedelta(days=self.EXPIRY_DAYS)

    @builtins.property
    def is_expired(self):
        return self.status in self.OPEN_STATUSES and timezone.now() >= self.expires_at

    @classmethod
    def open_request(cls, applicant, property_obj):
        """The applicant's unanswered, unexpired request for this property."""
        cutoff = timezone.now() - datetime.timedelta(days=cls.EXPIRY_DAYS)
        return cls.objects.filter(
            applicant=applicant,
            property=property_obj,
            status__in=cls.OPEN_STATUSES,
            created_at__gt=cutoff,
        ).order_by('-created_at').first()


class Notification(models.Model):
    recipient = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='notifications')
    organization = models.ForeignKey(Organization, blank=True, null=True, on_delete=models.CASCADE, related_name='notifications')
    property = models.ForeignKey(Description, blank=True, null=True, on_delete=models.CASCADE, related_name='notifications')
    interest_request = models.ForeignKey(PropertyInterestRequest, blank=True, null=True, on_delete=models.CASCADE, related_name='notifications')
    notification_type = models.CharField(max_length=80)
    title = models.CharField(max_length=160)
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.recipient} - {self.title}'


class PropertyInterestMessage(models.Model):
    TYPE_MESSAGE = 'message'
    TYPE_VISIT_PROPOSAL = 'visit_proposal'
    TYPE_VISIT_CONFIRMATION = 'visit_confirmation'
    TYPE_VISIT_DECLINED = 'visit_declined'
    TYPE_CHOICES = [
        (TYPE_MESSAGE, 'Message'),
        (TYPE_VISIT_PROPOSAL, 'Visit proposal'),
        (TYPE_VISIT_CONFIRMATION, 'Visit confirmation'),
        (TYPE_VISIT_DECLINED, 'Visit declined'),
    ]

    interest_request = models.ForeignKey(PropertyInterestRequest, on_delete=models.CASCADE, related_name='messages')
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='property_interest_messages')
    message = models.TextField()
    message_type = models.CharField(max_length=32, choices=TYPE_CHOICES, default=TYPE_MESSAGE)
    proposed_visit_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f'{self.sender} - {self.interest_request_id}'


class AuditLog(models.Model):
    organization = models.ForeignKey(Organization, blank=True, null=True, on_delete=models.CASCADE, related_name='audit_logs')
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, blank=True, null=True, on_delete=models.SET_NULL, related_name='audit_logs')
    action = models.CharField(max_length=80)
    target_type = models.CharField(max_length=80)
    target_id = models.PositiveIntegerField(blank=True, null=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.action} {self.target_type}'
    
# models.py Test upload images
class Hotel(models.Model):
    name = models.CharField(max_length=50)
    hotel_Main_Img = models.ImageField(max_length=255, upload_to='images/', validators=property_image_validators)
    #thumbnail = models.ImageField(upload_to='images/')
 
    '''
    def save(self, *args, **kwargs):
        self.thumbnail = make_thumbnail(self.hotel_Main_Img, size=(100, 100))
        
        super().save(*args, **kwargs)
        '''

'''
# import the `make_thumbnail` function
from some_file import make_thumbnail

class MyModel(models.Model):
    image = models.ImageField(max_length=255)
    thumbnail = models.ImageField(max_length=255)

    def save(self, *args, **kwargs):
        self.thumbnail = make_thumbnail(self.image, size=(100, 100))

        super().save(*args, **kwargs)
'''