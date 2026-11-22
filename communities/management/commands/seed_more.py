import random
from datetime import timedelta
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.utils import timezone
from communities.models import (Community, Membership, Listing, BorrowRequest, LostFoundItem,
                                Notice, Profile, Order)

NEW_USERS = ['kiran', 'anu', 'vishnu', 'remya', 'akhil', 'sana', 'midhun', 'athira', 'basil', 'nimisha']

# title, description, category, type, price, rent unit
ITEMS = [
    ('Operating Systems textbook', 'Galvin 9th edition, clean pages.', 'books', 'sell', 350, 'day'),
    ('Python crash course book', 'Great for beginners, light highlights.', 'books', 'sell', 220, 'day'),
    ('Previous year question papers', 'Printed bundle for semesters 1 to 4.', 'books', 'sell', 90, 'day'),
    ('Novel set: Malayalam classics', 'Five novels in good condition.', 'books', 'lend', 15, 'week'),
    ('Casio scientific calculator', 'Works perfectly, spare battery included.', 'electronics', 'lend', 20, 'day'),
    ('Bluetooth speaker', 'Loud and clear, good for hostel parties.', 'electronics', 'lend', 60, 'day'),
    ('Power bank 20000 mAh', 'Fast charging, two ports.', 'electronics', 'lend', 10, 'hour'),
    ('Mechanical keyboard', 'Blue switches, USB cable included.', 'electronics', 'sell', 1800, 'day'),
    ('Laptop cooling pad', 'Two fans, adjustable stand.', 'electronics', 'sell', 600, 'day'),
    ('Projector for presentations', 'HD projector, HDMI cable included.', 'electronics', 'lend', 250, 'day'),
    ('Wireless earphones', 'Barely used, charging case included.', 'electronics', 'sell', 900, 'day'),
    ('Denim jacket (M)', 'Blue, worn a few times.', 'clothing', 'sell', 700, 'day'),
    ('Graduation gown', 'Black gown with hood. Rent for the ceremony.', 'clothing', 'lend', 150, 'day'),
    ('Formal blazer (L)', 'Navy blue, ideal for interviews.', 'clothing', 'lend', 100, 'day'),
    ('Sports shoes (size 9)', 'Used for one season.', 'clothing', 'sell', 800, 'day'),
    ('Folding study table', 'Light and easy to carry to the hostel.', 'furniture', 'sell', 900, 'day'),
    ('Plastic chair set of 2', 'Sturdy, white.', 'furniture', 'sell', 500, 'day'),
    ('Bookshelf (4 shelves)', 'Wooden, pickup only.', 'furniture', 'sell', 1500, 'day'),
    ('Extension board 6-socket', 'With surge protector.', 'electronics', 'lend', 5, 'day'),
    ('Bicycle for rent', 'Gear cycle, helmet included.', 'other', 'lend', 50, 'day'),
    ('Badminton racket pair', 'Two rackets and shuttles.', 'other', 'lend', 25, 'hour'),
    ('Cricket bat and ball set', 'Good for weekend matches.', 'other', 'lend', 100, 'day'),
    ('Camping tent (3 person)', 'Waterproof, easy setup.', 'other', 'lend', 300, 'week'),
    ('Guitar capo and tuner kit', 'Everything for beginners.', 'other', 'sell', 250, 'day'),
    ('Travel backpack 50L', 'Rain cover included.', 'other', 'sell', 1200, 'day'),
    ('Drawing instruments box', 'Compass, set squares, protractor.', 'other', 'sell', 180, 'day'),
    ('Mixer grinder', 'Three jars, works well.', 'electronics', 'lend', 40, 'day'),
    ('Induction cooktop', 'Spare unit, perfect for PG rooms.', 'electronics', 'lend', 500, 'month'),
    ('Water can (20L) with stand', 'Clean, handy for hostel.', 'other', 'sell', 300, 'day'),
    ('Room cooler', 'Table-top cooler, summer ready.', 'electronics', 'lend', 900, 'month'),
]

LOST_FOUND = [
    ('lost', 'Blue backpack', 'Has notebooks and a water bottle.', 'Main bus stop', 'Call 98950 11122'),
    ('found', 'Black spectacles', 'Found on a bench near the garden.', 'College garden', 'Message me here'),
    ('lost', 'Student ID card', 'Name starts with A, BCA second year.', 'Canteen', 'Call 98950 22233'),
    ('found', 'Samsung phone', 'Found with a blue cover, screen locked.', 'Library entrance', 'Message me here'),
    ('lost', 'Silver bracelet', 'Thin chain, sentimental value.', 'Auditorium', 'Call 98950 33344'),
    ('found', 'Set of keys', 'Three keys with a green tag.', 'Parking area', 'Message me here'),
    ('lost', 'Black umbrella', 'Left near the notice board.', 'Block A', 'Call 98950 44455'),
    ('found', 'Wireless mouse', 'Left in the computer lab.', 'Computer lab', 'Message me here'),
]

NOTICES = [
    ('Internal exams start next Monday', 'Timetable is on the department board. Carry your ID card.', 'announcement', True),
    ('Blood donation camp', 'Camp this Friday 10 AM to 3 PM in the main hall. Everyone is welcome.', 'event', False),
    ('Water supply interruption', 'Supply will be off tomorrow from 9 AM to 1 PM for tank cleaning.', 'general', False),
    ('Annual day rehearsal', 'Rehearsals begin from Wednesday after 4 PM. Volunteers please register.', 'event', False),
    ('Library timings changed', 'Library now closes at 8 PM on weekdays.', 'announcement', False),
    ('Waste segregation drive', 'Please use the green and blue bins provided on every floor.', 'general', True),
]

MEMBER_POSTS = [
    ('Broken tap in the common bathroom', 'The tap on the second floor leaks all day. Please fix it.', 'issue'),
    ('Need a roommate for next semester', 'Looking for a calm roommate. Message me if interested.', 'help'),
    ('Stray dogs near the gate at night', 'Please be careful while returning late.', 'issue'),
    ('Anyone going to Kochi this Saturday?', 'Want to share a ride and split the fare.', 'help'),
    ('Power cut in the evenings', 'Is it the same in all blocks? Maybe we should report together.', 'issue'),
]


class Command(BaseCommand):
    help = 'Adds extra demo data. Safe to run more than once. Deletes nothing.'

    def handle(self, *args, **options):
        random.seed(11)
        communities = list(Community.objects.order_by('id'))
        if not communities:
            self.stdout.write('No communities yet. Run seed_demo first.')
            return
        admin = User.objects.filter(is_superuser=True).first()
        now = timezone.now()

        # users, profiles, memberships
        for i, name in enumerate(NEW_USERS):
            u, created = User.objects.get_or_create(username=name, defaults={'email': name + '@example.com'})
            if created:
                u.set_password('Student@123')
                u.save()
            Profile.objects.get_or_create(user=u, defaults={'phone': '98470%05d' % (20000 + i * 211), 'upi_id': name + '@okicici'})
            for c in (communities[i % len(communities)], communities[(i + 1) % len(communities)]):
                Membership.objects.get_or_create(user=u, community=c, defaults={'status': 'approved'})

        members = {}
        for c in communities:
            members[c.id] = [m.user for m in Membership.objects.filter(community=c, status='approved').select_related('user')]

        # listings
        made = 0
        for i, (title, desc, cat, typ, price, unit) in enumerate(ITEMS):
            c = communities[i % len(communities)]
            people = members[c.id]
            if not people:
                continue
            seller = people[i % len(people)]
            l, created = Listing.objects.get_or_create(
                title=title, community=c,
                defaults={'seller': seller, 'description': desc, 'category': cat, 'listing_type': typ,
                          'price': price, 'rent_unit': unit, 'status': 'available'})
            if created:
                Listing.objects.filter(pk=l.pk).update(created_at=now - timedelta(days=random.randint(0, 10)))
                made += 1

        # lost and found
        for i, (kind, title, desc, loc, contact) in enumerate(LOST_FOUND):
            c = communities[i % len(communities)]
            people = members[c.id]
            if people:
                LostFoundItem.objects.get_or_create(
                    title=title, community=c,
                    defaults={'user': people[i % len(people)], 'item_type': kind, 'description': desc,
                              'location': loc, 'contact': contact, 'status': 'open'})

        # notices by admin and by members
        for i, (title, content, ntype, pinned) in enumerate(NOTICES):
            Notice.objects.get_or_create(title=title, community=communities[i % len(communities)],
                                         defaults={'content': content, 'notice_type': ntype,
                                                   'created_by': admin, 'is_pinned': pinned})
        for i, (title, content, ntype) in enumerate(MEMBER_POSTS):
            c = communities[i % len(communities)]
            people = members[c.id]
            if people:
                Notice.objects.get_or_create(title=title, community=c,
                                             defaults={'content': content, 'notice_type': ntype,
                                                       'created_by': people[i % len(people)]})

        # borrow requests and cash orders
        return_date = timezone.localdate() + timedelta(days=4)
        reqs = orders = 0
        for l in Listing.objects.filter(status='available').order_by('-id')[:25]:
            others = [p for p in members.get(l.community_id, []) if p != l.seller]
            if not others:
                continue
            buyer = others[l.id % len(others)]
            if l.listing_type == 'lend' and l.id % 3 == 0:
                if not BorrowRequest.objects.filter(listing=l, borrower=buyer).exists():
                    BorrowRequest.objects.create(listing=l, borrower=buyer, return_date=return_date,
                                                 units=2, message='Need it for a couple of days.', status='pending')
                    reqs += 1
            elif l.listing_type == 'sell' and l.id % 4 == 0:
                if not Order.objects.filter(listing=l, buyer=buyer).exists():
                    Order.objects.create(listing=l, buyer=buyer, amount=l.price, method='cash', status='paid')
                    orders += 1

        self.stdout.write(self.style.SUCCESS(
            'Done. New listings: %d, borrow requests: %d, orders: %d. New students use password Student@123.'
            % (made, reqs, orders)))
