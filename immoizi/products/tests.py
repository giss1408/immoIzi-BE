from types import SimpleNamespace
from io import BytesIO
from decimal import Decimal
import tempfile
import datetime

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import ValidationError
from django.core.files.storage import default_storage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.conf import settings
from django.test import TestCase, override_settings
from django.utils import translation
from PIL import Image

from .models import (
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
    validate_property_image,
    validate_property_video,
)
from .schema import schema


class GraphQLSecurityTest(TestCase):
    def setUp(self):
        User = get_user_model()
        self.owner = User.objects.create_user(username='owner', password='secret')
        self.other_owner = User.objects.create_user(username='other', password='secret')
        self.staff = User.objects.create_user(username='staff', password='secret', is_staff=True)
        self.category = Category.objects.create(title='Residence')
        self.owner_tenant = Tenant.objects.create(
            user=self.owner,
            nomPrenoms='Owner Tenant',
            isbn='OWNER0000001',
            quantity=1,
        )
        self.other_tenant = Tenant.objects.create(
            user=self.other_owner,
            nomPrenoms='Other Tenant',
            isbn='OTHER0000001',
            quantity=1,
        )
        self.owner_description = self.create_description('Owner Asset', self.owner_tenant)
        self.other_description = self.create_description('Other Asset', self.other_tenant)

    def create_description(self, title, tenant):
        return Description.objects.create(
            title=title,
            country="Cote d'Ivoire",
            city='Abidjan',
            district='Marcory',
            tenant=tenant.nomPrenoms,
            isbn=tenant.isbn,
            rooms=3,
            surface_m2=90,
            price=250000,
            description='Apartment description',
            status=True,
            category=self.category,
            imageurl='https://example.com/image.jpg',
            product_tag='APT',
            bailleur=tenant,
        )

    def execute(self, query, user):
        return schema.execute(query, context_value=SimpleNamespace(user=user))

    def test_anonymous_user_cannot_query_assets(self):
        result = self.execute('{ descriptions { id title } }', AnonymousUser())

        self.assertTrue(result.errors)

    def test_landlord_only_sees_owned_assets(self):
        result = self.execute('{ descriptions { title } tenants { nomPrenoms } }', self.owner)

        self.assertIsNone(result.errors)
        self.assertEqual(result.data['descriptions'], [{'title': 'Owner Asset'}])
        self.assertEqual(result.data['tenants'], [{'nomPrenoms': 'Owner Tenant'}])

    def test_staff_can_see_all_assets(self):
        result = self.execute('{ descriptions { title } tenants { nomPrenoms } }', self.staff)

        self.assertIsNone(result.errors)
        self.assertCountEqual(
            result.data['descriptions'],
            [{'title': 'Owner Asset'}, {'title': 'Other Asset'}],
        )
        self.assertCountEqual(
            result.data['tenants'],
            [{'nomPrenoms': 'Owner Tenant'}, {'nomPrenoms': 'Other Tenant'}],
        )

    def test_landlord_cannot_update_another_landlords_asset(self):
        mutation = f'''
            mutation {{
                updateDescription(id: "{self.other_description.id}", input: {{ title: "Changed" }}) {{
                    description {{ title }}
                }}
            }}
        '''

        result = self.execute(mutation, self.owner)

        self.assertTrue(result.errors)
        self.other_description.refresh_from_db()
        self.assertEqual(self.other_description.title, 'Other Asset')


class ManagementBackendTest(TestCase):
    def setUp(self):
        User = get_user_model()
        self.owner = User.objects.create_user(username='management-owner', password='secret')
        self.manager = User.objects.create_user(username='management-manager', password='secret')
        self.outsider = User.objects.create_user(username='management-outsider', password='secret')
        self.organization = Organization.objects.create(name='Izi Agency', slug='izi-agency')
        OrganizationMembership.objects.create(
            organization=self.organization,
            user=self.owner,
            role=OrganizationMembership.ROLE_OWNER,
        )
        OrganizationMembership.objects.create(
            organization=self.organization,
            user=self.manager,
            role=OrganizationMembership.ROLE_MANAGER,
        )
        self.category = Category.objects.create(title='Residence')
        self.tenant = Tenant.objects.create(
            organization=self.organization,
            user=self.owner,
            nomPrenoms='Managed Tenant',
            isbn='MANAGED000001',
            quantity=1,
        )
        self.property = Description.objects.create(
            organization=self.organization,
            created_by=self.owner,
            title='Managed Asset',
            country="Cote d'Ivoire",
            city='Abidjan',
            district='Cocody',
            tenant=self.tenant.nomPrenoms,
            isbn=self.tenant.isbn,
            rooms=4,
            surface_m2=120,
            price=450000,
            description='Managed apartment',
            status=True,
            listing_status=Description.LISTING_AVAILABLE,
            category=self.category,
            imageurl='https://example.com/image.jpg',
            product_tag='APT',
            bailleur=self.tenant,
        )

    def execute(self, query, user):
        return schema.execute(query, context_value=SimpleNamespace(user=user))

    def test_organization_member_can_query_scoped_management_data(self):
        lease = Lease.objects.create(
            property=self.property,
            organization=self.organization,
            tenant=self.tenant,
            start_date=datetime.date(2026, 1, 1),
            rent_amount=Decimal('450000.00'),
            status=Lease.STATUS_ACTIVE,
        )
        RentPayment.objects.create(
            lease=lease,
            organization=self.organization,
            due_date=datetime.date(2026, 2, 1),
            amount=Decimal('450000.00'),
        )
        PropertyMedia.objects.create(
            property=self.property,
            organization=self.organization,
            media_type=PropertyMedia.MEDIA_EXTERNAL_VIDEO,
            external_url='https://example.com/property-video',
            uploaded_by=self.owner,
        )

        result = self.execute('''
            {
                organizations { name }
                descriptions(first: 1, search: "Managed") { title listingStatus }
                leases { status rentAmount }
                rentPayments { status amount }
                propertyMedia { mediaType externalUrl }
            }
        ''', self.manager)

        self.assertIsNone(result.errors)
        self.assertEqual(result.data['organizations'], [{'name': 'Izi Agency'}])
        self.assertEqual(result.data['descriptions'], [{'title': 'Managed Asset', 'listingStatus': 'AVAILABLE'}])
        self.assertEqual(result.data['leases'], [{'status': 'ACTIVE', 'rentAmount': '450000.00'}])
        self.assertEqual(result.data['rentPayments'], [{'status': 'PENDING', 'amount': '450000.00'}])
        self.assertEqual(result.data['propertyMedia'], [{'mediaType': 'EXTERNAL_VIDEO', 'externalUrl': 'https://example.com/property-video'}])

    def test_outsider_cannot_query_organization_property(self):
        result = self.execute('{ descriptions { title } organizations { name } }', self.outsider)

        self.assertIsNone(result.errors)
        self.assertEqual(result.data['descriptions'], [])
        self.assertEqual(result.data['organizations'], [])

    def test_member_can_create_maintenance_request_for_scoped_property(self):
        mutation = f'''
            mutation {{
                createMaintenanceRequest(
                    propertyId: "{self.property.id}",
                    title: "Leak",
                    description: "Water under the sink",
                    priority: "high"
                ) {{
                    maintenanceRequest {{ title priority status }}
                }}
            }}
        '''

        result = self.execute(mutation, self.manager)

        self.assertIsNone(result.errors)
        self.assertEqual(
            result.data['createMaintenanceRequest']['maintenanceRequest'],
            {'title': 'Leak', 'priority': 'HIGH', 'status': 'OPEN'},
        )
        self.assertTrue(MaintenanceRequest.objects.filter(property=self.property, reported_by=self.manager).exists())

    def test_outsider_cannot_create_maintenance_request_for_scoped_property(self):
        mutation = f'''
            mutation {{
                createMaintenanceRequest(
                    propertyId: "{self.property.id}",
                    title: "Leak",
                    description: "Water under the sink"
                ) {{
                    maintenanceRequest {{ title }}
                }}
            }}
        '''

        result = self.execute(mutation, self.outsider)

        self.assertTrue(result.errors)
        self.assertFalse(MaintenanceRequest.objects.filter(title='Leak').exists())


class RoleAccessTest(TestCase):
    def setUp(self):
        User = get_user_model()
        self.seeker = User.objects.create_user(username='seeker', password='secret', email='seeker@example.com')
        self.landlord_user = User.objects.create_user(username='landlord', password='secret')
        self.tenant_user = User.objects.create_user(username='tenant-user', password='secret')
        self.other_tenant_user = User.objects.create_user(username='other-tenant-user', password='secret')
        UserProfile.objects.create(user=self.seeker, preferred_city='Abidjan')
        self.organization = Organization.objects.create(name='Role Agency', slug='role-agency')
        self.landlord = LandlordProfile.objects.create(
            user=self.landlord_user,
            organization=self.organization,
            display_name='Primary Landlord',
            is_verified=True,
        )
        OrganizationMembership.objects.create(
            organization=self.organization,
            user=self.landlord_user,
            role=OrganizationMembership.ROLE_OWNER,
        )
        self.tenant_profile = TenantProfile.objects.create(user=self.tenant_user, display_name='Current Tenant')
        self.other_tenant_profile = TenantProfile.objects.create(user=self.other_tenant_user, display_name='Other Tenant')
        self.category = Category.objects.create(title='Residence')
        self.legacy_tenant = Tenant.objects.create(
            organization=self.organization,
            user=self.tenant_user,
            nomPrenoms='Current Tenant',
            isbn='TENANT000001',
            quantity=1,
        )
        self.public_property = self.create_property('Available Public Asset', Description.LISTING_AVAILABLE)
        self.rented_property = self.create_property(
            'Tenant Rented Asset',
            Description.LISTING_RENTED,
            current_tenant=self.tenant_profile,
        )
        self.other_rented_property = self.create_property(
            'Other Tenant Asset',
            Description.LISTING_RENTED,
            current_tenant=self.other_tenant_profile,
        )
        self.lease = Lease.objects.create(
            property=self.rented_property,
            organization=self.organization,
            tenant=self.legacy_tenant,
            tenant_profile=self.tenant_profile,
            start_date=datetime.date(2026, 1, 1),
            rent_amount=Decimal('300000.00'),
            status=Lease.STATUS_ACTIVE,
        )
        RentPayment.objects.create(
            lease=self.lease,
            organization=self.organization,
            due_date=datetime.date(2026, 2, 1),
            amount=Decimal('300000.00'),
        )
        PropertyDocument.objects.create(
            property=self.rented_property,
            organization=self.organization,
            title='Tenant Receipt',
            document_type=PropertyDocument.DOCUMENT_RECEIPT,
            visibility=PropertyDocument.VISIBILITY_TENANT,
            file=SimpleUploadedFile('receipt.pdf', b'receipt', content_type='application/pdf'),
            uploaded_by=self.landlord_user,
        )
        PropertyDocument.objects.create(
            property=self.rented_property,
            organization=self.organization,
            title='Internal Note',
            document_type=PropertyDocument.DOCUMENT_OTHER,
            visibility=PropertyDocument.VISIBILITY_INTERNAL,
            file=SimpleUploadedFile('internal.pdf', b'internal', content_type='application/pdf'),
            uploaded_by=self.landlord_user,
        )

    def create_property(self, title, listing_status, current_tenant=None):
        return Description.objects.create(
            organization=self.organization,
            created_by=self.landlord_user,
            landlord=self.landlord,
            current_tenant=current_tenant,
            title=title,
            country="Cote d'Ivoire",
            city='Abidjan',
            district='Plateau',
            tenant=current_tenant.display_name if current_tenant else 'Anonyme',
            isbn='ROLE0000001',
            rooms=3,
            surface_m2=85,
            price=300000,
            description='Role-based property',
            status=True,
            listing_status=listing_status,
            category=self.category,
            imageurl='https://example.com/image.jpg',
            product_tag='APT',
            bailleur=self.legacy_tenant,
        )

    def execute(self, query, user):
        return schema.execute(query, context_value=SimpleNamespace(user=user))

    def test_seeker_can_read_public_assets_and_profile(self):
        result = self.execute('''
            {
                me { username isSeeker isLandlord isTenant userProfile { preferredCity } }
                publicDescriptions { title }
            }
        ''', self.seeker)

        self.assertIsNone(result.errors)
        self.assertEqual(result.data['me']['username'], 'seeker')
        self.assertTrue(result.data['me']['isSeeker'])
        self.assertFalse(result.data['me']['isLandlord'])
        self.assertFalse(result.data['me']['isTenant'])
        self.assertEqual(result.data['me']['userProfile'], {'preferredCity': 'Abidjan'})
        self.assertEqual(result.data['publicDescriptions'], [{'title': 'Available Public Asset'}])

    def test_landlord_can_read_owned_properties(self):
        result = self.execute('{ me { isLandlord landlordProfile { displayName } } myLandlordProperties { title } }', self.landlord_user)

        self.assertIsNone(result.errors)
        self.assertTrue(result.data['me']['isLandlord'])
        self.assertEqual(result.data['me']['landlordProfile'], {'displayName': 'Primary Landlord'})
        self.assertCountEqual(
            result.data['myLandlordProperties'],
            [{'title': 'Available Public Asset'}, {'title': 'Tenant Rented Asset'}, {'title': 'Other Tenant Asset'}],
        )

    def test_tenant_reads_only_active_rented_asset_data(self):
        result = self.execute('''
            {
                me { isTenant tenantProfile { displayName } }
                myTenantProperties { title }
                myTenantPayments { amount status }
                myTenantDocuments { title visibility }
            }
        ''', self.tenant_user)

        self.assertIsNone(result.errors)
        self.assertTrue(result.data['me']['isTenant'])
        self.assertEqual(result.data['me']['tenantProfile'], {'displayName': 'Current Tenant'})
        self.assertEqual(result.data['myTenantProperties'], [{'title': 'Tenant Rented Asset'}])
        self.assertEqual(result.data['myTenantPayments'], [{'amount': '300000.00', 'status': 'PENDING'}])
        self.assertEqual(result.data['myTenantDocuments'], [{'title': 'Tenant Receipt', 'visibility': 'TENANT'}])

    def test_tenant_cannot_create_maintenance_for_unrented_property(self):
        mutation = f'''
            mutation {{
                createMaintenanceRequest(
                    propertyId: "{self.public_property.id}",
                    title: "Broken sink",
                    description: "Needs repair"
                ) {{
                    maintenanceRequest {{ title }}
                }}
            }}
        '''

        result = self.execute(mutation, self.tenant_user)

        self.assertTrue(result.errors)
        self.assertFalse(MaintenanceRequest.objects.filter(title='Broken sink').exists())

    def test_property_interest_creates_landlord_notification(self):
        mutation = f'''
            mutation {{
                createPropertyInterestRequest(
                    propertyId: "{self.public_property.id}",
                    profession: "Architecte",
                    salaryRange: "500000_800000",
                    occupantsCount: 2,
                    leaseStartDate: "2026-10-01",
                    message: "Je souhaite visiter le bien."
                ) {{
                    interestRequest {{ id status }}
                }}
            }}
        '''

        result = self.execute(mutation, self.seeker)

        self.assertIsNone(result.errors)
        self.assertEqual(result.data['createPropertyInterestRequest']['interestRequest']['status'], 'PENDING')
        notification = Notification.objects.get(recipient=self.landlord_user)
        self.assertEqual(notification.property_id, self.public_property.id)
        self.assertFalse(notification.is_read)

        landlord_result = self.execute('{ notifications { title property { title } isRead } }', self.landlord_user)
        self.assertIsNone(landlord_result.errors)
        self.assertEqual(landlord_result.data['notifications'][0]['property']['title'], 'Available Public Asset')

        outsider_result = self.execute('{ notifications { id } }', self.other_tenant_user)
        self.assertIsNone(outsider_result.errors)
        self.assertEqual(outsider_result.data['notifications'], [])

    def test_landlord_can_propose_visit_and_only_applicant_can_read_thread(self):
        interest_request = PropertyInterestRequest.objects.create(
            property=self.public_property,
            applicant=self.seeker,
            profession='Architecte',
            salary_range='500000_800000',
            occupants_count=2,
            lease_start_date=datetime.date(2026, 10, 1),
        )
        mutation = f'''
            mutation {{
                sendPropertyInterestMessage(
                    interestRequestId: "{interest_request.id}",
                    message: "Je vous propose une visite mardi à 14h.",
                    messageType: "visit_proposal",
                    proposedVisitAt: "2026-10-06T14:00:00Z"
                ) {{
                    interestMessage {{ message messageType proposedVisitAt }}
                }}
            }}
        '''

        result = self.execute(mutation, self.landlord_user)

        self.assertIsNone(result.errors)
        self.assertEqual(result.data['sendPropertyInterestMessage']['interestMessage']['messageType'], 'VISIT_PROPOSAL')
        interest_request.refresh_from_db()
        self.assertEqual(interest_request.status, PropertyInterestRequest.STATUS_REVIEWING)
        self.assertTrue(PropertyInterestMessage.objects.filter(interest_request=interest_request, sender=self.landlord_user).exists())
        applicant_result = self.execute(
            f'{{ propertyInterestMessages(interestRequestId: "{interest_request.id}") {{ message sender {{ username }} }} }}',
            self.seeker,
        )
        self.assertIsNone(applicant_result.errors)
        self.assertEqual(applicant_result.data['propertyInterestMessages'][0]['sender']['username'], 'landlord')

        outsider_result = self.execute(
            f'{{ propertyInterestMessages(interestRequestId: "{interest_request.id}") {{ id }} }}',
            self.other_tenant_user,
        )
        self.assertTrue(outsider_result.errors)

    def test_landlord_can_delete_owned_notification_only(self):
        notification = Notification.objects.create(
            recipient=self.landlord_user,
            property=self.public_property,
            title='Test notification',
            message='Test message',
            notification_type='test',
        )
        mutation = f'mutation {{ deleteNotification(notificationId: "{notification.id}") {{ deletedNotificationId }} }}'

        result = self.execute(mutation, self.landlord_user)

        self.assertIsNone(result.errors)
        self.assertFalse(Notification.objects.filter(pk=notification.id).exists())

        forbidden = self.execute(mutation, self.other_tenant_user)
        self.assertTrue(forbidden.errors)


class ImageUploadSecurityTest(TestCase):
    def make_image_upload(self, name='property.jpg', image_format='JPEG'):
        image_buffer = BytesIO()
        Image.new('RGB', (20, 20), color='white').save(image_buffer, format=image_format)
        image_buffer.seek(0)
        return SimpleUploadedFile(name, image_buffer.getvalue(), content_type='image/jpeg')

    def make_video_upload(self, name='property.mp4', content_type='video/mp4', size=1024):
        return SimpleUploadedFile(name, b'0' * size, content_type=content_type)

    def test_real_estate_asset_image_upload_is_saved(self):
        User = get_user_model()
        owner = User.objects.create_user(username='asset-owner', password='secret')
        category = Category.objects.create(title='Residence')
        tenant = Tenant.objects.create(
            user=owner,
            nomPrenoms='Asset Owner',
            isbn='ASSET0000001',
            quantity=1,
        )

        with tempfile.TemporaryDirectory() as media_root, override_settings(MEDIA_ROOT=media_root):
            asset = Description(
                title='Asset With Image',
                country="Cote d'Ivoire",
                city='Abidjan',
                district='Marcory',
                tenant=tenant.nomPrenoms,
                isbn=tenant.isbn,
                rooms=4,
                surface_m2=120,
                price=350000,
                description='Property with an uploaded image',
                status=True,
                category=category,
                imageurl='https://example.com/image.jpg',
                product_tag='HOUSE',
                bailleur=tenant,
                main_image=self.make_image_upload(),
            )

            asset.full_clean()
            asset.save()
            stored_asset = Description.objects.get(pk=asset.pk)

            self.assertTrue(stored_asset.main_image.name.startswith('properties/'))
            self.assertTrue(stored_asset.thumbnail.name.startswith('descriptions/thumbnails/'))
            self.assertTrue(default_storage.exists(stored_asset.main_image.name))
            self.assertTrue(default_storage.exists(stored_asset.thumbnail.name))

    def test_real_estate_asset_video_upload_is_saved(self):
        User = get_user_model()
        owner = User.objects.create_user(username='video-owner', password='secret')
        category = Category.objects.create(title='Residence')
        tenant = Tenant.objects.create(
            user=owner,
            nomPrenoms='Video Owner',
            isbn='VIDEO0000001',
            quantity=1,
        )

        with tempfile.TemporaryDirectory() as media_root, override_settings(MEDIA_ROOT=media_root):
            asset = Description(
                title='Asset With Video',
                country="Cote d'Ivoire",
                city='Abidjan',
                district='Marcory',
                tenant=tenant.nomPrenoms,
                isbn=tenant.isbn,
                rooms=4,
                surface_m2=120,
                price=350000,
                description='Property with one uploaded description video',
                status=True,
                category=category,
                imageurl='https://example.com/image.jpg',
                product_tag='HOUSE',
                bailleur=tenant,
                description_video=self.make_video_upload(),
            )

            asset.full_clean()
            asset.save()
            stored_asset = Description.objects.get(pk=asset.pk)

            self.assertTrue(stored_asset.description_video.name.startswith('properties/'))
            self.assertTrue(default_storage.exists(stored_asset.description_video.name))

    def test_invalid_image_upload_is_rejected(self):
        upload = SimpleUploadedFile('property.jpg', b'not an image', content_type='image/jpeg')

        with self.assertRaises(ValidationError):
            validate_property_image(upload)

    def test_oversized_image_upload_is_rejected(self):
        upload = SimpleUploadedFile('property.jpg', b'0' * (5 * 1024 * 1024 + 1), content_type='image/jpeg')

        with self.assertRaises(ValidationError):
            validate_property_image(upload)

    def test_oversized_video_upload_is_rejected(self):
        upload = self.make_video_upload(size=10 * 1024 * 1024 + 1)

        with self.assertRaises(ValidationError):
            validate_property_video(upload)

    def test_unsupported_video_upload_is_rejected(self):
        upload = self.make_video_upload(name='property.avi', content_type='video/x-msvideo')

        with self.assertRaises(ValidationError):
            Description(description_video=upload).full_clean(exclude=[
                'title', 'country', 'city', 'district', 'tenant', 'isbn', 'rooms',
                'surface_m2', 'price', 'description', 'status', 'category',
                'imageurl', 'product_tag', 'bailleur',
            ])


class InternationalizationTest(TestCase):
    def test_french_and_english_languages_are_configured(self):
        self.assertIn(('fr', 'Français'), settings.LANGUAGES)
        self.assertIn(('en', 'English'), settings.LANGUAGES)

    def test_french_language_can_be_activated(self):
        with translation.override('fr'):
            self.assertEqual(translation.get_language(), 'fr')


class ThumbnailTest(TestCase):
    def test_thumbnail_is_rewound_for_remote_storage(self):
        from utils.imagesManager.imagesManager_upload import make_thumbnail

        buffer = BytesIO()
        Image.new('RGB', (800, 600), 'orange').save(buffer, 'JPEG')
        buffer.seek(0)
        source = SimpleUploadedFile('photo.jpg', buffer.read(), content_type='image/jpeg')

        thumbnail = make_thumbnail(source, size=(300, 200))

        # Cloudinary reads from the current position, not from the start.
        self.assertEqual(thumbnail.file.tell(), 0)
        self.assertGreater(len(thumbnail.read()), 0)



class PropertyListingMutationTest(TestCase):
    CREATE = '''
        mutation Create($categoryId: ID!, $price: Int!, $status: String) {
            createPropertyListing(title: "  Duplex Riviera  ", categoryId: $categoryId,
                city: "Abidjan", district: "Riviera", rooms: 4, price: $price,
                surfaceM2: 150, description: "Duplex lumineux", listingStatus: $status) {
                property { id title city district rooms surfaceM2 price listingStatus category { title } }
            }
        }
    '''

    def setUp(self):
        User = get_user_model()
        self.landlord_user = User.objects.create_user(username='listing-landlord', password='secret')
        self.landlord = LandlordProfile.objects.create(user=self.landlord_user, display_name='Aya Kouassi')
        self.seeker = User.objects.create_user(username='listing-seeker', password='secret')
        self.other_landlord_user = User.objects.create_user(username='other-landlord', password='secret')
        LandlordProfile.objects.create(user=self.other_landlord_user, display_name='Other')
        self.residence = Category.objects.create(title='Residence')
        self.business = Category.objects.create(title='Business')

    def execute(self, query, user, **variables):
        with translation.override('en'):
            return schema.execute(query, variable_values=variables, context_value=SimpleNamespace(user=user))

    def create(self, user=None, **variables):
        variables.setdefault('categoryId', str(self.residence.id))
        variables.setdefault('price', 450000)
        return self.execute(self.CREATE, user or self.landlord_user, **variables)

    def test_landlord_creates_a_listing_visible_in_portfolio_and_public_search(self):
        result = self.create()
        self.assertIsNone(result.errors)
        created = result.data['createPropertyListing']['property']
        self.assertEqual(created['title'], 'Duplex Riviera')
        self.assertEqual(created['surfaceM2'], 150)
        self.assertEqual(created['listingStatus'], 'AVAILABLE')
        self.assertEqual(created['category']['title'], 'Residence')

        listing = Description.objects.get(pk=created['id'])
        self.assertEqual(listing.landlord, self.landlord)
        self.assertEqual(listing.created_by, self.landlord_user)
        self.assertFalse(listing.status)

        portfolio = self.execute('{ myLandlordProperties { id } }', self.landlord_user)
        self.assertEqual([p['id'] for p in portfolio.data['myLandlordProperties']], [created['id']])
        public = self.execute('{ publicDescriptions(search: "Riviera") { id } }', AnonymousUser())
        self.assertEqual(len(public.data['publicDescriptions']), 1)

    def test_draft_listing_is_not_public(self):
        result = self.create(status='draft')
        self.assertIsNone(result.errors)
        public = self.execute('{ publicDescriptions { id } }', AnonymousUser())
        self.assertEqual(public.data['publicDescriptions'], [])

    def test_only_landlords_can_create_listings(self):
        result = self.create(user=self.seeker)
        self.assertIsNotNone(result.errors)
        self.assertFalse(Description.objects.exists())

    def test_invalid_values_are_rejected(self):
        self.assertIn('negative', str(self.create(price=-5).errors[0]))
        self.assertIn('status', str(self.create(status='flying').errors[0]))
        self.assertIn('category', str(self.create(categoryId='999999').errors[0]))
        self.assertFalse(Description.objects.exists())

    def test_owner_updates_all_details(self):
        listing_id = self.create().data['createPropertyListing']['property']['id']
        result = self.execute('''
            mutation Update($id: ID!, $categoryId: ID) {
                updatePropertyListing(propertyId: $id, title: "Bureaux Plateau", categoryId: $categoryId,
                    city: "Abidjan", district: "Plateau", rooms: 6, surfaceM2: 210, price: 980000,
                    description: "Open space", listingStatus: "rented") {
                    property { title district rooms surfaceM2 price description listingStatus category { title } }
                }
            }
        ''', self.landlord_user, id=listing_id, categoryId=str(self.business.id))
        self.assertIsNone(result.errors)
        updated = result.data['updatePropertyListing']['property']
        self.assertEqual(updated['title'], 'Bureaux Plateau')
        self.assertEqual(updated['rooms'], 6)
        self.assertEqual(updated['listingStatus'], 'RENTED')
        self.assertEqual(updated['category']['title'], 'Business')
        self.assertTrue(Description.objects.get(pk=listing_id).status)

    def test_partial_update_keeps_other_fields(self):
        listing_id = self.create().data['createPropertyListing']['property']['id']
        result = self.execute(
            'mutation($id: ID!) { updatePropertyListing(propertyId: $id, price: 500000) { property { price title } } }',
            self.landlord_user, id=listing_id)
        self.assertIsNone(result.errors)
        self.assertEqual(result.data['updatePropertyListing']['property'], {'price': 500000, 'title': 'Duplex Riviera'})

    def test_other_landlords_cannot_update(self):
        listing_id = self.create().data['createPropertyListing']['property']['id']
        result = self.execute(
            'mutation($id: ID!) { updatePropertyListing(propertyId: $id, price: 1) { property { price } } }',
            self.other_landlord_user, id=listing_id)
        self.assertIsNotNone(result.errors)
        self.assertEqual(Description.objects.get(pk=listing_id).price, 450000)

    def test_errors_are_translated_to_french(self):
        with translation.override('fr'):
            result = schema.execute(self.CREATE, variable_values={'categoryId': str(self.residence.id), 'price': -1},
                                    context_value=SimpleNamespace(user=self.landlord_user))
        self.assertIn('negatifs', str(result.errors[0]))



class InterestResponseTest(TestCase):
    def setUp(self):
        User = get_user_model()
        self.landlord_user = User.objects.create_user(username='resp-landlord', password='secret')
        landlord = LandlordProfile.objects.create(user=self.landlord_user, display_name='Aya')
        self.applicant = User.objects.create_user(
            username='resp-applicant', password='secret', first_name='Nadia', last_name='Diallo')
        self.stranger = User.objects.create_user(username='resp-stranger', password='secret')
        self.property = Description.objects.create(
            landlord=landlord, created_by=self.landlord_user, title='Villa Cocody', rooms=5, price=900000,
            description='Villa', status=False, listing_status=Description.LISTING_AVAILABLE,
            category=Category.objects.create(title='Residence'), imageurl='', product_tag='VIL')

    def execute(self, query, user, **variables):
        with translation.override('en'):
            return schema.execute(query, variable_values=variables, context_value=SimpleNamespace(user=user))

    def apply(self):
        result = self.execute('''
            mutation($id: ID!) {
                createPropertyInterestRequest(propertyId: $id, profession: "Fonctionnaire",
                    salaryRange: "300 000 - 500 000 FCFA", occupantsCount: 2, leaseStartDate: "2026-11-01",
                    message: "Bonjour") { interestRequest { id } }
            }''', self.applicant, id=str(self.property.id))
        self.assertIsNone(result.errors)
        return result.data['createPropertyInterestRequest']['interestRequest']['id']

    RESPOND = '''
        mutation($id: ID!, $accept: Boolean!, $message: String) {
            respondToPropertyInterest(interestRequestId: $id, accept: $accept, message: $message) {
                interestRequest { status applicantName }
            }
        }'''

    def test_application_notifies_the_landlord_with_applicant_name(self):
        request_id = self.apply()
        notification = Notification.objects.get(recipient=self.landlord_user)
        self.assertEqual(notification.interest_request_id, int(request_id))
        result = self.execute('{ propertyInterestRequests { applicantName status } }', self.landlord_user)
        self.assertEqual(result.data['propertyInterestRequests'],
                         [{'applicantName': 'Nadia Diallo', 'status': 'PENDING'}])

    def test_landlord_accepts_and_the_applicant_is_notified(self):
        request_id = self.apply()
        result = self.execute(self.RESPOND, self.landlord_user, id=request_id, accept=True,
                              message='Passez me voir samedi.')
        self.assertIsNone(result.errors)
        self.assertEqual(result.data['respondToPropertyInterest']['interestRequest']['status'], 'ACCEPTED')
        notification = Notification.objects.get(recipient=self.applicant)
        self.assertEqual(notification.title, 'Demande acceptée')
        self.assertEqual(notification.notification_type, 'property_interest.accepted')
        self.assertEqual(PropertyInterestMessage.objects.get().message, 'Passez me voir samedi.')

    def test_landlord_refuses(self):
        request_id = self.apply()
        result = self.execute(self.RESPOND, self.landlord_user, id=request_id, accept=False)
        self.assertEqual(result.data['respondToPropertyInterest']['interestRequest']['status'], 'REJECTED')
        self.assertEqual(Notification.objects.get(recipient=self.applicant).title, 'Demande refusée')
        self.assertFalse(PropertyInterestMessage.objects.exists())

    def test_only_the_landlord_can_answer(self):
        request_id = self.apply()
        for user in (self.applicant, self.stranger):
            result = self.execute(self.RESPOND, user, id=request_id, accept=True)
            self.assertIsNotNone(result.errors)
        self.assertEqual(PropertyInterestRequest.objects.get().status, PropertyInterestRequest.STATUS_PENDING)

    def test_visit_proposal_and_confirmation_notify_each_side(self):
        request_id = self.apply()
        send = '''
            mutation($id: ID!, $type: String, $at: DateTime) {
                sendPropertyInterestMessage(interestRequestId: $id, message: "Visite ?", messageType: $type,
                    proposedVisitAt: $at) { interestMessage { id } }
            }'''
        result = self.execute(send, self.landlord_user, id=request_id, type='visit_proposal',
                              at='2026-11-05T10:00:00+00:00')
        self.assertIsNone(result.errors)
        self.assertEqual(Notification.objects.filter(recipient=self.applicant).get().title, 'Proposition de visite')
        result = self.execute(send, self.applicant, id=request_id, type='visit_confirmation')
        self.assertIsNone(result.errors)
        self.assertTrue(Notification.objects.filter(recipient=self.landlord_user, title='Visite confirmée').exists())
