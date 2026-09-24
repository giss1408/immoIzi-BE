import graphene
from django.contrib.auth import authenticate
from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.utils.translation import gettext_lazy as _
from graphene_django import DjangoObjectType
from .middleware import issue_token
from .models import (
    AuditLog,
    Category,
    Description,
    LandlordProfile,
    Lease,
    MaintenanceRequest,
    Notification,
    PropertyInterestMessage,
    PropertyInterestRequest,
    Organization,
    OrganizationMembership,
    PropertyDocument,
    PropertyMedia,
    RentPayment,
    Tenant,
    TenantProfile,
    UserProfile,
)


def require_authenticated_user(info):
    user = info.context.user
    if not user.is_authenticated:
        raise PermissionDenied(_("Authentication is required."))
    return user


def organization_ids_for_user(user):
    return OrganizationMembership.objects.filter(
        user=user,
        is_active=True,
    ).values_list('organization_id', flat=True)


def organizations_for_user(user):
    queryset = Organization.objects.all()
    if user.is_staff or user.is_superuser:
        return queryset
    return queryset.filter(memberships__user=user, memberships__is_active=True).distinct()


def is_landlord_user(user):
    return hasattr(user, 'landlord_profile')


def is_tenant_user(user):
    return hasattr(user, 'tenant_profile')


def public_descriptions_queryset():
    return Description.objects.select_related('category', 'landlord').filter(
        listing_status=Description.LISTING_AVAILABLE,
        is_archived=False,
        deleted_at__isnull=True,
    )


def landlord_properties_for_user(user):
    queryset = Description.objects.select_related('category', 'landlord', 'current_tenant', 'bailleur')
    if user.is_staff or user.is_superuser:
        return queryset.all()
    return queryset.filter(
        Q(landlord__user=user) |
        Q(created_by=user) |
        Q(organization_id__in=organization_ids_for_user(user))
    ).distinct()


def tenant_properties_for_user(user):
    queryset = Description.objects.select_related('category', 'landlord', 'current_tenant', 'bailleur')
    if user.is_staff or user.is_superuser:
        return queryset.all()
    return queryset.filter(
        Q(current_tenant__user=user) |
        Q(leases__tenant_profile__user=user, leases__status=Lease.STATUS_ACTIVE) |
        Q(leases__tenant__user=user, leases__status=Lease.STATUS_ACTIVE)
    ).distinct()


def descriptions_for_user(user):
    queryset = Description.objects.select_related('category', 'bailleur', 'landlord', 'current_tenant')
    if user.is_staff or user.is_superuser:
        return queryset.all()
    return queryset.filter(
        Q(bailleur__user=user) |
        Q(landlord__user=user) |
        Q(current_tenant__user=user) |
        Q(created_by=user) |
        Q(organization_id__in=organization_ids_for_user(user)) |
        Q(leases__tenant_profile__user=user, leases__status=Lease.STATUS_ACTIVE) |
        Q(leases__tenant__user=user, leases__status=Lease.STATUS_ACTIVE)
    ).distinct()


def tenants_for_user(user):
    queryset = Tenant.objects.all()
    if user.is_staff or user.is_superuser:
        return queryset
    return queryset.filter(
        Q(user=user) |
        Q(organization_id__in=organization_ids_for_user(user))
    ).distinct()


def organization_scoped_queryset(user, queryset):
    if user.is_staff or user.is_superuser:
        return queryset
    return queryset.filter(organization_id__in=organization_ids_for_user(user)).distinct()


def property_scoped_queryset(user, queryset):
    if user.is_staff or user.is_superuser:
        return queryset
    return queryset.filter(
        Q(property__bailleur__user=user) |
        Q(property__landlord__user=user) |
        Q(property__current_tenant__user=user) |
        Q(property__created_by=user) |
        Q(property__leases__tenant_profile__user=user, property__leases__status=Lease.STATUS_ACTIVE) |
        Q(property__leases__tenant__user=user, property__leases__status=Lease.STATUS_ACTIVE) |
        Q(property__organization_id__in=organization_ids_for_user(user)) |
        Q(organization_id__in=organization_ids_for_user(user))
    ).distinct()


def tenant_documents_for_user(user):
    queryset = PropertyDocument.objects.select_related('property', 'organization', 'uploaded_by')
    if user.is_staff or user.is_superuser:
        return queryset
    return queryset.filter(
        visibility=PropertyDocument.VISIBILITY_TENANT,
    ).filter(
        Q(property__current_tenant__user=user) |
        Q(property__leases__tenant_profile__user=user, property__leases__status=Lease.STATUS_ACTIVE) |
        Q(property__leases__tenant__user=user, property__leases__status=Lease.STATUS_ACTIVE)
    ).distinct()

# Category Type
class CategoryType(DjangoObjectType):
    class Meta:
        model = Category
        fields = ('id', 'title')


class OrganizationType(DjangoObjectType):
    class Meta:
        model = Organization
        fields = ('id', 'name', 'slug', 'created_at')


class OrganizationMembershipType(DjangoObjectType):
    class Meta:
        model = OrganizationMembership
        fields = ('id', 'organization', 'user', 'role', 'is_active', 'created_at')


class UserProfileType(DjangoObjectType):
    class Meta:
        model = UserProfile
        fields = ('id', 'user', 'phone', 'preferred_city', 'created_at')


class LandlordProfileType(DjangoObjectType):
    class Meta:
        model = LandlordProfile
        fields = ('id', 'user', 'organization', 'display_name', 'phone', 'is_verified', 'created_at')


class TenantProfileType(DjangoObjectType):
    class Meta:
        model = TenantProfile
        fields = ('id', 'user', 'display_name', 'phone', 'created_at')


class MeType(graphene.ObjectType):
    id = graphene.ID()
    username = graphene.String()
    email = graphene.String()
    is_seeker = graphene.Boolean()
    is_landlord = graphene.Boolean()
    is_tenant = graphene.Boolean()
    user_profile = graphene.Field(UserProfileType)
    landlord_profile = graphene.Field(LandlordProfileType)
    tenant_profile = graphene.Field(TenantProfileType)

    def resolve_id(user, info):
        return user.id

    def resolve_is_seeker(user, info):
        return hasattr(user, 'real_estate_profile')

    def resolve_is_landlord(user, info):
        return is_landlord_user(user)

    def resolve_is_tenant(user, info):
        return is_tenant_user(user)

    def resolve_user_profile(user, info):
        return getattr(user, 'real_estate_profile', None)

    def resolve_landlord_profile(user, info):
        return getattr(user, 'landlord_profile', None)

    def resolve_tenant_profile(user, info):
        return getattr(user, 'tenant_profile', None)

class UpdateCategory(graphene.Mutation):
    class Arguments:
        id = graphene.ID(required=True)
        title = graphene.String(required=True)

    category = graphene.Field(CategoryType)

    @classmethod
    def mutate(cls, root, info, id, title):
        require_authenticated_user(info)
        category = Category.objects.get(pk=id)
        category.title = title
        category.save()
        return UpdateCategory(category=category)

class CreateCategory(graphene.Mutation):
    class Arguments:
        title = graphene.String(required=True)

    category = graphene.Field(CategoryType)

    @classmethod
    def mutate(cls, root, info, title):
        require_authenticated_user(info)
        category = Category.objects.create(title=title)
        return CreateCategory(category=category)
def _build_absolute_url(info, file_field):
    if not file_field:
        return None
    request = info.context
    try:
        url = file_field.url
    except ValueError:
        return None
    return request.build_absolute_uri(url) if request else url


# Description Type
class DescriptionType(DjangoObjectType):
    main_image_url = graphene.String()
    gallery_image_urls = graphene.List(graphene.String)
    gallery_image_slots = graphene.List(graphene.String)
    video_url = graphene.String()
    video_urls = graphene.List(graphene.String)
    has_video = graphene.Boolean()

    class Meta:
        model = Description
        fields = (
            'id', 'organization', 'created_by', 'landlord', 'current_tenant', 'title', 'tenant', 'country', 'city', 'district', 'isbn',
            'rooms', 'price', 'description', 'status', 'date_created',
            'date_toEnter', 'category', 'imageurl', 'product_tag', 'bailleur', 'thumbnail',
            'image_1', 'image_2', 'image_3', 'image_4', 'image_5', 'image_6', 'image_7', 'image_8', 'image_9',
            'main_image', 'description_video', 'description_video_2', 'description_video_3', 'description_video_4', 'description_video_5',
            'surface_m2', 'listing_status', 'updated_at', 'is_archived', 'archived_at', 'deleted_at', 'is_test_data',
        )

    def resolve_main_image_url(self, info):
        return _build_absolute_url(info, self.main_image) or self.imageurl or None

    def resolve_gallery_image_urls(self, info):
        return [
            url for url in (
                _build_absolute_url(info, self.image_1),
                _build_absolute_url(info, self.image_2),
                _build_absolute_url(info, self.image_3),
                _build_absolute_url(info, self.image_4),
                _build_absolute_url(info, self.image_5),
                _build_absolute_url(info, self.image_6),
                _build_absolute_url(info, self.image_7),
                _build_absolute_url(info, self.image_8),
                _build_absolute_url(info, self.image_9),
            ) if url
        ]

    def resolve_gallery_image_slots(self, info):
        return [
            slot for slot, field in (
                ('image_1', self.image_1), ('image_2', self.image_2), ('image_3', self.image_3),
                ('image_4', self.image_4), ('image_5', self.image_5), ('image_6', self.image_6),
                ('image_7', self.image_7), ('image_8', self.image_8), ('image_9', self.image_9),
            ) if field
        ]

    def resolve_video_url(self, info):
        return _build_absolute_url(info, self.description_video)

    def resolve_video_urls(self, info):
        return [
            url for url in (
                _build_absolute_url(info, self.description_video),
                _build_absolute_url(info, self.description_video_2),
                _build_absolute_url(info, self.description_video_3),
                _build_absolute_url(info, self.description_video_4),
                _build_absolute_url(info, self.description_video_5),
            ) if url
        ]

    def resolve_has_video(self, info):
        return bool(self.description_video or self.description_video_2 or self.description_video_3)


class PropertyMediaType(DjangoObjectType):
    class Meta:
        model = PropertyMedia
        fields = ('id', 'property', 'organization', 'media_type', 'file', 'external_url', 'caption', 'position', 'is_primary', 'uploaded_by', 'created_at')


class PropertyDocumentType(DjangoObjectType):
    class Meta:
        model = PropertyDocument
        fields = ('id', 'property', 'organization', 'title', 'document_type', 'visibility', 'file', 'uploaded_by', 'created_at')


class LeaseType(DjangoObjectType):
    class Meta:
        model = Lease
        fields = ('id', 'property', 'organization', 'tenant', 'tenant_profile', 'start_date', 'end_date', 'rent_amount', 'deposit_amount', 'status', 'created_at')


class RentPaymentType(DjangoObjectType):
    class Meta:
        model = RentPayment
        fields = ('id', 'lease', 'organization', 'due_date', 'paid_at', 'amount', 'status', 'reference', 'notes', 'created_at')


class MaintenanceRequestType(DjangoObjectType):
    class Meta:
        model = MaintenanceRequest
        fields = ('id', 'property', 'organization', 'title', 'description', 'priority', 'status', 'reported_by', 'assigned_to', 'created_at', 'updated_at')


class PropertyInterestRequestType(DjangoObjectType):
    class Meta:
        model = PropertyInterestRequest
        fields = ('id', 'property', 'applicant', 'profession', 'salary_range', 'employer', 'occupants_count', 'lease_start_date', 'message', 'status', 'created_at', 'updated_at')


class NotificationType(DjangoObjectType):
    class Meta:
        model = Notification
        fields = ('id', 'organization', 'property', 'interest_request', 'notification_type', 'title', 'message', 'is_read', 'created_at')


class PropertyInterestMessageType(DjangoObjectType):
    sender = graphene.Field(MeType)

    class Meta:
        model = PropertyInterestMessage
        fields = ('id', 'interest_request', 'sender', 'message', 'message_type', 'proposed_visit_at', 'created_at')


class AuditLogType(DjangoObjectType):
    class Meta:
        model = AuditLog
        fields = ('id', 'organization', 'actor', 'action', 'target_type', 'target_id', 'metadata', 'created_at')

class DescriptionInput(graphene.InputObjectType):
    title = graphene.String()
    country = graphene.String()
    city = graphene.String()
    district = graphene.String()
    bailleur = graphene.String()
    status = graphene.String()
    listing_status = graphene.String()
    price = graphene.Int()


class CreateOrganization(graphene.Mutation):
    class Arguments:
        name = graphene.String(required=True)
        slug = graphene.String(required=True)

    organization = graphene.Field(OrganizationType)

    @classmethod
    def mutate(cls, root, info, name, slug):
        user = require_authenticated_user(info)
        organization = Organization.objects.create(name=name, slug=slug)
        OrganizationMembership.objects.create(
            organization=organization,
            user=user,
            role=OrganizationMembership.ROLE_OWNER,
        )
        AuditLog.objects.create(
            organization=organization,
            actor=user,
            action='organization.created',
            target_type='Organization',
            target_id=organization.id,
        )
        return CreateOrganization(organization=organization)


class CreateMaintenanceRequest(graphene.Mutation):
    class Arguments:
        property_id = graphene.ID(required=True)
        title = graphene.String(required=True)
        description = graphene.String(required=True)
        priority = graphene.String()

    maintenance_request = graphene.Field(MaintenanceRequestType)

    @classmethod
    def mutate(cls, root, info, property_id, title, description, priority=None):
        user = require_authenticated_user(info)
        property_obj = descriptions_for_user(user).get(pk=property_id)
        if is_tenant_user(user) and not tenant_properties_for_user(user).filter(pk=property_obj.pk).exists():
            raise PermissionDenied(_('Tenants can create maintenance requests only for their rented properties.'))
        maintenance_request = MaintenanceRequest.objects.create(
            property=property_obj,
            organization=property_obj.organization,
            title=title,
            description=description,
            priority=priority or MaintenanceRequest.PRIORITY_NORMAL,
            reported_by=user,
        )
        AuditLog.objects.create(
            organization=property_obj.organization,
            actor=user,
            action='maintenance.created',
            target_type='MaintenanceRequest',
            target_id=maintenance_request.id,
        )
        return CreateMaintenanceRequest(maintenance_request=maintenance_request)


class UpdateMaintenanceRequest(graphene.Mutation):
    class Arguments:
        id = graphene.ID(required=True)
        title = graphene.String()
        description = graphene.String()
        priority = graphene.String()
        status = graphene.String()

    maintenance_request = graphene.Field(MaintenanceRequestType)

    @classmethod
    def mutate(cls, root, info, id, title=None, description=None, priority=None, status=None):
        user = require_authenticated_user(info)
        request = property_scoped_queryset(user, MaintenanceRequest.objects.all()).get(pk=id)
        if title is not None:
            request.title = title
        if description is not None:
            request.description = description
        if priority is not None:
            request.priority = priority
        if status is not None:
            request.status = status
        request.save()
        AuditLog.objects.create(
            organization=request.organization,
            actor=user,
            action='maintenance.updated',
            target_type='MaintenanceRequest',
            target_id=request.id,
        )
        return UpdateMaintenanceRequest(maintenance_request=request)


class CreatePropertyInterestRequest(graphene.Mutation):
    class Arguments:
        property_id = graphene.ID(required=True)
        profession = graphene.String(required=True)
        salary_range = graphene.String(required=True)
        employer = graphene.String()
        occupants_count = graphene.Int(required=True)
        lease_start_date = graphene.Date(required=True)
        message = graphene.String()

    interest_request = graphene.Field(PropertyInterestRequestType)

    @classmethod
    def mutate(cls, root, info, property_id, profession, salary_range, occupants_count, lease_start_date, employer='', message=''):
        user = require_authenticated_user(info)
        try:
            property_obj = public_descriptions_queryset().get(pk=property_id)
        except Description.DoesNotExist:
            raise PermissionDenied(_('This listing is not available for applications.'))

        interest_request = PropertyInterestRequest.objects.create(
            property=property_obj,
            applicant=user,
            profession=profession,
            salary_range=salary_range,
            employer=employer or '',
            occupants_count=occupants_count,
            lease_start_date=lease_start_date,
            message=message or '',
        )
        recipient = property_obj.landlord.user if property_obj.landlord_id else property_obj.created_by
        if recipient:
            Notification.objects.create(
                recipient=recipient,
                organization=property_obj.organization,
                property=property_obj,
                interest_request=interest_request,
                notification_type='property_interest.created',
                title='Nouvel intérêt pour votre bien',
                message=f'{user.get_full_name() or user.username} souhaite louer « {property_obj.title} ».',
            )
        AuditLog.objects.create(
            organization=property_obj.organization,
            actor=user,
            action='property_interest.created',
            target_type='PropertyInterestRequest',
            target_id=interest_request.id,
        )
        return CreatePropertyInterestRequest(interest_request=interest_request)


class MarkNotificationRead(graphene.Mutation):
    class Arguments:
        notification_id = graphene.ID(required=True)

    notification = graphene.Field(NotificationType)

    @classmethod
    def mutate(cls, root, info, notification_id):
        user = require_authenticated_user(info)
        try:
            notification = Notification.objects.get(pk=notification_id, recipient=user)
        except Notification.DoesNotExist:
            raise PermissionDenied(_('Notification not found.'))
        notification.is_read = True
        notification.save(update_fields=['is_read'])
        return MarkNotificationRead(notification=notification)


class DeleteNotification(graphene.Mutation):
    class Arguments:
        notification_id = graphene.ID(required=True)

    deleted_notification_id = graphene.ID()

    @classmethod
    def mutate(cls, root, info, notification_id):
        user = require_authenticated_user(info)
        deleted, _ = Notification.objects.filter(pk=notification_id, recipient=user).delete()
        if not deleted:
            raise PermissionDenied(_('Notification not found.'))
        return DeleteNotification(deleted_notification_id=notification_id)


class SendPropertyInterestMessage(graphene.Mutation):
    class Arguments:
        interest_request_id = graphene.ID(required=True)
        message = graphene.String(required=True)
        message_type = graphene.String()
        proposed_visit_at = graphene.DateTime()

    interest_message = graphene.Field(PropertyInterestMessageType)

    @classmethod
    def mutate(cls, root, info, interest_request_id, message, message_type='message', proposed_visit_at=None):
        user = require_authenticated_user(info)
        if message_type not in {choice[0] for choice in PropertyInterestMessage.TYPE_CHOICES}:
            raise PermissionDenied(_('Invalid message type.'))
        if message_type == PropertyInterestMessage.TYPE_VISIT_PROPOSAL and proposed_visit_at is None:
            raise PermissionDenied(_('A visit proposal requires a date.'))
        try:
            interest_request = PropertyInterestRequest.objects.select_related('property__landlord__user', 'property__created_by', 'applicant').get(pk=interest_request_id)
        except PropertyInterestRequest.DoesNotExist:
            raise PermissionDenied(_('Interest request not found.'))

        property_obj = interest_request.property
        landlord_user_id = property_obj.landlord.user_id if property_obj.landlord_id else property_obj.created_by_id
        manager_access = (
            user.is_staff or user.is_superuser or
            user.id == landlord_user_id or
            user.id == property_obj.created_by_id or
            property_obj.organization_id in organization_ids_for_user(user)
        )
        if user.id != interest_request.applicant_id and not manager_access:
            raise PermissionDenied(_('You cannot access this conversation.'))
        recipient_id = interest_request.applicant_id if manager_access and user.id != interest_request.applicant_id else landlord_user_id
        if not recipient_id or recipient_id == user.id:
            raise PermissionDenied(_('No conversation recipient is configured.'))

        interest_message = PropertyInterestMessage.objects.create(
            interest_request=interest_request,
            sender=user,
            message=message.strip(),
            message_type=message_type,
            proposed_visit_at=proposed_visit_at,
        )
        if manager_access and interest_request.status == PropertyInterestRequest.STATUS_PENDING:
            interest_request.status = PropertyInterestRequest.STATUS_REVIEWING
            interest_request.save(update_fields=['status', 'updated_at'])
        title = {
            PropertyInterestMessage.TYPE_VISIT_PROPOSAL: 'Proposition de visite',
            PropertyInterestMessage.TYPE_VISIT_CONFIRMATION: 'Visite confirmée',
            PropertyInterestMessage.TYPE_VISIT_DECLINED: 'Visite refusée',
        }.get(message_type, 'Nouveau message concernant votre demande')
        Notification.objects.create(
            recipient_id=recipient_id,
            organization=property_obj.organization,
            property=property_obj,
            interest_request=interest_request,
            notification_type=f'property_interest.{message_type}',
            title=title,
            message=f'{user.get_full_name() or user.username} vous a écrit au sujet de « {property_obj.title} ».',
        )
        return SendPropertyInterestMessage(interest_message=interest_message)


class TokenAuth(graphene.Mutation):
    class Arguments:
        username = graphene.String(required=True)
        password = graphene.String(required=True)

    token = graphene.String()
    user = graphene.Field(MeType)

    @classmethod
    def mutate(cls, root, info, username, password):
        user = authenticate(info.context, username=username, password=password)
        if user is None:
            raise PermissionDenied(_('Invalid username or password.'))
        return TokenAuth(token=issue_token(user), user=user)

class CreateDescription(graphene.Mutation):
    class Arguments:
        input = DescriptionInput(required=True)

    description = graphene.Field(DescriptionType)

    @classmethod
    def mutate(cls, root, info, input):
        require_authenticated_user(info)
        description = Description.objects.create(
            title=input.title,
            country=input.country,
            city=input.city,
            district=input.district,
            bailleur=input.bailleur,
            status=input.status,
            price=input.price,
        )
        return CreateDescription(description=description)

class UpdateDescription(graphene.Mutation):
    class Arguments:
        id = graphene.ID(required=True)
        input = DescriptionInput(required=True)

    description = graphene.Field(DescriptionType)

    @classmethod
    def mutate(cls, root, info, id, input):
        user = require_authenticated_user(info)
        description = descriptions_for_user(user).get(pk=id)
        for field in ['title', 'bailleur', 'country', 'city', 'district', 'status', 'price']:
            setattr(description, field, getattr(input, field, getattr(description, field)))
        description.save()
        return UpdateDescription(description=description)


class UpdatePropertyListing(graphene.Mutation):
    """Lets a landlord edit the marketing content of their own listing (price + description only)."""

    class Arguments:
        property_id = graphene.ID(required=True)
        price = graphene.Int()
        description = graphene.String()

    property = graphene.Field(DescriptionType)

    @classmethod
    def mutate(cls, root, info, property_id, price=None, description=None):
        user = require_authenticated_user(info)
        try:
            listing = landlord_properties_for_user(user).get(pk=property_id)
        except Description.DoesNotExist:
            raise PermissionDenied(_('You can only edit your own listings.'))

        if price is not None:
            listing.price = price
        if description is not None:
            listing.description = description
        listing.save()

        AuditLog.objects.create(
            organization=listing.organization,
            actor=user,
            action='property.updated',
            target_type='Description',
            target_id=listing.id,
        )
        return UpdatePropertyListing(property=listing)

# Tenant Type
class TenantType(DjangoObjectType):
    class Meta:
        model = Tenant
        fields = (
            'id', 'nomPrenoms', 'isbn', 'quantity',
            'date_created', 'status_payment', 'expire_date',
        )

class Query(graphene.ObjectType):
    me = graphene.Field(MeType)
    categories = graphene.List(CategoryType)
    organizations = graphene.List(OrganizationType)
    organization_memberships = graphene.List(OrganizationMembershipType)
    user_profile = graphene.Field(UserProfileType)
    landlord_profile = graphene.Field(LandlordProfileType)
    tenant_profile = graphene.Field(TenantProfileType)
    public_descriptions = graphene.List(DescriptionType, first=graphene.Int(), offset=graphene.Int(), search=graphene.String(), city=graphene.String())
    descriptions = graphene.List(DescriptionType, first=graphene.Int(), offset=graphene.Int(), search=graphene.String(), listing_status=graphene.String())
    my_landlord_properties = graphene.List(DescriptionType, first=graphene.Int(), offset=graphene.Int(), search=graphene.String())
    my_tenant_properties = graphene.List(DescriptionType)
    my_tenant_leases = graphene.List(LeaseType)
    my_tenant_payments = graphene.List(RentPaymentType)
    my_tenant_documents = graphene.List(PropertyDocumentType)
    my_tenant_maintenance_requests = graphene.List(MaintenanceRequestType)
    tenants = graphene.List(TenantType)
    property_media = graphene.List(PropertyMediaType)
    property_documents = graphene.List(PropertyDocumentType)
    leases = graphene.List(LeaseType)
    rent_payments = graphene.List(RentPaymentType)
    maintenance_requests = graphene.List(MaintenanceRequestType)
    property_interest_requests = graphene.List(PropertyInterestRequestType)
    my_property_interest_requests = graphene.List(PropertyInterestRequestType)
    notifications = graphene.List(NotificationType)
    property_interest_messages = graphene.List(
        PropertyInterestMessageType,
        interest_request_id=graphene.ID(required=True),
    )
    audit_logs = graphene.List(AuditLogType)

    def resolve_me(self, info, **kwargs):
        return require_authenticated_user(info)

    def resolve_categories(self, info, **kwargs):
        require_authenticated_user(info)
        return Category.objects.all()

    def resolve_user_profile(self, info, **kwargs):
        user = require_authenticated_user(info)
        return getattr(user, 'real_estate_profile', None)

    def resolve_landlord_profile(self, info, **kwargs):
        user = require_authenticated_user(info)
        return getattr(user, 'landlord_profile', None)

    def resolve_tenant_profile(self, info, **kwargs):
        user = require_authenticated_user(info)
        return getattr(user, 'tenant_profile', None)

    def resolve_public_descriptions(self, info, first=None, offset=None, search=None, city=None, **kwargs):
        queryset = public_descriptions_queryset()
        if search:
            queryset = queryset.filter(
                Q(title__icontains=search) |
                Q(city__icontains=search) |
                Q(district__icontains=search)
            )
        if city:
            queryset = queryset.filter(city__iexact=city)
        if offset:
            queryset = queryset[offset:]
        if first:
            queryset = queryset[:first]
        return queryset

    def resolve_organizations(self, info, **kwargs):
        user = require_authenticated_user(info)
        return organizations_for_user(user)

    def resolve_organization_memberships(self, info, **kwargs):
        user = require_authenticated_user(info)
        return organization_scoped_queryset(user, OrganizationMembership.objects.select_related('organization', 'user'))

    def resolve_descriptions(self, info, first=None, offset=None, search=None, listing_status=None, **kwargs):
        user = require_authenticated_user(info)
        queryset = descriptions_for_user(user)
        if search:
            queryset = queryset.filter(
                Q(title__icontains=search) |
                Q(city__icontains=search) |
                Q(district__icontains=search)
            )
        if listing_status:
            queryset = queryset.filter(listing_status=listing_status)
        if offset:
            queryset = queryset[offset:]
        if first:
            queryset = queryset[:first]
        return queryset

    def resolve_my_landlord_properties(self, info, first=None, offset=None, search=None, **kwargs):
        user = require_authenticated_user(info)
        queryset = landlord_properties_for_user(user)
        if search:
            queryset = queryset.filter(
                Q(title__icontains=search) |
                Q(city__icontains=search) |
                Q(district__icontains=search)
            )
        if offset:
            queryset = queryset[offset:]
        if first:
            queryset = queryset[:first]
        return queryset

    def resolve_my_tenant_properties(self, info, **kwargs):
        user = require_authenticated_user(info)
        return tenant_properties_for_user(user)

    def resolve_my_tenant_leases(self, info, **kwargs):
        user = require_authenticated_user(info)
        queryset = Lease.objects.select_related('property', 'organization', 'tenant', 'tenant_profile')
        if user.is_staff or user.is_superuser:
            return queryset
        return queryset.filter(
            Q(tenant_profile__user=user) |
            Q(tenant__user=user)
        ).distinct()

    def resolve_my_tenant_payments(self, info, **kwargs):
        user = require_authenticated_user(info)
        queryset = RentPayment.objects.select_related('lease', 'organization', 'lease__property')
        if user.is_staff or user.is_superuser:
            return queryset
        return queryset.filter(
            Q(lease__tenant_profile__user=user) |
            Q(lease__tenant__user=user)
        ).distinct()

    def resolve_my_tenant_documents(self, info, **kwargs):
        user = require_authenticated_user(info)
        return tenant_documents_for_user(user)

    def resolve_my_tenant_maintenance_requests(self, info, **kwargs):
        user = require_authenticated_user(info)
        queryset = MaintenanceRequest.objects.select_related('property', 'organization', 'reported_by', 'assigned_to')
        if user.is_staff or user.is_superuser:
            return queryset
        return queryset.filter(
            Q(property__current_tenant__user=user) |
            Q(property__leases__tenant_profile__user=user, property__leases__status=Lease.STATUS_ACTIVE) |
            Q(property__leases__tenant__user=user, property__leases__status=Lease.STATUS_ACTIVE) |
            Q(reported_by=user)
        ).distinct()

    def resolve_tenants(self, info, **kwargs):
        user = require_authenticated_user(info)
        return tenants_for_user(user)

    def resolve_property_media(self, info, **kwargs):
        user = require_authenticated_user(info)
        return property_scoped_queryset(user, PropertyMedia.objects.select_related('property', 'organization', 'uploaded_by'))

    def resolve_property_documents(self, info, **kwargs):
        user = require_authenticated_user(info)
        return property_scoped_queryset(user, PropertyDocument.objects.select_related('property', 'organization', 'uploaded_by'))

    def resolve_leases(self, info, **kwargs):
        user = require_authenticated_user(info)
        return property_scoped_queryset(user, Lease.objects.select_related('property', 'organization', 'tenant'))

    def resolve_rent_payments(self, info, **kwargs):
        user = require_authenticated_user(info)
        queryset = RentPayment.objects.select_related('lease', 'organization', 'lease__property')
        if user.is_staff or user.is_superuser:
            return queryset
        return queryset.filter(
            Q(organization_id__in=organization_ids_for_user(user)) |
            Q(lease__property__bailleur__user=user) |
            Q(lease__property__created_by=user)
        ).distinct()

    def resolve_maintenance_requests(self, info, **kwargs):
        user = require_authenticated_user(info)
        return property_scoped_queryset(user, MaintenanceRequest.objects.select_related('property', 'organization', 'reported_by', 'assigned_to'))

    def resolve_property_interest_requests(self, info, **kwargs):
        user = require_authenticated_user(info)
        return PropertyInterestRequest.objects.filter(
            Q(property__landlord__user=user) |
            Q(property__created_by=user) |
            Q(property__organization_id__in=organization_ids_for_user(user))
        ).select_related('property', 'applicant').distinct()

    def resolve_my_property_interest_requests(self, info, **kwargs):
        user = require_authenticated_user(info)
        return PropertyInterestRequest.objects.filter(applicant=user).select_related('property', 'applicant')

    def resolve_notifications(self, info, **kwargs):
        user = require_authenticated_user(info)
        return Notification.objects.filter(recipient=user).select_related('property', 'interest_request')

    def resolve_property_interest_messages(self, info, interest_request_id, **kwargs):
        user = require_authenticated_user(info)
        try:
            interest_request = PropertyInterestRequest.objects.select_related('property__landlord__user', 'property__created_by').get(pk=interest_request_id)
        except PropertyInterestRequest.DoesNotExist:
            raise PermissionDenied(_('Interest request not found.'))
        property_obj = interest_request.property
        landlord_user_id = property_obj.landlord.user_id if property_obj.landlord_id else property_obj.created_by_id
        manager_access = (
            user.is_staff or user.is_superuser or
            user.id == landlord_user_id or
            user.id == property_obj.created_by_id or
            property_obj.organization_id in organization_ids_for_user(user)
        )
        if user.id != interest_request.applicant_id and not manager_access:
            raise PermissionDenied(_('You cannot access this conversation.'))
        return PropertyInterestMessage.objects.filter(interest_request=interest_request).select_related('sender')

    def resolve_audit_logs(self, info, **kwargs):
        user = require_authenticated_user(info)
        return organization_scoped_queryset(user, AuditLog.objects.select_related('organization', 'actor'))

class Mutation(graphene.ObjectType):
    token_auth = TokenAuth.Field()
    create_organization = CreateOrganization.Field()
    update_category = UpdateCategory.Field()
    create_category = CreateCategory.Field()
    create_description = CreateDescription.Field()
    update_description = UpdateDescription.Field()
    update_property_listing = UpdatePropertyListing.Field()
    create_maintenance_request = CreateMaintenanceRequest.Field()
    update_maintenance_request = UpdateMaintenanceRequest.Field()
    create_property_interest_request = CreatePropertyInterestRequest.Field()
    mark_notification_read = MarkNotificationRead.Field()
    delete_notification = DeleteNotification.Field()
    send_property_interest_message = SendPropertyInterestMessage.Field()

schema = graphene.Schema(query=Query, mutation=Mutation)
