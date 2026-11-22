"""Fills the database with demo communities, students and activity.

    python manage.py seed_demo

WARNING: this first DELETES all communities, listings, requests, notices, notifications and every
non-superuser account. Superuser (admin) accounts are kept. If no superuser exists, one is created
(username: admin, password: Admin@12345).
"""
import random
from datetime import timedelta

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.utils import timezone

from communities.models import (Community, Membership, Listing, BorrowRequest, LostFoundItem, Notice,
                                Notification, CommunityRequest, Report, Profile, Order, Conversation, Message)

STUDENT_PASSWORD = 'Student@123'
NAMES = ['anjali', 'rahul', 'meera', 'arjun', 'sneha', 'nikhil', 'fathima', 'joseph', 'devika', 'adithya',
         'neha', 'sanjay', 'gopika', 'abhijith', 'maria']

COMMUNITIES = [
    ('Santhigiri College', 'college', 'Vazhithala, Thodupuzha, Idukki',
     'Students and staff of Santhigiri College. Buy and sell textbooks, borrow lab equipment and catch every college notice.'),
    ('Thodupuzha Town Residents', 'neighbourhood', 'Thodupuzha, Idukki',
     'Neighbours around Thodupuzha town: lend tools, share local notices and find lost belongings.'),
    ('Sunrise Boys Hostel', 'hostel', 'Near Santhigiri College, Thodupuzha',
     'Residents of Sunrise Hostel. Share chargers, kettles and study material, and keep up with hostel rules.'),
    ('Kakkanad PG Network', 'hostel', 'Kakkanad, Kochi',
     'Young professionals and students living in PGs around Infopark.'),
]

# title, description, category, type, price, community index, seller index, status
LISTINGS = [
    ('Engineering Mathematics (Vol 2)', 'Barely used, no markings. Covers the full syllabus.', 'books', 'sell', 250, 0, 0, 'available'),
    ('Scientific calculator fx-991', 'Lend for exams. Please return the same week.', 'electronics', 'lend', 100, 0, 1, 'lent'),
    ('Data Structures in C notes', 'Handwritten and neatly organised, semesters 3 and 4.', 'books', 'sell', 120, 0, 2, 'available'),
    ('Arduino starter kit', 'Complete kit with sensors. Great for mini projects.', 'electronics', 'lend', 300, 0, 3, 'available'),
    ('Lab coat (size M)', 'Washed and ironed, used one semester.', 'clothing', 'sell', 150, 0, 4, 'available'),
    ('Study table lamp', 'Warm LED lamp, works perfectly.', 'furniture', 'sell', 200, 0, 5, 'sold'),
    ('Drawing board and T-square', 'Needed for engineering graphics. Lend for the week.', 'other', 'lend', 50, 0, 6, 'available'),
    ('Pressure cooker 3L', 'Handy for neighbours. Can lend for festival season.', 'other', 'lend', 0, 1, 7, 'available'),
    ('Ladder (6 ft)', 'Aluminium ladder, lend for a day or two.', 'furniture', 'lend', 100, 1, 8, 'available'),
    ('Ceiling fan, 2 years old', 'Working condition, selling since we are moving.', 'electronics', 'sell', 800, 1, 9, 'available'),
    ('Saree set (festive)', 'Worn once. Pick up from Thodupuzha town.', 'clothing', 'sell', 900, 1, 10, 'available'),
    ('Electric kettle', 'Shared by two rooms before, now spare.', 'electronics', 'lend', 0, 2, 11, 'available'),
    ('Single cot mattress', 'Clean, medium firm. Hostel pickup only.', 'furniture', 'sell', 600, 2, 12, 'available'),
    ('Bicycle (Hero Sprint)', 'Good for commuting to college.', 'other', 'sell', 2500, 2, 13, 'available'),
    ('Standing desk fan', 'Quiet, three speeds.', 'electronics', 'sell', 700, 3, 14, 'available'),
    ('Formal shirts (pack of 3)', 'Size 40, office wear.', 'clothing', 'sell', 500, 3, 0, 'available'),
    ('Wireless headphones', 'Great for study sessions. Rent by the week.', 'electronics', 'lend', 50, 0, 3, 'available'),
    ('City bicycle', 'Rent by the day for trips around town.', 'other', 'lend', 40, 1, 7, 'available'),
    ('Acoustic guitar', 'Beginner friendly. Rent by the month.', 'other', 'lend', 300, 2, 12, 'available'),
    ('Laptop (i5, 8GB)', 'Lightly used, charger included.', 'electronics', 'sell', 21000, 3, 14, 'available'),
    ('College backpack', 'Waterproof, two compartments.', 'other', 'sell', 450, 0, 6, 'available'),
]
# rent items: title -> (rent price, unit). Prices above are overridden for lending items.
RENT = {'Scientific calculator fx-991': (20, 'day'), 'Arduino starter kit': (60, 'day'),
        'Drawing board and T-square': (15, 'day'), 'Pressure cooker 3L': (0, 'day'), 'Ladder (6 ft)': (30, 'day'),
        'Electric kettle': (0, 'day'), 'Wireless headphones': (50, 'week'), 'City bicycle': (40, 'day'),
        'Acoustic guitar': (300, 'month')}

LOST_FOUND = [
    ('lost', 'Black leather wallet', 'Contains ID card and a few receipts.', 'Library, ground floor', 'anjali: 98765 43210', 0, 0, 'open'),
    ('found', 'Blue umbrella', 'Left in the canteen after the rain.', 'Canteen', 'rahul: 98765 11111', 0, 1, 'open'),
    ('lost', 'Silver earphones case', 'White case with a small scratch.', 'Block B corridor', 'meera: 90000 22222', 0, 2, 'resolved'),
    ('found', 'House keys with red keychain', 'Found near the bus stop.', 'Thodupuzha bus stand', 'joseph: 90000 33333', 1, 7, 'open'),
    ('lost', 'Grey hoodie', 'Left in the common room.', 'Sunrise Hostel common room', 'nikhil: 90000 44444', 2, 5, 'open'),
    ('found', 'Water bottle (steel)', 'Picked up outside the lift.', 'Infopark Phase 1', 'maria: 90000 55555', 3, 14, 'open'),
]

NOTICES = [
    (0, 'Internal exams start next Monday', 'The timetable is on the department board. Please carry your ID cards.', 'announcement', True),
    (0, 'Tech fest registration open', 'Register for events before Friday. Teams of up to four.', 'event', False),
    (0, 'Library timings during exams', 'The library stays open until 9 pm throughout the exam week.', 'general', False),
    (1, 'Water supply interruption on Sunday', 'Pipeline maintenance from 9 am to 2 pm. Please store water.', 'announcement', True),
    (1, 'Onam celebration planning meeting', 'Join us at the community hall on Saturday evening.', 'event', False),
    (2, 'Hostel curfew reminder', 'Gates close at 9:30 pm. Contact the warden for late entry.', 'general', True),
    (3, 'Weekend movie night', 'Common room, Saturday 8 pm. Bring snacks!', 'event', False),
]


class Command(BaseCommand):
    help = 'Delete all demo-able data and create fresh demo communities, users and activity.'

    def add_arguments(self, parser):
        parser.add_argument('--yes', action='store_true', help='Skip the confirmation question.')

    def handle(self, *args, **options):
        if not options['yes']:
            answer = input('This DELETES all communities, content and non-admin users. Type YES to continue: ')
            if answer.strip() != 'YES':
                self.stdout.write('Cancelled.')
                return
        random.seed(7)
        now = timezone.now()

        # 1. wipe (admins are kept)
        for model in (Message, Conversation, Order, Profile, Report, Notification, BorrowRequest, LostFoundItem, Notice, Listing, Membership,
                      CommunityRequest, Community):
            model.objects.all().delete()
        User.objects.filter(is_superuser=False).delete()

        if not User.objects.filter(is_superuser=True).exists():
            User.objects.create_superuser('admin', 'admin@example.com', 'Admin@12345')
            self.stdout.write('Created admin account: admin / Admin@12345')
        admin_user = User.objects.filter(is_superuser=True).first()

        # 2. users
        users = []
        for i, name in enumerate(NAMES):
            u = User.objects.create_user(name, f'{name}@example.com', STUDENT_PASSWORD)
            User.objects.filter(pk=u.pk).update(date_joined=now - timedelta(days=random.randint(0, 13)))
            users.append(u)

        for i, u in enumerate(users):
            Profile.objects.create(user=u, phone='98950%05d' % (10000 + i * 137), upi_id=u.username + '@okaxis')

        # 3. communities and memberships
        communities = [Community.objects.create(name=n, community_type=t, location=l, description=d)
                       for n, t, l, d in COMMUNITIES]
        homes = {0: range(0, 8), 1: range(7, 11), 2: range(5, 14), 3: range(11, 15)}
        for ci, idxs in homes.items():
            for k, ui in enumerate(idxs):
                Membership.objects.create(user=users[ui], community=communities[ci], status='approved',
                                          role='moderator' if k == 0 else 'member')
        Membership.objects.create(user=users[12], community=communities[0], status='pending')   # pending examples
        Membership.objects.create(user=users[13], community=communities[0], status='pending')
        Membership.objects.create(user=users[9], community=communities[0], status='rejected')

        # 4. listings (spread over the last 2 weeks so the admin chart has a shape)
        listings = []
        for title, desc, cat, typ, price, ci, si, status in LISTINGS:
            listing = Listing.objects.create(
                seller=users[si], community=communities[ci], title=title, description=desc,
                category=cat, listing_type=typ, price=RENT.get(title, (price, 'day'))[0],
                rent_unit=RENT.get(title, (price, 'day'))[1], status=status)
            Listing.objects.filter(pk=listing.pk).update(created_at=now - timedelta(days=random.randint(0, 13)))
            listings.append(listing)

        # 5. borrow requests
        tomorrow = timezone.localdate() + timedelta(days=5)
        BorrowRequest.objects.create(listing=listings[1], borrower=users[2], return_date=tomorrow,
                                     message='Need it for the internal exam.', status='approved')
        BorrowRequest.objects.create(listing=listings[3], borrower=users[4], return_date=tomorrow,
                                     message='For my mini project demo.', status='pending')
        BorrowRequest.objects.create(listing=listings[6], borrower=users[0], return_date=tomorrow,
                                     message='Graphics assignment due soon.', status='returned')
        BorrowRequest.objects.create(listing=listings[7], borrower=users[8], return_date=tomorrow,
                                     message='Festival cooking.', status='rejected')
        Notification.objects.create(user=users[3], message='sneha requested to borrow Arduino starter kit.', link='/borrow-requests/')
        Notification.objects.create(user=users[2], message='Your request to borrow Scientific calculator fx-991 has been approved.', link='/borrow-requests/')

        # 6. lost and found
        for kind, title, desc, loc, contact, ci, ui, status in LOST_FOUND:
            LostFoundItem.objects.create(user=users[ui], community=communities[ci], item_type=kind, title=title,
                                         description=desc, location=loc, contact=contact, status=status)

        # 7. notices
        for ci, title, content, ntype, pinned in NOTICES:
            Notice.objects.create(community=communities[ci], title=title, content=content, notice_type=ntype,
                                  created_by=admin_user, is_pinned=pinned)

        # 7b. member posts on the noticeboard (issues, help wanted)
        for ci, ui, title, content, ntype in [
            (1, 8, 'Street light not working near Town Hall road', 'The light has been off for two weeks. Please report it to the ward member.', 'issue'),
            (0, 4, 'Looking for a study partner for DBMS', 'Anyone preparing for the DBMS internal? Let us meet at the library.', 'help'),
            (2, 12, 'Wi-Fi is very slow after 9 PM', 'Is it only my room? Please reply if you face the same.', 'issue')]:
            Notice.objects.create(community=communities[ci], title=title, content=content, notice_type=ntype, created_by=users[ui])

        # 7c. one confirmed order, one waiting for payment, one chat
        sold = listings[5]
        Order.objects.create(listing=sold, buyer=users[1], amount=sold.price, method='upi', upi_ref='UPI4455667788', status='confirmed')
        Order.objects.create(listing=listings[0], buyer=users[3], amount=listings[0].price, method='upi', status='awaiting')
        convo = Conversation.objects.create(starter=users[3], other=users[0], listing=listings[0], status='accepted', other_shared=True)
        for who, text in [(users[3], 'Hi, is the Maths book still available?'), (users[0], 'Yes! I can hand it over at the library tomorrow.')]:
            Message.objects.create(conversation=convo, sender=who, body=text, is_read=True)

        # 8. a pending community request and an open report
        CommunityRequest.objects.create(user=users[3], name='Idukki Hill View Colony', community_type='neighbourhood',
                                        location='Idukki', description='Residents of the Hill View colony want a shared noticeboard.')
        Report.objects.create(reporter=users[4], community=communities[0], listing=listings[4],
                              reason='Photo does not match the item description.')

        self.stdout.write(self.style.SUCCESS(
            f'Done. {len(users)} students (password: {STUDENT_PASSWORD}), {len(communities)} communities, '
            f'{len(listings)} listings. Try logging in as anjali (moderator of Santhigiri College).'))
