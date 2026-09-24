from django.contrib import admin
from .models import (
	AuditLog,
	Category,
	Description,
	LandlordProfile,
	Lease,
	MaintenanceRequest,
	Notification,
	PropertyInterestMessage,
	Organization,
	OrganizationMembership,
	PropertyDocument,
	PropertyMedia,
	RentPayment,
	Tenant,
	TenantProfile,
	UserProfile,
)

# Register your models here.
admin.site.register(Category)


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
	list_display = ('title', 'recipient', 'is_read', 'created_at')
	list_filter = ('is_read', 'notification_type')
	search_fields = ('title', 'message', 'recipient__username', 'property__title')


@admin.register(PropertyInterestMessage)
class PropertyInterestMessageAdmin(admin.ModelAdmin):
	list_display = ('interest_request', 'sender', 'message_type', 'proposed_visit_at', 'created_at')
	list_filter = ('message_type',)
	search_fields = ('message', 'sender__username', 'interest_request__property__title')


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
	list_display = ('name', 'slug', 'created_at')
	search_fields = ('name', 'slug')


@admin.register(OrganizationMembership)
class OrganizationMembershipAdmin(admin.ModelAdmin):
	list_display = ('organization', 'user', 'role', 'is_active')
	list_filter = ('role', 'is_active')
	search_fields = ('organization__name', 'user__username', 'user__email')


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
	list_display = ('user', 'phone', 'preferred_city', 'created_at')
	search_fields = ('user__username', 'user__email', 'phone', 'preferred_city')


@admin.register(LandlordProfile)
class LandlordProfileAdmin(admin.ModelAdmin):
	list_display = ('display_name', 'user', 'organization', 'is_verified', 'created_at')
	list_filter = ('is_verified', 'organization')
	search_fields = ('display_name', 'user__username', 'user__email', 'phone')


@admin.register(TenantProfile)
class TenantProfileAdmin(admin.ModelAdmin):
	list_display = ('display_name', 'user', 'phone', 'created_at')
	search_fields = ('display_name', 'user__username', 'user__email', 'phone')


@admin.register(Tenant)
class TenantAdmin(admin.ModelAdmin):
	list_display = ('nomPrenoms', 'organization', 'user', 'status_payment', 'expire_date')
	list_filter = ('status_payment', 'organization')
	search_fields = ('nomPrenoms', 'isbn', 'user__username')


@admin.register(Description)
class DescriptionAdmin(admin.ModelAdmin):
	list_display = ('title', 'landlord', 'current_tenant', 'organization', 'city', 'district', 'price', 'listing_status', 'is_archived')
	list_filter = ('listing_status', 'is_archived', 'organization', 'category')
	search_fields = ('title', 'city', 'district', 'tenant', 'isbn', 'landlord__display_name', 'current_tenant__display_name')


@admin.register(PropertyMedia)
class PropertyMediaAdmin(admin.ModelAdmin):
	list_display = ('property', 'organization', 'media_type', 'position', 'is_primary', 'created_at')
	list_filter = ('media_type', 'is_primary', 'organization')
	search_fields = ('property__title', 'caption')


@admin.register(PropertyDocument)
class PropertyDocumentAdmin(admin.ModelAdmin):
	list_display = ('title', 'property', 'organization', 'document_type', 'visibility', 'created_at')
	list_filter = ('document_type', 'visibility', 'organization')
	search_fields = ('title', 'property__title')


@admin.register(Lease)
class LeaseAdmin(admin.ModelAdmin):
	list_display = ('property', 'tenant_profile', 'tenant', 'organization', 'start_date', 'end_date', 'rent_amount', 'status')
	list_filter = ('status', 'organization')
	search_fields = ('property__title', 'tenant__nomPrenoms', 'tenant_profile__display_name')


@admin.register(RentPayment)
class RentPaymentAdmin(admin.ModelAdmin):
	list_display = ('lease', 'organization', 'due_date', 'amount', 'status', 'reference')
	list_filter = ('status', 'organization')
	search_fields = ('lease__property__title', 'reference')


@admin.register(MaintenanceRequest)
class MaintenanceRequestAdmin(admin.ModelAdmin):
	list_display = ('title', 'property', 'organization', 'priority', 'status', 'created_at')
	list_filter = ('priority', 'status', 'organization')
	search_fields = ('title', 'property__title')


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
	list_display = ('action', 'target_type', 'target_id', 'organization', 'actor', 'created_at')
	list_filter = ('action', 'target_type', 'organization')
	search_fields = ('action', 'target_type', 'actor__username')
	readonly_fields = ('created_at',)