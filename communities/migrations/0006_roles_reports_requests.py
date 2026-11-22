from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('communities', '0005_listing_listing_type'),
    ]

    operations = [
        migrations.AddField(
            model_name='membership', name='role',
            field=models.CharField(choices=[('member', 'Member'), ('moderator', 'Moderator')], default='member', max_length=20),
        ),
        migrations.AddField(
            model_name='listing', name='image',
            field=models.ImageField(blank=True, upload_to='listings/'),
        ),
        migrations.AlterField(
            model_name='listing', name='status',
            field=models.CharField(choices=[('available', 'Available'), ('sold', 'Sold'), ('lent', 'Lent out')], default='available', max_length=20),
        ),
        migrations.AddField(
            model_name='notification', name='link',
            field=models.CharField(blank=True, default='', max_length=200),
        ),
        migrations.CreateModel(
            name='CommunityRequest',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100)),
                ('community_type', models.CharField(choices=[('college', 'College'), ('hostel', 'Hostel'), ('neighbourhood', 'Neighbourhood'), ('other', 'Other')], max_length=20)),
                ('location', models.CharField(max_length=200)),
                ('description', models.TextField()),
                ('status', models.CharField(choices=[('pending', 'Pending'), ('approved', 'Approved'), ('rejected', 'Rejected')], default='pending', max_length=20)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name='Report',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('reason', models.TextField()),
                ('status', models.CharField(choices=[('open', 'Open'), ('resolved', 'Resolved')], default='open', max_length=20)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('community', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='communities.community')),
                ('listing', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='communities.listing')),
                ('lost_item', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='communities.lostfounditem')),
                ('reporter', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
        ),
    ]
