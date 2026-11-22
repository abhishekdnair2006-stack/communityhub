from datetime import timedelta
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.utils import timezone
from communities.models import (Community, Membership, Listing, LostFoundItem, Notice, Notification,
                                CommunityRequest, Report, Profile)

NEW_COMMUNITIES = [
    ('Muvattupuzha Town Residents', 'neighbourhood', 'Muvattupuzha, Ernakulam',
     'Neighbours around Muvattupuzha town sharing tools, notices and local help.'),
    ('Nirmala Higher Secondary School', 'college', 'Muvattupuzha, Ernakulam',
     'Students and parents of Nirmala school. Share books, uniforms and school notices.'),
    ('Idukki Hill View Colony', 'neighbourhood', 'Idukki',
     'Residents of the Hill View colony: lend tools, report issues and read colony notices.'),
    ('Infopark Women PG Network', 'hostel', 'Kakkanad, Kochi',
     'Women working or studying near Infopark. Safe sharing of items and local tips.'),
    ('Kochi Metro Flat Owners', 'other', 'Edappally, Kochi',
     'Flat residents sharing items, parking notices and maintenance updates.'),
]

APPLICANTS = ['rosemary', 'tinu', 'harikrishnan', 'shilpa', 'jithin', 'ancy', 'noufal', 'lakshmi']

COMMUNITY_REQUESTS = [
    ('Vazhakulam Pineapple Farmers Group', 'other', 'Vazhakulam, Ernakulam',
     'Farmers who want to share tools, transport and market notices.'),
    ('Rajagiri Hostel Block C', 'hostel', 'Kakkanad, Kochi',
     'Residents of Block C asking for their own noticeboard and marketplace.'),
    ('Kothamangalam Evening Walkers Club', 'neighbourhood', 'Kothamangalam',
     'A walking club that also wants to organise events and share equipment.'),
]

ADMIN_NOTICES = [
    'Welcome to CommunityHub! Please be respectful and keep listings honest.',
    'Reminder: never pay in advance for items you have not seen.',
    'New feature: rent items by the hour, day, week or month.',
]


class Command(BaseCommand):
    help = 'Adds data that the admin can act on. Safe to run more than once. Deletes nothing.'

    def handle(self, *args, **options):
        now = timezone.now()
        admin = User.objects.filter(is_superuser=True).first()
        if not admin:
            self.stdout.write('No admin account found. Run seed_demo first.')
            return

        # 1. new communities
        new = []
        for name, kind, loc, desc in NEW_COMMUNITIES:
            c, _ = Community.objects.get_or_create(name=name, defaults={
                'community_type': kind, 'location': loc, 'description': desc})
            new.append(c)

        # 2. applicants with PENDING join requests (admin approves or rejects on the dashboard)
        applicants = []
        for i, name in enumerate(APPLICANTS):
            u, created = User.objects.get_or_create(username=name, defaults={'email': name + '@example.com'})
            if created:
                u.set_password('Student@123')
                u.save()
            Profile.objects.get_or_create(user=u, defaults={'phone': '98460%05d' % (30000 + i * 173), 'upi_id': name + '@oksbi'})
            applicants.append(u)
        for i, u in enumerate(applicants):
            for c in (new[i % len(new)], new[(i + 2) % len(new)]):
                Membership.objects.get_or_create(user=u, community=c, defaults={'status': 'pending'})

        # 3. a few existing communities get one pending request each too
        for c in Community.objects.exclude(id__in=[x.id for x in new])[:4]:
            u = applicants[c.id % len(applicants)]
            Membership.objects.get_or_create(user=u, community=c, defaults={'status': 'pending'})

        # 4. community requests from students (admin approves to create the community)
        requesters = list(User.objects.filter(is_staff=False, is_superuser=False).order_by('id')[:3])
        for (name, kind, loc, desc), u in zip(COMMUNITY_REQUESTS, requesters):
            if not Community.objects.filter(name=name).exists():
                CommunityRequest.objects.get_or_create(name=name, defaults={
                    'user': u, 'community_type': kind, 'location': loc, 'description': desc})

        # 5. open reports on listings and lost & found posts
        reasons = ['This looks like spam.', 'Price is unrealistic and the photo seems copied.',
                   'Contact details are fake.', 'Rude language in the description.',
                   'Item was already sold but is still listed.']
        reporters = list(User.objects.filter(is_staff=False, is_superuser=False).order_by('-id')[:6])
        listings = list(Listing.objects.order_by('-id')[:4])
        for i, l in enumerate(listings):
            r = [x for x in reporters if x != l.seller]
            if r and not Report.objects.filter(listing=l).exists():
                Report.objects.create(reporter=r[0], community=l.community, listing=l, reason=reasons[i % len(reasons)])
        for i, lf in enumerate(LostFoundItem.objects.order_by('-id')[:2]):
            r = [x for x in reporters if x != lf.user]
            if r and not Report.objects.filter(lost_item=lf).exists():
                Report.objects.create(reporter=r[0], community=lf.community, lost_item=lf, reason=reasons[(i + 2) % len(reasons)])

        # 6. admin notices in every community
        for c in Community.objects.all():
            for i, text in enumerate(ADMIN_NOTICES):
                Notice.objects.get_or_create(title=text[:60], community=c, defaults={
                    'content': text, 'notice_type': 'announcement', 'created_by': admin, 'is_pinned': i == 0})

        # 7. a couple of notifications for the admin
        for msg in ['5 membership requests are waiting for approval.', 'New community requests need review.']:
            Notification.objects.get_or_create(user=admin, message=msg, defaults={'link': '/staff/dashboard/'})

        self.stdout.write(self.style.SUCCESS(
            'Done. Communities: %d, pending memberships: %d, community requests: %d, open reports: %d.'
            % (Community.objects.count(), Membership.objects.filter(status='pending').count(),
               CommunityRequest.objects.filter(status='pending').count(), Report.objects.filter(status='open').count())))
