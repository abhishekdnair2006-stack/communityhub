"""Run with:  python manage.py test
These tests cover the main user scenarios and the security rules."""
from datetime import timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import (Community, Membership, Listing, BorrowRequest, LostFoundItem, Notice, Notification,
                     CommunityRequest, Report, Order, Profile, Conversation, Message)


class BaseCase(TestCase):
    def setUp(self):
        self.community = Community.objects.create(name='Test College', community_type='college',
                                                  location='Thodupuzha', description='Test')
        self.other_community = Community.objects.create(name='Other', community_type='hostel',
                                                        location='Kochi', description='Other')
        self.admin = User.objects.create_user('admin1', password='pw', is_staff=True)
        self.a = User.objects.create_user('alice', password='pw')
        self.b = User.objects.create_user('bob', password='pw')
        self.c = User.objects.create_user('carol', password='pw')       # pending member
        for u in (self.a, self.b):
            Membership.objects.create(user=u, community=self.community, status='approved')
        Membership.objects.create(user=self.c, community=self.community, status='pending')

    def make_listing(self, seller=None, **kw):
        data = dict(seller=seller or self.a, community=self.community, title='Calculator', description='d',
                    category='electronics', listing_type='lend', price=0)
        data.update(kw)
        return Listing.objects.create(**data)


class AccessTests(BaseCase):
    def test_logged_out_redirected_to_login(self):
        r = self.client.get(reverse('community_detail', args=[self.community.id]))
        self.assertEqual(r.status_code, 302)
        self.assertIn('/accounts/login/', r.url)

    def test_pending_member_denied(self):
        self.client.login(username='carol', password='pw')
        r = self.client.get(reverse('community_detail', args=[self.community.id]))
        self.assertEqual(r.status_code, 403)

    def test_member_cannot_open_other_community(self):
        self.client.login(username='alice', password='pw')
        r = self.client.get(reverse('marketplace', args=[self.other_community.id]))
        self.assertEqual(r.status_code, 403)

    def test_join_creates_one_pending_membership(self):
        self.client.login(username='alice', password='pw')
        url = reverse('join_community', args=[self.other_community.id])
        self.client.post(url); self.client.post(url)
        self.assertEqual(Membership.objects.filter(user=self.a, community=self.other_community).count(), 1)

    def test_join_requires_post(self):
        self.client.login(username='alice', password='pw')
        r = self.client.get(reverse('join_community', args=[self.other_community.id]))
        self.assertEqual(r.status_code, 405)


class ListingTests(BaseCase):
    def test_other_user_cannot_edit_or_delete(self):
        listing = self.make_listing()
        self.client.login(username='bob', password='pw')
        self.assertEqual(self.client.get(reverse('edit_listing', args=[listing.id])).status_code, 404)
        self.assertEqual(self.client.post(reverse('delete_listing', args=[listing.id])).status_code, 404)
        self.assertTrue(Listing.objects.filter(id=listing.id).exists())

    def test_owner_can_mark_sold(self):
        listing = self.make_listing(listing_type='sell')
        self.client.login(username='alice', password='pw')
        self.client.post(reverse('set_listing_status', args=[listing.id]), {'action': 'sold'})
        listing.refresh_from_db()
        self.assertEqual(listing.status, 'sold')


class BorrowTests(BaseCase):
    def request_borrow(self, listing, days=3):
        when = (timezone.localdate() + timedelta(days=days)).isoformat()
        return self.client.post(reverse('borrow_item', args=[listing.id]), {'return_date': when, 'message': 'hi'})

    def test_full_borrow_flow(self):
        listing = self.make_listing()
        self.client.login(username='bob', password='pw')
        self.request_borrow(listing)
        req = BorrowRequest.objects.get()
        self.assertEqual(req.status, 'pending')
        self.assertTrue(Notification.objects.filter(user=self.a).exists())

        self.client.login(username='alice', password='pw')
        self.client.post(reverse('update_borrow_request', args=[req.id]), {'action': 'approve'})
        req.refresh_from_db(); listing.refresh_from_db()
        self.assertEqual((req.status, listing.status), ('approved', 'lent'))
        self.assertTrue(Notification.objects.filter(user=self.b).exists())

        self.client.post(reverse('update_borrow_request', args=[req.id]), {'action': 'return'})
        req.refresh_from_db(); listing.refresh_from_db()
        self.assertEqual((req.status, listing.status), ('returned', 'available'))

    def test_cannot_borrow_own_or_sale_item(self):
        own = self.make_listing()
        self.client.login(username='alice', password='pw')
        self.request_borrow(own)
        self.assertEqual(BorrowRequest.objects.count(), 0)
        sale = self.make_listing(seller=self.b, listing_type='sell')
        self.assertEqual(self.client.get(reverse('borrow_item', args=[sale.id])).status_code, 404)

    def test_past_date_and_duplicates_rejected(self):
        listing = self.make_listing()
        self.client.login(username='bob', password='pw')
        self.request_borrow(listing, days=-1)
        self.assertEqual(BorrowRequest.objects.count(), 0)
        self.request_borrow(listing); self.request_borrow(listing)
        self.assertEqual(BorrowRequest.objects.count(), 1)

    def test_only_owner_can_decide(self):
        listing = self.make_listing()
        req = BorrowRequest.objects.create(listing=listing, borrower=self.b,
                                           return_date=timezone.localdate() + timedelta(days=2))
        self.client.login(username='bob', password='pw')
        r = self.client.post(reverse('update_borrow_request', args=[req.id]), {'action': 'approve'})
        self.assertEqual(r.status_code, 404)


class LostFoundNoticeTests(BaseCase):
    def test_only_owner_resolves(self):
        item = LostFoundItem.objects.create(user=self.a, community=self.community, item_type='lost',
                                            title='Wallet', description='d', location='l', contact='c')
        self.client.login(username='bob', password='pw')
        self.assertEqual(self.client.post(reverse('resolve_lost_found', args=[item.id])).status_code, 403)
        self.client.login(username='alice', password='pw')
        self.client.post(reverse('resolve_lost_found', args=[item.id]))
        item.refresh_from_db()
        self.assertEqual(item.status, 'resolved')

    def test_normal_user_cannot_post_announcement_but_admin_can(self):
        url = reverse('add_notice', args=[self.community.id])
        data = {'title': 'T', 'content': 'C', 'notice_type': 'announcement', 'is_pinned': 'on'}
        self.client.login(username='alice', password='pw')
        self.client.post(url, data)                      # members may not post announcements
        self.assertFalse(Notice.objects.exists())
        self.client.login(username='admin1', password='pw')
        self.client.post(url, data)
        self.assertTrue(Notice.objects.filter(is_pinned=True).exists())
        self.assertTrue(Notification.objects.filter(user=self.a).exists())

    def test_moderator_can_post_notice(self):
        Membership.objects.filter(user=self.a).update(role='moderator')
        self.client.login(username='alice', password='pw')
        r = self.client.post(reverse('add_notice', args=[self.community.id]),
                             {'title': 'T', 'content': 'C', 'notice_type': 'general'})
        self.assertEqual(r.status_code, 302)


class NotificationTests(BaseCase):
    def test_cannot_read_others_notification(self):
        n = Notification.objects.create(user=self.a, message='hi')
        self.client.login(username='bob', password='pw')
        self.assertEqual(self.client.post(reverse('mark_notification_read', args=[n.id])).status_code, 404)


class AdminFeatureTests(BaseCase):
    def test_dashboard_staff_only(self):
        self.client.login(username='alice', password='pw')
        self.assertEqual(self.client.get(reverse('admin_dashboard')).status_code, 403)
        self.client.login(username='admin1', password='pw')
        self.assertEqual(self.client.get(reverse('admin_dashboard')).status_code, 200)

    def test_community_request_approval_creates_community(self):
        req = CommunityRequest.objects.create(user=self.a, name='New Colony', community_type='neighbourhood',
                                              location='Idukki', description='d')
        self.client.login(username='admin1', password='pw')
        self.client.post(reverse('decide_community_request', args=[req.id]), {'action': 'approve'})
        c = Community.objects.get(name='New Colony')
        self.assertTrue(Membership.objects.filter(user=self.a, community=c, role='moderator', status='approved').exists())

    def test_moderator_approves_member_but_member_cannot(self):
        m = Membership.objects.get(user=self.c)
        self.client.login(username='bob', password='pw')
        self.assertEqual(self.client.post(reverse('decide_membership', args=[m.id]), {'action': 'approve'}).status_code, 403)
        Membership.objects.filter(user=self.a).update(role='moderator')
        self.client.login(username='alice', password='pw')
        self.client.post(reverse('decide_membership', args=[m.id]), {'action': 'approve'})
        m.refresh_from_db()
        self.assertEqual(m.status, 'approved')

    def test_report_flow(self):
        listing = self.make_listing(seller=self.a)
        self.client.login(username='bob', password='pw')
        self.client.post(reverse('report_content', args=['listing', listing.id]), {'reason': 'spam'})
        report = Report.objects.get()
        self.client.login(username='admin1', password='pw')
        self.client.post(reverse('resolve_report', args=[report.id]), {'action': 'remove'})
        self.assertFalse(Listing.objects.filter(id=listing.id).exists())


class ShopTests(BaseCase):
    def test_shop_shows_only_my_communities_items(self):
        mine = self.make_listing(title='Mine visible', seller=self.b)
        Listing.objects.create(seller=self.b, community=self.other_community, title='Hidden item', description='d',
                               category='books', listing_type='sell', price=5)
        self.client.login(username='alice', password='pw')
        r = self.client.get(reverse('shop'))
        self.assertContains(r, 'Mine visible')
        self.assertNotContains(r, 'Hidden item')

    def test_shop_filters_by_rent_unit_and_price(self):
        self.make_listing(title='Weekly headphones', seller=self.b, price=50, rent_unit='week')
        self.make_listing(title='Daily lamp', seller=self.b, price=10, rent_unit='day')
        self.client.login(username='alice', password='pw')
        r = self.client.get(reverse('shop'), {'unit': 'week'})
        self.assertContains(r, 'Weekly headphones')
        self.assertNotContains(r, 'Daily lamp')
        r = self.client.get(reverse('shop'), {'max': '20'})
        self.assertContains(r, 'Daily lamp')
        self.assertNotContains(r, 'Weekly headphones')

    def test_price_label_shows_rent_unit(self):
        l = self.make_listing(price=20, rent_unit='hour')
        self.assertEqual(l.price_label, '\u20b920 / hour')

    def test_pending_member_cannot_buy(self):
        l = self.make_listing(seller=self.a, listing_type='sell', price=100)
        self.client.login(username='carol', password='pw')
        self.assertEqual(self.client.get(reverse('buy_item', args=[l.id])).status_code, 403)


class BuyTests(BaseCase):
    def setUp(self):
        super().setUp()
        Profile.objects.create(user=self.a, upi_id='alice@okaxis', phone='9895012345')
        self.item = self.make_listing(seller=self.a, listing_type='sell', price=250, title='Maths book')

    def test_full_upi_purchase_flow(self):
        self.client.login(username='bob', password='pw')
        r = self.client.post(reverse('buy_item', args=[self.item.id]), {'method': 'upi'})
        order = Order.objects.get()
        self.assertRedirects(r, reverse('order_detail', args=[order.id]))
        page = self.client.get(reverse('order_detail', args=[order.id]))
        self.assertContains(page, '<svg')            # QR code
        self.assertContains(page, 'alice@okaxis')
        # a too-short reference is refused
        self.client.post(reverse('order_action', args=[order.id]), {'action': 'paid', 'upi_ref': '123'})
        order.refresh_from_db(); self.assertEqual(order.status, 'awaiting')
        self.client.post(reverse('order_action', args=[order.id]), {'action': 'paid', 'upi_ref': 'UTR123456789'})
        order.refresh_from_db(); self.assertEqual(order.status, 'paid')
        # buyer cannot confirm own payment
        self.client.post(reverse('order_action', args=[order.id]), {'action': 'confirm'})
        order.refresh_from_db(); self.assertEqual(order.status, 'paid')
        # seller confirms -> item sold
        self.client.logout(); self.client.login(username='alice', password='pw')
        self.client.post(reverse('order_action', args=[order.id]), {'action': 'confirm'})
        order.refresh_from_db(); self.item.refresh_from_db()
        self.assertEqual(order.status, 'confirmed'); self.assertEqual(self.item.status, 'sold')

    def test_upi_needs_seller_upi_id(self):
        Profile.objects.filter(user=self.a).update(upi_id='')
        self.client.login(username='bob', password='pw')
        self.client.post(reverse('buy_item', args=[self.item.id]), {'method': 'upi'})
        self.assertEqual(Order.objects.count(), 0)

    def test_cannot_buy_own_item_or_view_others_order(self):
        self.client.login(username='alice', password='pw')
        self.client.post(reverse('buy_item', args=[self.item.id]), {'method': 'cash'})
        self.assertEqual(Order.objects.count(), 0)
        order = Order.objects.create(listing=self.item, buyer=self.b, amount=250)
        self.client.logout(); self.client.login(username='carol', password='pw')
        self.assertEqual(self.client.get(reverse('order_detail', args=[order.id])).status_code, 403)


class RentTests(BaseCase):
    def test_borrow_stores_units_and_total(self):
        item = self.make_listing(seller=self.a, price=30, rent_unit='day')
        self.client.login(username='bob', password='pw')
        d = (timezone.localdate() + timedelta(days=3)).isoformat()
        self.client.post(reverse('borrow_item', args=[item.id]), {'return_date': d, 'units': '3'})
        req = BorrowRequest.objects.get()
        self.assertEqual(req.units, 3); self.assertEqual(req.total_rent, 90)


class ChatTests(BaseCase):
    def setUp(self):
        super().setUp()
        self.item = self.make_listing(seller=self.a, listing_type='sell', price=10)
        Profile.objects.create(user=self.a, phone='9895012345')
        Profile.objects.create(user=self.b, phone='9895099999')

    def start(self):
        self.client.login(username='bob', password='pw')
        self.client.post(reverse('start_chat', args=[self.item.id]), {'body': 'Is it available?'})
        return Conversation.objects.get()

    def test_chat_needs_acceptance_before_replies(self):
        convo = self.start()
        self.assertEqual(convo.status, 'pending')
        self.client.post(reverse('chat', args=[convo.id]), {'action': 'send', 'body': 'hello??'})
        self.assertEqual(Message.objects.count(), 1)       # blocked until accepted
        self.client.logout(); self.client.login(username='alice', password='pw')
        self.client.post(reverse('chat', args=[convo.id]), {'action': 'accept'})
        self.client.post(reverse('chat', args=[convo.id]), {'action': 'send', 'body': 'Yes it is'})
        self.assertEqual(Message.objects.count(), 2)

    def test_whatsapp_hidden_until_shared(self):
        convo = self.start()
        self.client.logout(); self.client.login(username='alice', password='pw')
        self.client.post(reverse('chat', args=[convo.id]), {'action': 'accept'})
        self.client.logout(); self.client.login(username='bob', password='pw')
        self.assertNotContains(self.client.get(reverse('chat', args=[convo.id])), 'wa.me')
        self.client.logout(); self.client.login(username='alice', password='pw')
        self.client.post(reverse('chat', args=[convo.id]), {'action': 'share'})
        self.client.logout(); self.client.login(username='bob', password='pw')
        self.assertContains(self.client.get(reverse('chat', args=[convo.id])), 'wa.me/919895012345')

    def test_outsider_cannot_open_chat(self):
        convo = self.start()
        self.client.logout(); self.client.login(username='carol', password='pw')
        self.assertEqual(self.client.get(reverse('chat', args=[convo.id])).status_code, 403)


class NoticeBoardMemberTests(BaseCase):
    def test_member_can_post_issue_but_not_announcement_or_pin(self):
        self.client.login(username='alice', password='pw')
        url = reverse('add_notice', args=[self.community.id])
        self.client.post(url, {'title': 'Pothole', 'content': 'Road is damaged', 'notice_type': 'issue', 'is_pinned': 'on'})
        n = Notice.objects.get(); self.assertEqual(n.notice_type, 'issue'); self.assertFalse(n.is_pinned)
        r = self.client.post(url, {'title': 'Fake', 'content': 'x', 'notice_type': 'announcement'})
        self.assertEqual(Notice.objects.count(), 1)

    def test_pending_member_cannot_post(self):
        self.client.login(username='carol', password='pw')
        r = self.client.post(reverse('add_notice', args=[self.community.id]),
                             {'title': 'x', 'content': 'y', 'notice_type': 'issue'})
        self.assertEqual(r.status_code, 403)

    def test_author_can_delete_own_post_only(self):
        n = Notice.objects.create(community=self.community, title='t', content='c', notice_type='issue', created_by=self.a)
        self.client.login(username='bob', password='pw')
        self.assertEqual(self.client.post(reverse('notice_action', args=[n.id]), {'action': 'delete'}).status_code, 403)
        self.client.logout(); self.client.login(username='alice', password='pw')
        self.client.post(reverse('notice_action', args=[n.id]), {'action': 'delete'})
        self.assertEqual(Notice.objects.count(), 0)
