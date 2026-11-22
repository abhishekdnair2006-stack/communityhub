"""Shop feed, buying (UPI), chat and profile views for CommunityHub."""
import io
from decimal import Decimal, InvalidOperation
from urllib.parse import quote

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse
from django.views.decorators.http import require_POST

import segno
from PIL import Image, ImageOps
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.core.validators import validate_email

from .models import Community, Membership, Listing, Order, Profile, Conversation, Message
from .views import is_member, denied, notify


def get_profile(user):
    return Profile.objects.get_or_create(user=user)[0]


def upi_qr_svg(upi_id, name, amount, note):
    """Builds a UPI payment QR (works in GPay, PhonePe, Paytm) as inline SVG."""
    link = 'upi://pay?pa=%s&pn=%s&am=%s&cu=INR&tn=%s' % (quote(upi_id), quote(name), amount, quote(note))
    out = io.BytesIO()
    segno.make(link, error='m').save(out, kind='svg', scale=5, border=2, xmldecl=False, svgns=True,
                                      nl=False, dark='#0F1B33', light='#ffffff')
    return out.getvalue().decode(), link


# ---------- Shop feed (Amazon-style) ----------

@login_required
def shop(request):
    mine = Membership.objects.filter(user=request.user, status='approved').select_related('community')
    my_ids = [m.community_id for m in mine]
    if request.user.is_staff:
        my_ids = list(Community.objects.values_list('id', flat=True))

    listings = Listing.objects.filter(community_id__in=my_ids, status='available').select_related('seller', 'community')
    selected = request.GET.get('community', 'all')
    if selected.isdigit() and int(selected) in my_ids:
        listings = listings.filter(community_id=int(selected))
    else:
        selected = 'all'

    category = request.GET.get('category', '')
    kind = request.GET.get('type', '')
    unit = request.GET.get('unit', '')
    q = request.GET.get('q', '').strip()
    sort = request.GET.get('sort', 'new')
    if category in [c[0] for c in Listing.CATEGORIES]:
        listings = listings.filter(category=category)
    if kind in ('sell', 'lend'):
        listings = listings.filter(listing_type=kind)
    if unit in [u[0] for u in Listing.RENT_UNITS]:
        listings = listings.filter(listing_type='lend', rent_unit=unit)
    if q:
        listings = listings.filter(Q(title__icontains=q) | Q(description__icontains=q))
    try:
        max_price = Decimal(request.GET.get('max', ''))
        listings = listings.filter(price__lte=max_price)
    except InvalidOperation:
        max_price = ''
    listings = listings.order_by({'low': 'price', 'high': '-price'}.get(sort, '-created_at'))

    page = Paginator(listings, 12).get_page(request.GET.get('page'))
    qs = request.GET.copy()
    qs.pop('page', None)
    return render(request, 'communities/shop.html', {
        'listings': page, 'page': page, 'communities': mine, 'selected': selected, 'q': q,
        'category': category, 'kind': kind, 'unit': unit, 'sort': sort, 'max_price': max_price,
        'categories': Listing.CATEGORIES, 'units': Listing.RENT_UNITS, 'qs': qs.urlencode(),
        'has_communities': bool(my_ids)})


# ---------- Buying ----------

@login_required
def buy_item(request, listing_id):
    listing = get_object_or_404(Listing, id=listing_id, listing_type='sell', status='available')
    if not is_member(request.user, listing.community):
        return denied(request)
    if listing.seller == request.user:
        messages.error(request, 'This is your own item.')
        return redirect('shop')
    existing = Order.objects.filter(listing=listing, buyer=request.user, status__in=['awaiting', 'paid']).first()
    if existing:
        return redirect('order_detail', order_id=existing.id)

    seller_upi = get_profile(listing.seller).upi_id
    error = None
    if request.method == 'POST':
        method = request.POST.get('method', 'upi')
        if method not in ('upi', 'cash'):
            method = 'upi'
        if method == 'upi' and not seller_upi:
            error = 'The seller has not added a UPI ID yet. Choose cash, or message the seller.'
        else:
            order = Order.objects.create(listing=listing, buyer=request.user, amount=listing.price,
                                         method=method, note=request.POST.get('note', '').strip()[:500],
                                         status='awaiting' if method == 'upi' else 'paid')
            notify(listing.seller, '%s wants to buy %s.' % (request.user.username, listing.title),
                   reverse('order_detail', args=[order.id]))
            return redirect('order_detail', order_id=order.id)
    return render(request, 'communities/buy.html', {'listing': listing, 'seller_upi': seller_upi, 'error': error})


@login_required
def order_detail(request, order_id):
    order = get_object_or_404(Order.objects.select_related('listing', 'buyer', 'listing__seller'), id=order_id)
    listing = order.listing
    if request.user not in (order.buyer, listing.seller):
        return denied(request)
    is_seller = request.user == listing.seller
    qr = link = None
    seller_upi = get_profile(listing.seller).upi_id
    if order.method == 'upi' and order.status in ('awaiting', 'paid') and not is_seller and seller_upi:
        qr, link = upi_qr_svg(seller_upi, listing.seller.username, order.amount, 'CommunityHub ' + listing.title[:30])
    return render(request, 'communities/order_detail.html', {
        'order': order, 'listing': listing, 'is_seller': is_seller, 'qr': qr, 'upi_link': link,
        'seller_upi': seller_upi})


@login_required
@require_POST
def order_action(request, order_id):
    order = get_object_or_404(Order.objects.select_related('listing'), id=order_id)
    listing = order.listing
    action = request.POST.get('action')
    is_seller = request.user == listing.seller
    if request.user not in (order.buyer, listing.seller):
        return denied(request)

    if action == 'paid' and not is_seller and order.status == 'awaiting':
        ref = request.POST.get('upi_ref', '').strip()[:40]
        if len(ref) < 6:
            messages.error(request, 'Please enter the UPI transaction/reference number (at least 6 characters).')
        else:
            order.upi_ref, order.status = ref, 'paid'
            order.save()
            notify(listing.seller, '%s says they paid for %s. Please check your UPI app and confirm.'
                   % (order.buyer.username, listing.title), reverse('order_detail', args=[order.id]))
            messages.success(request, 'Thanks! The seller will confirm once the money arrives.')
    elif action == 'confirm' and is_seller and order.status == 'paid':
        if listing.status != 'available':
            messages.error(request, 'This item is no longer available.')
        else:
            order.status = 'confirmed'
            order.save()
            listing.status = 'sold'
            listing.save(update_fields=['status'])
            Order.objects.filter(listing=listing, status__in=['awaiting', 'paid']).exclude(id=order.id) \
                .update(status='cancelled')
            notify(order.buyer, 'Your purchase of %s is confirmed. Arrange pickup with %s.'
                   % (listing.title, listing.seller.username), reverse('order_detail', args=[order.id]))
            messages.success(request, 'Sale confirmed. The item is marked as sold.')
    elif action == 'cancel' and order.status in ('awaiting', 'paid'):
        order.status = 'cancelled'
        order.save()
        other = order.buyer if is_seller else listing.seller
        notify(other, 'The order for %s was cancelled by %s.' % (listing.title, request.user.username),
               reverse('order_detail', args=[order.id]))
        messages.success(request, 'Order cancelled.')
    return redirect('order_detail', order_id=order.id)


@login_required
def my_orders(request):
    bought = Order.objects.filter(buyer=request.user).select_related('listing', 'listing__seller').order_by('-created_at')
    sold = Order.objects.filter(listing__seller=request.user).select_related('listing', 'buyer').order_by('-created_at')
    return render(request, 'communities/orders.html', {'bought': bought, 'sold': sold})


# ---------- Profile ----------

def save_avatar(profile, upload):
    """Checks the uploaded picture, crops it to a square and stores it as a small JPEG."""
    if upload.size > 5 * 1024 * 1024:
        raise ValueError('That photo is too big. Please use one under 5 MB.')
    try:
        Image.open(upload).verify()
        upload.seek(0)
        img = ImageOps.exif_transpose(Image.open(upload)).convert('RGB')
    except Exception:
        raise ValueError('That file is not a valid picture. Please use a JPG or PNG.')
    img = ImageOps.fit(img, (400, 400), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, 'JPEG', quality=88)
    if profile.avatar:
        profile.avatar.delete(save=False)
    profile.avatar.save('user%s.jpg' % profile.user_id, ContentFile(buf.getvalue()), save=False)


@login_required
def profile_edit(request):
    profile = get_profile(request.user)
    user = request.user
    error = None
    if request.method == 'POST':
        phone = ''.join(ch for ch in request.POST.get('phone', '') if ch.isdigit())
        upi = request.POST.get('upi_id', '').strip()
        first, last = request.POST.get('first_name', '').strip()[:30], request.POST.get('last_name', '').strip()[:30]
        email = request.POST.get('email', '').strip()[:254]
        try:
            if email:
                validate_email(email)
        except ValidationError:
            error = 'Enter a valid email address.'
        if not error and phone and not (10 <= len(phone) <= 13):
            error = 'Enter a valid phone number (10 digits, with or without country code).'
        elif not error and upi and ('@' not in upi or ' ' in upi):
            error = 'A UPI ID looks like name@bank.'
        if not error:
            try:
                if request.POST.get('remove_avatar') and profile.avatar:
                    profile.avatar.delete(save=False)
                if request.FILES.get('avatar'):
                    save_avatar(profile, request.FILES['avatar'])
            except ValueError as problem:
                error = str(problem)
        if not error:
            profile.phone, profile.upi_id = phone, upi
            profile.save()
            user.first_name, user.last_name, user.email = first, last, email
            user.save(update_fields=['first_name', 'last_name', 'email'])
            messages.success(request, 'Profile saved.')
            return redirect('profile_edit')
    return render(request, 'communities/profile.html', {'profile': profile, 'error': error})


# ---------- Chat ----------

@login_required
@require_POST
def start_chat(request, listing_id):
    listing = get_object_or_404(Listing, id=listing_id)
    if not is_member(request.user, listing.community):
        return denied(request)
    if listing.seller == request.user:
        messages.error(request, 'You cannot message yourself.')
        return redirect('shop')
    body = request.POST.get('body', '').strip()[:1000]
    if not body:
        messages.error(request, 'Write a message first.')
        return redirect(request.META.get('HTTP_REFERER') or 'shop')
    convo, created = Conversation.objects.get_or_create(starter=request.user, other=listing.seller, listing=listing)
    if convo.status == 'declined':
        messages.error(request, 'The owner declined this chat.')
        return redirect('inbox')
    Message.objects.create(conversation=convo, sender=request.user, body=body)
    if created:
        notify(listing.seller, '%s wants to chat about %s.' % (request.user.username, listing.title),
               reverse('chat', args=[convo.id]))
    else:
        notify(listing.seller, 'New message from %s.' % request.user.username, reverse('chat', args=[convo.id]))
    messages.success(request, 'Message sent.' if convo.status == 'accepted'
                     else 'Chat request sent. You can talk once the owner accepts.')
    return redirect('chat', convo_id=convo.id)


@login_required
def inbox(request):
    convos = Conversation.objects.filter(Q(starter=request.user) | Q(other=request.user)) \
        .select_related('starter', 'other', 'listing').order_by('-updated_at')
    rows = []
    for c in convos:
        last = c.messages.order_by('-created_at').first()
        unread = c.messages.filter(is_read=False).exclude(sender=request.user).count()
        rows.append({'c': c, 'partner': c.partner(request.user), 'last': last, 'unread': unread})
    return render(request, 'communities/inbox.html', {'rows': rows})


@login_required
def chat(request, convo_id):
    convo = get_object_or_404(Conversation.objects.select_related('starter', 'other', 'listing'), id=convo_id)
    if request.user not in (convo.starter, convo.other):
        return denied(request)
    partner = convo.partner(request.user)
    i_am_starter = request.user == convo.starter

    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'accept' and request.user == convo.other and convo.status == 'pending':
            convo.status = 'accepted'
            convo.save()
            notify(convo.starter, '%s accepted your chat request.' % request.user.username,
                   reverse('chat', args=[convo.id]))
        elif action == 'decline' and request.user == convo.other and convo.status == 'pending':
            convo.status = 'declined'
            convo.save()
        elif action == 'send' and convo.status == 'accepted':
            body = request.POST.get('body', '').strip()[:1000]
            if body:
                Message.objects.create(conversation=convo, sender=request.user, body=body)
                convo.save()  # bumps updated_at
                notify(partner, 'New message from %s.' % request.user.username, reverse('chat', args=[convo.id]))
        elif action == 'share' and convo.status == 'accepted':
            if not get_profile(request.user).phone:
                messages.error(request, 'Add your phone number in your profile first.')
                return redirect('chat', convo_id=convo.id)
            if i_am_starter:
                convo.starter_shared = True
            else:
                convo.other_shared = True
            convo.save()
            messages.success(request, 'Your WhatsApp number is now visible to %s.' % partner.username)
        elif action == 'unshare' and convo.status == 'accepted':
            if i_am_starter:
                convo.starter_shared = False
            else:
                convo.other_shared = False
            convo.save()
        return redirect('chat', convo_id=convo.id)

    convo.messages.filter(is_read=False).exclude(sender=request.user).update(is_read=True)
    partner_shared = convo.other_shared if i_am_starter else convo.starter_shared
    i_shared = convo.starter_shared if i_am_starter else convo.other_shared
    wa = ''
    if partner_shared:
        phone = get_profile(partner).phone
        if phone:
            wa = 'https://wa.me/' + (phone if len(phone) > 10 else '91' + phone)
    return render(request, 'communities/chat.html', {
        'convo': convo, 'partner': partner, 'chat_messages': convo.messages.select_related('sender'),
        'is_receiver': request.user == convo.other, 'wa_link': wa, 'i_shared': i_shared})
