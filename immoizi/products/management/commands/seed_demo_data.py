import datetime
from decimal import Decimal
from io import BytesIO
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from PIL import Image as PILImage

from products.models import (
    Category,
    Description,
    LandlordProfile,
    Lease,
    MaintenanceRequest,
    Organization,
    OrganizationMembership,
    PropertyDocument,
    RentPayment,
    Tenant,
    TenantProfile,
    UserProfile,
)

User = get_user_model()

CATEGORY_NAMES = ['Residence', 'Business', 'Commerce', 'Industrie']

# Solid colors used to generate distinguishable dummy JPEGs for each seeded property/gallery slot.
IMAGE_COLORS = [
    (255, 130, 0),
    (0, 154, 68),
    (255, 255, 255),
    (60, 120, 190),
    (200, 90, 60),
    (120, 120, 120),
]

# A real 2-second H.264 clip (4 KB): cloud storage such as Cloudinary rejects
# fake container bytes, and the apps' video player needs something playable.
DEMO_VIDEO_PATH = Path(__file__).resolve().parent / 'fixtures' / 'demo-video.mp4'


def _dummy_image_bytes(color_index):
    color = IMAGE_COLORS[color_index % len(IMAGE_COLORS)]
    buffer = BytesIO()
    PILImage.new('RGB', (640, 480), color=color).save(buffer, format='JPEG')
    return buffer.getvalue()

PROPERTIES = [
    {
        'title': 'Villa de prestige avec piscine',
        'category': 'Residence',
        'city': 'Abidjan',
        'district': 'Cocody',
        'rooms': 5,
        'surface_m2': 220,
        'price': 920000,
        'listing_status': Description.LISTING_AVAILABLE,
        'description': 'Villa moderne avec piscine, jardin paysager et garage double.',
    },
    {
        'title': 'Appartement duplex vue lagune',
        'category': 'Residence',
        'city': 'Abidjan',
        'district': 'Yopougon',
        'rooms': 4,
        'surface_m2': 170,
        'price': 710000,
        'listing_status': Description.LISTING_RENTED,
        'description': 'Duplex lumineux avec balcon panoramique sur la lagune.',
    },
    {
        'title': 'Bureau commercial centre-ville',
        'category': 'Business',
        'city': 'Abidjan',
        'district': 'Plateau',
        'rooms': 2,
        'surface_m2': 98,
        'price': 480000,
        'listing_status': Description.LISTING_RESERVED,
        'description': 'Espace de bureaux climatise, proche des institutions financieres.',
    },
    {
        'title': 'Local commercial passant',
        'category': 'Commerce',
        'city': 'Yamoussoukro',
        'district': 'Centre',
        'rooms': 1,
        'surface_m2': 60,
        'price': 260000,
        'listing_status': Description.LISTING_AVAILABLE,
        'description': 'Local en rez-de-chaussee avec forte visibilite et grand acces client.',
    },
    {
        'title': 'Entrepot logistique',
        'category': 'Industrie',
        'city': 'Abidjan',
        'district': 'Vridi',
        'rooms': 1,
        'surface_m2': 540,
        'price': 1150000,
        'listing_status': Description.LISTING_AVAILABLE,
        'description': 'Entrepot securise avec quai de chargement et bureaux annexes.',
    },
    {
        'title': 'Studio meuble pour etudiant',
        'category': 'Residence',
        'city': 'Yamoussoukro',
        'district': 'Centre',
        'rooms': 1,
        'surface_m2': 42,
        'price': 195000,
        'listing_status': Description.LISTING_AVAILABLE,
        'description': 'Studio compact et meuble, ideal pour etudiant ou jeune actif.',
    },
]


class Command(BaseCommand):
    help = 'Seed the database with demo data for landlord, tenant and seeker accounts.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--password',
            default='DemoPass123!',
            help='Password to assign to the generated demo accounts.',
        )

    def handle(self, *args, **options):
        password = options['password']
        with transaction.atomic():
            organization = self._create_organization()
            categories = self._create_categories()
            landlord_user, landlord_profile = self._create_landlord(organization, password)
            tenant_user, tenant_profile, tenant_record = self._create_tenant(organization, password)
            self._create_seeker(password)
            properties = self._create_properties(organization, landlord_user, landlord_profile, tenant_profile, categories)
            lease = self._create_lease(organization, properties[1], tenant_record, tenant_profile)
            self._create_payments(organization, lease)
            self._create_maintenance(organization, properties, landlord_user)
            self._create_document(organization, properties[1], landlord_user)

        self.stdout.write(self.style.SUCCESS(
            'Demo data ready. Landlord: landlord_demo / Tenant: tenant_demo / Seeker: seeker_demo '
            f'(password: {password})'
        ))

    def _create_organization(self):
        organization, _created = Organization.objects.get_or_create(
            slug='immoizi-demo',
            defaults={'name': 'Immoizi Demo Agency'},
        )
        return organization

    def _create_categories(self):
        categories = {}
        for name in CATEGORY_NAMES:
            category, _created = Category.objects.get_or_create(title=name)
            categories[name] = category
        return categories

    def _create_landlord(self, organization, password):
        user, created = User.objects.get_or_create(
            username='landlord_demo',
            defaults={'email': 'landlord_demo@immoizi.test', 'first_name': 'Aya', 'last_name': 'Kouassi'},
        )
        if created:
            user.set_password(password)
            user.save()

        UserProfile.objects.get_or_create(user=user, defaults={'phone': '+225 07 00 00 01', 'preferred_city': 'Abidjan'})
        landlord_profile, _created = LandlordProfile.objects.get_or_create(
            user=user,
            defaults={
                'organization': organization,
                'display_name': 'Aya Kouassi',
                'phone': '+225 07 00 00 01',
                'is_verified': True,
            },
        )
        OrganizationMembership.objects.get_or_create(
            organization=organization,
            user=user,
            defaults={'role': OrganizationMembership.ROLE_OWNER},
        )
        return user, landlord_profile

    def _create_tenant(self, organization, password):
        user, created = User.objects.get_or_create(
            username='tenant_demo',
            defaults={'email': 'tenant_demo@immoizi.test', 'first_name': 'Nadia', 'last_name': 'Diabate'},
        )
        if created:
            user.set_password(password)
            user.save()

        UserProfile.objects.get_or_create(user=user, defaults={'phone': '+225 07 00 00 02', 'preferred_city': 'Abidjan'})
        tenant_profile, _created = TenantProfile.objects.get_or_create(
            user=user,
            defaults={'display_name': 'Nadia Diabate', 'phone': '+225 07 00 00 02'},
        )
        tenant_record, _created = Tenant.objects.get_or_create(
            user=user,
            organization=organization,
            defaults={
                'nomPrenoms': 'Nadia Diabate',
                'isbn': '1234567890123',
                'quantity': 1,
                'status_payment': True,
                'expire_date': datetime.date.today() + datetime.timedelta(days=180),
            },
        )
        OrganizationMembership.objects.get_or_create(
            organization=organization,
            user=user,
            defaults={'role': OrganizationMembership.ROLE_AGENT},
        )
        return user, tenant_profile, tenant_record

    def _create_seeker(self, password):
        user, created = User.objects.get_or_create(
            username='seeker_demo',
            defaults={'email': 'seeker_demo@immoizi.test', 'first_name': 'Boubacar', 'last_name': 'Traore'},
        )
        if created:
            user.set_password(password)
            user.save()

        UserProfile.objects.get_or_create(user=user, defaults={'phone': '+225 07 00 00 03', 'preferred_city': 'Abidjan'})
        return user

    def _create_properties(self, organization, landlord_user, landlord_profile, tenant_profile, categories):
        properties = []
        for index, data in enumerate(PROPERTIES):
            current_tenant = tenant_profile if index == 1 else None
            description, _created = Description.objects.update_or_create(
                title=data['title'],
                defaults={
                    'organization': organization,
                    'created_by': landlord_user,
                    'landlord': landlord_profile,
                    'current_tenant': current_tenant,
                    'country': "Côte d'Ivoire",
                    'city': data['city'],
                    'district': data['district'],
                    'tenant': landlord_profile.display_name,
                    'isbn': f'900000000{index:04d}'[:13],
                    'rooms': data['rooms'],
                    'surface_m2': data['surface_m2'],
                    'price': data['price'],
                    'description': data['description'],
                    'status': data['listing_status'] != Description.LISTING_AVAILABLE,
                    'listing_status': data['listing_status'],
                    'category': categories[data['category']],
                    'imageurl': 'https://placehold.co/600x400',
                    'product_tag': data['category'][:10],
                    'is_test_data': True,
                },
            )
            properties.append(description)
        self._attach_media(properties)
        return properties

    def _attach_media(self, properties):
        for index, description in enumerate(properties):
            # Re-running the seed (e.g. on every deploy) must not re-upload.
            if description.main_image:
                continue
            description.main_image.save(f'demo-{index}-main.jpg', ContentFile(_dummy_image_bytes(index)), save=False)
            if index == 0:
                description.image_1.save('demo-0-gallery-1.jpg', ContentFile(_dummy_image_bytes(index + 1)), save=False)
                description.image_2.save('demo-0-gallery-2.jpg', ContentFile(_dummy_image_bytes(index + 2)), save=False)
                try:
                    description.description_video.save(
                        'demo-0-video.mp4', ContentFile(DEMO_VIDEO_PATH.read_bytes()), save=False)
                except Exception as exc:  # A missing demo video must not fail a deploy.
                    self.stderr.write(self.style.WARNING(f'Demo video skipped: {exc}'))
            elif index == 1:
                description.image_1.save('demo-1-gallery-1.jpg', ContentFile(_dummy_image_bytes(index + 1)), save=False)
            description.save()

    def _create_lease(self, organization, rented_property, tenant_record, tenant_profile):
        lease, _created = Lease.objects.get_or_create(
            property=rented_property,
            tenant=tenant_record,
            defaults={
                'organization': organization,
                'tenant_profile': tenant_profile,
                'start_date': datetime.date.today() - datetime.timedelta(days=90),
                'rent_amount': Decimal('710000.00'),
                'deposit_amount': Decimal('1420000.00'),
                'status': Lease.STATUS_ACTIVE,
            },
        )
        return lease

    def _create_payments(self, organization, lease):
        today = datetime.date.today()
        payment_plan = [
            (today - datetime.timedelta(days=60), RentPayment.STATUS_PAID, True),
            (today - datetime.timedelta(days=30), RentPayment.STATUS_PAID, True),
            (today + datetime.timedelta(days=5), RentPayment.STATUS_PENDING, False),
        ]
        for due_date, status, is_paid in payment_plan:
            RentPayment.objects.get_or_create(
                lease=lease,
                due_date=due_date,
                defaults={
                    'organization': organization,
                    'amount': lease.rent_amount,
                    'status': status,
                    'paid_at': timezone.now() if is_paid else None,
                    'reference': f'RCPT-{due_date.strftime("%Y%m")}',
                },
            )

    def _create_maintenance(self, organization, properties, landlord_user):
        maintenance_plan = [
            (properties[0], 'Remplacement plomberie', MaintenanceRequest.PRIORITY_NORMAL, MaintenanceRequest.STATUS_IN_PROGRESS),
            (properties[1], 'Fuite sous evier', MaintenanceRequest.PRIORITY_URGENT, MaintenanceRequest.STATUS_OPEN),
            (properties[4], 'Verification systeme incendie', MaintenanceRequest.PRIORITY_HIGH, MaintenanceRequest.STATUS_RESOLVED),
        ]
        for prop, title, priority, status in maintenance_plan:
            MaintenanceRequest.objects.get_or_create(
                property=prop,
                title=title,
                defaults={
                    'organization': organization,
                    'description': f'{title} - intervention planifiee pour {prop.title}.',
                    'priority': priority,
                    'status': status,
                    'reported_by': landlord_user,
                },
            )

    def _create_document(self, organization, rented_property, landlord_user):
        PropertyDocument.objects.get_or_create(
            property=rented_property,
            title='Contrat de location',
            defaults={
                'organization': organization,
                'document_type': PropertyDocument.DOCUMENT_LEASE,
                'visibility': PropertyDocument.VISIBILITY_TENANT,
                'file': 'properties/documents/demo-lease.pdf',
                'uploaded_by': landlord_user,
            },
        )
