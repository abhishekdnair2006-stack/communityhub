import csv
from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.core.paginator import Paginator
from django.db.models import Q, Count
from django.http import HttpResponse
from django.shortcuts import render, get_object_or_404, redirect
from datetime import timedelta
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.urls import reverse
from django.views.decorators.http import require_POST

from .models import (Community, Membership, Listing, BorrowRequest, LostFoundItem, Notice, Notification,
                     CommunityRequest, Report)


# ---------- Small helpers (used by many views) ----------

def is_member(user, community):
    """True only if the user has an APPROVED membership in this community."""
    return Membership.objects.filter(user=user, community=community, status='approved').exists()


def can_view(user, community):
    """Approved members can view a community. Staff may view it to administer it."""
    return user.is_staff or is_member(user, community)


def is_manager(user, community):
    """Admins (staff) and approved moderators of this community can manage it."""
    return user.is_staff or Membership.objects.filter(
        user=user, community=community, status='approved', role='moderator').exists()


def notify(user, message, link=''):
    Notification.objects.create(user=user, message=message, link=link)


def notify_staff(message, link=''):
    for admin_user in User.objects.filter(is_staff=True):
        notify(admin_user, message, link)


def denied(request):
    return render(request, 'communities/access_denied.html', status=403)


# ---------- Communities ----------

def community_list(request):
    search = request.GET.get('search', '').strip()
    communities = Community.objects.all().order_by('name')
    if search:
        communities = communities.filter(Q(name__icontains=search) | Q(location__icontains=search))

    # Attach the logged-in user's membership status to each community card.
    my_status = {}
    if request.user.is_authenticated:
        my_status = {m.community_id: m.status for m in Membership.objects.filter(user=request.user)}
    for c in communities:
        c.my_status = my_status.get(c.id)

    return render(request, 'communities/community_list.html', {'communities': communities, 'search': search})


@login_required
@require_POST
def join_community(request, community_id):
    community = get_object_or_404(Community, id=community_id)
    membership, created = Membership.objects.get_or_create(
        user=request.user, community=community, defaults={'status': 'pending'})

    if created:
        message = "Your request has been sent. An admin will review it soon."
    elif membership.status == 'approved':
        message = "You are already a member of this community."
    elif membership.status == 'rejected':
        message = "Your earlier request was rejected. Please contact the community admin."
    else:
        message = "You have already requested to join. Your request is still pending."

    return render(request, 'communities/join_result.html', {
        'message': message, 'community': community, 'status': membership.status, 'created': created})


@login_required
def community_detail(request, community_id):
    community = get_object_or_404(Community, id=community_id)
    if not can_view(request.user, community):
        return denied(request)

    return render(request, 'communities/community_detail.html', {
        'community': community,
        'member_count': Membership.objects.filter(community=community, status='approved').count(),
        'listing_count': Listing.objects.filter(community=community, status='available').count(),
        'open_lost_found': LostFoundItem.objects.filter(community=community, status='open').count(),
        'notice_count': Notice.objects.filter(community=community).count(),
        'my_listing_count': Listing.objects.filter(community=community, seller=request.user).count(),
        'can_manage': is_manager(request.user, community),
        'incoming_count': BorrowRequest.objects.filter(
            listing__seller=request.user, listing__community=community, status='pending').count(),
    })


# ---------- Marketplace ----------

def read_listing_form(post):
    """Validates the add/edit listing form. Returns (cleaned_values, error_message)."""
    values = {
        'title': post.get('title', '').strip(),
        'description': post.get('description', '').strip(),
        'category': post.get('category', ''),
        'listing_type': post.get('listing_type', ''),
        'price': post.get('price', '').strip(),
        'rent_unit': post.get('rent_unit', 'day'),
        'image_url': post.get('image_url', '').strip(),
    }
    if not values['title'] or not values['description']:
        return values, 'Please fill in the item name and description.'
    if values['category'] not in [c[0] for c in Listing.CATEGORIES]:
        return values, 'Please choose a valid category.'
    if values['listing_type'] not in [t[0] for t in Listing.LISTING_TYPES]:
        return values, 'Please choose whether this is for sale or for lending.'
    if values['rent_unit'] not in [u[0] for u in Listing.RENT_UNITS]:
        values['rent_unit'] = 'day'
    try:
        price = Decimal(values['price'])
        if price < 0:
            raise InvalidOperation
    except InvalidOperation:
        return values, 'Please enter a valid price (0 or more).'
    values['price'] = price
    return values, None


@login_required
def marketplace(request, community_id):
    community = get_object_or_404(Community, id=community_id)
    if not can_view(request.user, community):
        return denied(request)

    listings = Listing.objects.filter(community=community, status='available').select_related('seller')
    category = request.GET.get('category', '')
    listing_type = request.GET.get('type', '')
    if category in [c[0] for c in Listing.CATEGORIES]:
        listings = listings.filter(category=category)
    if listing_type in ['sell', 'lend']:
        listings = listings.filter(listing_type=listing_type)
    q = request.GET.get('q', '').strip()
    if q:
        listings = listings.filter(Q(title__icontains=q) | Q(description__icontains=q))

    page = Paginator(listings.order_by('-created_at'), 9).get_page(request.GET.get('page'))
    return render(request, 'communities/marketplace.html', {
        'community': community, 'listings': page, 'page': page, 'q': q,
        'categories': Listing.CATEGORIES, 'category': category, 'listing_type': listing_type})


@login_required
def add_listing(request, community_id):
    community = get_object_or_404(Community, id=community_id)
    if not is_member(request.user, community):
        return denied(request)

    values, error = {'listing_type': 'sell'}, None
    if request.method == 'POST':
        values, error = read_listing_form(request.POST)
        if not error:
            Listing.objects.create(seller=request.user, community=community,
                                   image=request.FILES.get('image') or '', **values)
            messages.success(request, 'Your item has been posted.')
            return redirect('marketplace', community_id=community.id)

    return render(request, 'communities/add_listing.html', {
        'community': community, 'v': values, 'error': error,
        'categories': Listing.CATEGORIES, 'types': Listing.LISTING_TYPES, 'units': Listing.RENT_UNITS})


@login_required
def my_listings(request):
    listings = Listing.objects.filter(seller=request.user).select_related('community').order_by('-created_at')
    return render(request, 'communities/my_listings.html', {'listings': listings})


@login_required
def edit_listing(request, listing_id):
    listing = get_object_or_404(Listing, id=listing_id, seller=request.user)  # owner only
    if not is_member(request.user, listing.community):
        return denied(request)

    values, error = listing, None
    if request.method == 'POST':
        values, error = read_listing_form(request.POST)
        if not error:
            for field, value in values.items():
                setattr(listing, field, value)
            if request.FILES.get('image'):
                listing.image = request.FILES['image']
            listing.save()
            messages.success(request, 'Listing updated.')
            return redirect('my_listings')

    return render(request, 'communities/add_listing.html', {
        'community': listing.community, 'listing': listing, 'editing': True, 'v': values, 'error': error,
        'categories': Listing.CATEGORIES, 'types': Listing.LISTING_TYPES, 'units': Listing.RENT_UNITS})


@login_required
@require_POST
def delete_listing(request, listing_id):
    listing = get_object_or_404(Listing, id=listing_id, seller=request.user)
    listing.delete()
    messages.success(request, 'Listing deleted.')
    return redirect('my_listings')


@login_required
@require_POST
def set_listing_status(request, listing_id):
    """Owner marks a listing as sold/unavailable, or makes it available again."""
    listing = get_object_or_404(Listing, id=listing_id, seller=request.user)
    action = request.POST.get('action')
    if action == 'sold' and listing.status == 'available':
        listing.status = 'sold'
        messages.success(request, 'Marked as sold / unavailable. It is hidden from the marketplace.')
    elif action == 'available' and listing.status == 'sold':
        listing.status = 'available'
        messages.success(request, 'Listing is available again.')
    else:
        messages.error(request, 'That change is not possible for this listing right now.')
    listing.save(update_fields=['status'])
    return redirect('my_listings')


# ---------- Borrowing ----------

@login_required
def borrow_item(request, listing_id):
    listing = get_object_or_404(Listing, id=listing_id, listing_type='lend', status='available')
    if not is_member(request.user, listing.community):
        return denied(request)

    context = {'listing': listing, 'min_date': timezone.localdate() + timedelta(days=1)}

    if listing.seller == request.user:
        context['error'] = 'You cannot request to borrow your own item.'
        return render(request, 'communities/borrow_request.html', context)

    if request.method == 'POST':
        return_date = parse_date(request.POST.get('return_date', '') or '')
        message = request.POST.get('message', '').strip()
        try:
            units = max(1, min(int(request.POST.get('units', '1')), 365))
        except ValueError:
            units = 1

        if not return_date or return_date <= timezone.localdate():
            context['error'] = 'Please select a return date in the future.'
        elif BorrowRequest.objects.filter(listing=listing, borrower=request.user,
                                          status__in=['pending', 'approved']).exists():
            context['error'] = 'You already have an active request for this item.'
        else:
            BorrowRequest.objects.create(listing=listing, borrower=request.user,
                                         return_date=return_date, units=units, message=message)
            notify(listing.seller, f"{request.user.username} requested to borrow {listing.title}.",
                   reverse('borrow_requests'))
            messages.success(request, 'Request sent. The owner will be notified.')
            return redirect('borrow_requests')

    return render(request, 'communities/borrow_request.html', context)


@login_required
def borrow_requests(request):
    incoming = BorrowRequest.objects.filter(listing__seller=request.user) \
        .select_related('listing', 'borrower', 'listing__community').order_by('-requested_at')
    outgoing = BorrowRequest.objects.filter(borrower=request.user) \
        .select_related('listing', 'listing__seller', 'listing__community').order_by('-requested_at')
    return render(request, 'communities/borrow_requests.html', {
        'requests': incoming, 'my_requests': outgoing})


@login_required
@require_POST
def update_borrow_request(request, request_id):
    # Only the owner of the listing can change the status.
    borrow_request = get_object_or_404(BorrowRequest, id=request_id, listing__seller=request.user)
    action = request.POST.get('action')
    title = borrow_request.listing.title

    listing = borrow_request.listing
    link = reverse('borrow_requests')

    if borrow_request.status == 'pending' and action == 'approve':
        if listing.status != 'available':
            messages.error(request, 'This item is not available (already lent out or sold).')
            return redirect('borrow_requests')
        borrow_request.status = 'approved'
        borrow_request.save(update_fields=['status'])
        listing.status = 'lent'                      # item is now lent out
        listing.save(update_fields=['status'])
        notify(borrow_request.borrower, f"Your request to borrow {title} has been approved.", link)
        messages.success(request, 'Request approved. The item is marked as lent out.')

    elif borrow_request.status == 'pending' and action == 'reject':
        borrow_request.status = 'rejected'
        borrow_request.save(update_fields=['status'])
        notify(borrow_request.borrower, f"Your request to borrow {title} has been rejected.", link)
        messages.success(request, 'Request rejected.')

    elif borrow_request.status == 'approved' and action == 'return':
        borrow_request.status = 'returned'
        borrow_request.save(update_fields=['status'])
        if listing.status == 'lent':
            listing.status = 'available'             # back on the marketplace
            listing.save(update_fields=['status'])
        notify(borrow_request.borrower, f"{title} has been marked as returned. Thank you!", link)
        messages.success(request, 'Marked as returned. The item is available again.')

    return redirect('borrow_requests')


# ---------- Lost & Found ----------

@login_required
def lost_found_list(request, community_id):
    community = get_object_or_404(Community, id=community_id)
    if not can_view(request.user, community):
        return denied(request)

    items = LostFoundItem.objects.filter(community=community).select_related('user')
    kind = request.GET.get('type', '')
    if kind in ('lost', 'found'):
        items = items.filter(item_type=kind)

    return render(request, 'communities/lost_found.html', {
        'community': community, 'items': items.order_by('status', '-created_at'), 'kind': kind,
        'can_manage': is_manager(request.user, community)})


@login_required
def add_lost_found(request, community_id):
    community = get_object_or_404(Community, id=community_id)
    if not is_member(request.user, community):
        return denied(request)

    v, error = {'item_type': request.GET.get('type', 'lost')}, None
    if request.method == 'POST':
        v = {k: request.POST.get(k, '').strip() for k in ('item_type', 'title', 'description', 'location', 'contact')}
        if v['item_type'] not in ('lost', 'found'):
            error = 'Please choose Lost or Found.'
        elif not all(v[k] for k in ('title', 'description', 'location', 'contact')):
            error = 'Please fill in every field.'
        else:
            LostFoundItem.objects.create(user=request.user, community=community, **v)
            messages.success(request, 'Your post is now on the board.')
            return redirect('lost_found_list', community_id=community.id)

    return render(request, 'communities/add_lost_found.html', {'community': community, 'v': v, 'error': error})


@login_required
@require_POST
def resolve_lost_found(request, item_id):
    item = get_object_or_404(LostFoundItem, id=item_id)
    if item.user != request.user and not is_manager(request.user, item.community):
        return denied(request)
    if item.status == 'open':
        item.status = 'resolved'
        item.save(update_fields=['status'])
        messages.success(request, 'Marked as resolved.')
    return redirect('lost_found_list', community_id=item.community.id)


# ---------- Noticeboard ----------

@login_required
def notice_list(request, community_id):
    community = get_object_or_404(Community, id=community_id)
    if not can_view(request.user, community):
        return denied(request)
    notices = Notice.objects.filter(community=community).select_related('created_by') \
        .order_by('-is_pinned', '-created_at')
    return render(request, 'communities/notices.html', {
        'community': community, 'notices': notices, 'can_manage': is_manager(request.user, community),
        'can_post': is_member(request.user, community) or request.user.is_staff})


@login_required
def add_notice(request, community_id):
    """Admins/moderators post announcements; every approved member can post issues, help requests and general notes."""
    community = get_object_or_404(Community, id=community_id)
    manager = is_manager(request.user, community)
    if not (manager or is_member(request.user, community)):
        return denied(request)

    allowed = [t for t in Notice.NOTICE_TYPES if manager or t[0] in Notice.MEMBER_TYPES]
    v, error = {'notice_type': allowed[0][0] if manager else 'issue'}, None
    if request.method == 'POST':
        v = {'title': request.POST.get('title', '').strip(), 'content': request.POST.get('content', '').strip(),
             'notice_type': request.POST.get('notice_type', ''),
             'is_pinned': manager and request.POST.get('is_pinned') == 'on'}
        if not v['title'] or not v['content']:
            error = 'Please add a title and the details.'
        elif v['notice_type'] not in [t[0] for t in allowed]:
            error = 'Please choose a valid type.'
        else:
            Notice.objects.create(community=community, created_by=request.user, **v)
            link = reverse('notice_list', args=[community.id])
            if manager:
                recipients = Membership.objects.filter(community=community, status='approved')
                for m in recipients:
                    notify(m.user, f"New notice in {community.name}: {v['title']}", link)
                messages.success(request, 'Notice published and members notified.')
            else:
                for m in Membership.objects.filter(community=community, status='approved', role='moderator'):
                    notify(m.user, f"{request.user.username} posted in {community.name}: {v['title']}", link)
                messages.success(request, 'Posted on the noticeboard.')
            return redirect('notice_list', community_id=community.id)

    return render(request, 'communities/add_notice.html', {
        'community': community, 'v': v, 'error': error, 'types': allowed, 'manager': manager})


@login_required
@require_POST
def notice_action(request, notice_id):
    notice = get_object_or_404(Notice, id=notice_id)
    action = request.POST.get('action')
    own_post = notice.created_by == request.user and action == 'delete'
    if not (own_post or is_manager(request.user, notice.community)):
        return denied(request)
    if action == 'delete':
        notice.delete()
        messages.success(request, 'Notice deleted.')
    elif action in ('pin', 'unpin'):
        notice.is_pinned = action == 'pin'
        notice.save(update_fields=['is_pinned'])
        messages.success(request, 'Notice pinned.' if notice.is_pinned else 'Notice unpinned.')
    return redirect('notice_list', community_id=notice.community_id)


# ---------- Notifications ----------

@login_required
def notification_list(request):
    notifications = Notification.objects.filter(user=request.user).order_by('-created_at')
    return render(request, 'communities/notifications.html', {'notifications': notifications})


@login_required
@require_POST
def mark_notification_read(request, notification_id):
    notification = get_object_or_404(Notification, id=notification_id, user=request.user)
    notification.is_read = True
    notification.save(update_fields=['is_read'])
    return redirect('notification_list')


@login_required
@require_POST
def mark_all_notifications_read(request):
    Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)
    return redirect('notification_list')


@login_required
@require_POST
def decide_membership(request, membership_id):
    membership = get_object_or_404(Membership, id=membership_id)
    if not is_manager(request.user, membership.community):
        return denied(request)
    action = request.POST.get('action')
    if action in ('approve', 'reject'):
        membership.status = 'approved' if action == 'approve' else 'rejected'
        membership.save(update_fields=['status'])
        link = reverse('community_detail', args=[membership.community_id]) if membership.status == 'approved' else reverse('community_list')
        notify(membership.user, f"Your request to join {membership.community.name} was {membership.status}.", link)
        messages.success(request, f"{membership.user.username}: {membership.status}.")
    if request.POST.get('from') == 'manage':
        return redirect('manage_community', community_id=membership.community_id)
    return redirect('admin_dashboard')


# ---------- Student dashboard, new-community requests ----------

@login_required
def my_communities(request):
    """The student's personal dashboard."""
    memberships = Membership.objects.filter(user=request.user).select_related('community').order_by('-joined_at')
    return render(request, 'communities/my_communities.html', {
        'memberships': memberships,
        'my_active_listings': Listing.objects.filter(seller=request.user, status='available').count(),
        'incoming_pending': BorrowRequest.objects.filter(listing__seller=request.user, status='pending').count(),
        'my_borrowing': BorrowRequest.objects.filter(borrower=request.user, status='approved').count(),
        'my_open_posts': LostFoundItem.objects.filter(user=request.user, status='open').count(),
        'my_requests': CommunityRequest.objects.filter(user=request.user).order_by('-created_at')[:5],
    })


@login_required
def request_community(request):
    v, error = {'community_type': 'neighbourhood'}, None
    if request.method == 'POST':
        v = {k: request.POST.get(k, '').strip() for k in ('name', 'community_type', 'location', 'description')}
        if not all(v.values()):
            error = 'Please fill in every field.'
        elif v['community_type'] not in [t[0] for t in Community.COMMUNITY_TYPES]:
            error = 'Please choose a community type.'
        elif Community.objects.filter(name__iexact=v['name'], location__iexact=v['location']).exists():
            error = 'This community already exists. Search for it on the Explore page and request to join.'
        elif CommunityRequest.objects.filter(user=request.user, name__iexact=v['name'], status='pending').exists():
            error = 'You have already requested this community. Please wait for the admin.'
        else:
            CommunityRequest.objects.create(user=request.user, **v)
            notify_staff(f"{request.user.username} requested a new community: {v['name']}.", reverse('admin_dashboard'))
            messages.success(request, 'Request sent. An admin will review it and add the community.')
            return redirect('my_communities')
    return render(request, 'communities/request_community.html', {
        'v': v, 'error': error, 'types': Community.COMMUNITY_TYPES})


@login_required
@require_POST
def decide_community_request(request, request_id):
    if not request.user.is_staff:
        return denied(request)
    req = get_object_or_404(CommunityRequest, id=request_id, status='pending')
    if request.POST.get('action') == 'approve':
        community = Community.objects.create(name=req.name, community_type=req.community_type,
                                             location=req.location, description=req.description)
        # The student who proposed it becomes its first approved member and moderator.
        Membership.objects.update_or_create(user=req.user, community=community,
                                            defaults={'status': 'approved', 'role': 'moderator'})
        req.status = 'approved'
        notify(req.user, f"{community.name} has been created. You are its first moderator.",
               reverse('community_detail', args=[community.id]))
        messages.success(request, f"{community.name} created.")
    else:
        req.status = 'rejected'
        notify(req.user, f"Your request to add {req.name} was not approved.")
        messages.success(request, 'Request rejected.')
    req.save(update_fields=['status'])
    return redirect('admin_dashboard')


# ---------- Community management (admin or community moderator) ----------

@login_required
def manage_community(request, community_id):
    community = get_object_or_404(Community, id=community_id)
    if not is_manager(request.user, community):
        return denied(request)
    members = Membership.objects.filter(community=community).select_related('user')
    return render(request, 'communities/manage_community.html', {
        'community': community,
        'pending': members.filter(status='pending').order_by('joined_at'),
        'approved': members.filter(status='approved').order_by('-role', 'user__username'),
        'reports': Report.objects.filter(community=community, status='open').select_related('reporter', 'listing', 'lost_item'),
    })


@login_required
@require_POST
def set_member_role(request, membership_id):
    """Only admins (staff) can promote a member to moderator or demote them."""
    if not request.user.is_staff:
        return denied(request)
    membership = get_object_or_404(Membership, id=membership_id, status='approved')
    membership.role = 'moderator' if request.POST.get('action') == 'promote' else 'member'
    membership.save(update_fields=['role'])
    messages.success(request, f"{membership.user.username} is now a {membership.role}.")
    return redirect('manage_community', community_id=membership.community_id)


@login_required
@require_POST
def remove_member(request, membership_id):
    membership = get_object_or_404(Membership, id=membership_id)
    if not is_manager(request.user, membership.community):
        return denied(request)
    if membership.role == 'moderator' and not request.user.is_staff:
        messages.error(request, 'Only an admin can remove a moderator.')
    else:
        membership.delete()
        messages.success(request, 'Member removed.')
    return redirect('manage_community', community_id=membership.community_id)


# ---------- Reports ----------

@login_required
@require_POST
def report_content(request, kind, object_id):
    if kind == 'listing':
        target = get_object_or_404(Listing, id=object_id)
        fields = {'listing': target}
    else:
        target = get_object_or_404(LostFoundItem, id=object_id)
        fields = {'lost_item': target}
    if not is_member(request.user, target.community):
        return denied(request)
    reason = request.POST.get('reason', '').strip()
    if not reason:
        messages.error(request, 'Please tell us why you are reporting this.')
    elif Report.objects.filter(reporter=request.user, status='open', **fields).exists():
        messages.error(request, 'You have already reported this. An admin will review it.')
    else:
        Report.objects.create(reporter=request.user, community=target.community, reason=reason, **fields)
        notify_staff(f"New report in {target.community.name}: {target.title}", reverse('admin_dashboard'))
        messages.success(request, 'Thanks. Your report was sent to the admins.')
    return redirect(request.META.get('HTTP_REFERER') or 'community_list')


@login_required
@require_POST
def resolve_report(request, report_id):
    report = get_object_or_404(Report, id=report_id)
    if not is_manager(request.user, report.community):
        return denied(request)
    target = report.listing or report.lost_item
    if request.POST.get('action') == 'remove':
        owner, title = (target.seller if report.listing else target.user), target.title
        target.delete()                              # the report is deleted with it
        notify(owner, f"Your post “{title}” was removed by a moderator after a report.")
        messages.success(request, 'Content removed.')
    else:
        report.status = 'resolved'
        report.save(update_fields=['status'])
        messages.success(request, 'Report dismissed.')
    if request.POST.get('from') == 'manage':
        return redirect('manage_community', community_id=report.community_id)
    return redirect('admin_dashboard')


@login_required
def export_memberships_csv(request):
    if not request.user.is_staff:
        return denied(request)
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="memberships.csv"'
    writer = csv.writer(response)
    writer.writerow(['Username', 'Email', 'Community', 'Status', 'Role', 'Requested on'])
    for m in Membership.objects.select_related('user', 'community').order_by('community__name'):
        writer.writerow([m.user.username, m.user.email, m.community.name, m.status, m.role,
                         m.joined_at.strftime('%Y-%m-%d')])
    return response
