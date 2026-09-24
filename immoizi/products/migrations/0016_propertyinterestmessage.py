from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('products', '0015_notification'),
    ]

    operations = [
        migrations.CreateModel(
            name='PropertyInterestMessage',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('message', models.TextField()),
                ('message_type', models.CharField(choices=[('message', 'Message'), ('visit_proposal', 'Visit proposal'), ('visit_confirmation', 'Visit confirmation'), ('visit_declined', 'Visit declined')], default='message', max_length=32)),
                ('proposed_visit_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('interest_request', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='messages', to='products.propertyinterestrequest')),
                ('sender', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='property_interest_messages', to=settings.AUTH_USER_MODEL)),
            ],
            options={'ordering': ['created_at']},
        ),
    ]