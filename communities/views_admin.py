"""Admin (staff) pages: dashboard (things to act on), reports (graphs) and the communities list."""
from datetime import timedelta

from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db.models import Count, Q, Sum
from django.db.models.functions import TruncDate
from django.shortcuts import render
from django.utils import timezone

from .models import (Community, Membership, Listing, BorrowRequest, LostFoundItem, CommunityRequest, Report, Order)
from .views import denied

# Chart colours (blue, teal, amber, violet, rose, green)
PALETTE = ['#2563EB', '#0E9F9A', '#D98A0B', '#6B4FE0', '#D63F66', '#14A06F']
STATUS_COLOURS = {'pending': '#D98A0B', 'approved': '#14A06F', 'rejected': '#D63F66', 'returned': '#2563EB',
                  'awaiting': '#D98A0B', 'paid': '#6B4FE0', 'confirmed': '#14A06F', 'cancelled': '#D63F66',
                  'open': '#D98A0B', 'resolved': '#14A06F', 'lost': '#D63F66', 'found': '#14A06F',
                  'sell': '#2563EB', 'lend': '#0E9F9A'}


def staff_only(view):
    """Login required, and only staff may enter."""
    @login_required
    def wrapper(request, *args, **kwargs):
        if not request.user.is_staff:
            return denied(request)
        return view(request, *args, **kwargs)
    wrapper.__name__ = view.__name__
    wrapper.__doc__ = view.__doc__
    return wrapper


def daily_counts(qs, field, days):
    """Number of rows created on each day in `days` (a list of dates)."""
    rows = qs.filter(**{field + '__date__gte': days[0]}).annotate(d=TruncDate(field)).values('d').annotate(n=Count('id'))
    found = {r['d']: r['n'] for r in rows}
    return [found.get(d, 0) for d in days]


def period_stat(qs, field, n):
    """Rows created in the last n days, and the % change against the n days before that."""
    now = timezone.now()
    cur = qs.filter(**{field + '__gte': now - timedelta(days=n)}).count()
    prev = qs.filter(**{field + '__gte': now - timedelta(days=2 * n), field + '__lt': now - timedelta(days=n)}).count()
    change = None if prev == 0 else round((cur - prev) * 100 / prev)  # nothing to compare with -> no percentage
    return cur, change


def pairs(model, field, choices, qs=None):
    """[{label, value, colour}] for every choice of a field (zero included)."""
    found = dict((qs if qs is not None else model.objects).values_list(field).annotate(n=Count('id')))
    return [{'label': label, 'value': found.get(key, 0), 'color': STATUS_COLOURS.get(key)} for key, label in choices]


def day_labels(days):
    return [d.strftime('%d %b').lstrip('0') for d in days]


# ---------- Dashboard: what needs the admin's attention ----------

@staff_only
def admin_dashboard(request):
    today = timezone.localdate()
    days = [today - timedelta(days=i) for i in range(13, -1, -1)]
    pending = Membership.objects.filter(status='pending').select_related('user', 'community').order_by('joined_at')
    community_requests = CommunityRequest.objects.filter(status='pending').select_related('user').order_by('created_at')
    open_reports = Report.objects.filter(status='open').select_related('reporter', 'community', 'listing', 'lost_item')
    n_pending, n_requests, n_reports = pending.count(), community_requests.count(), open_reports.count()

    kpis = [
        ('Users', User.objects.count(), 'c1', 'users'),
        ('Communities', Community.objects.count(), 'c6', 'building'),
        ('Active listings', Listing.objects.filter(status='available').count(), 'c4', 'tag'),
        ('Active borrows', BorrowRequest.objects.filter(status='approved').count(), 'c5', 'repeat'),
        ('Waiting for approval', n_pending + n_requests, 'c2', 'clock'),
        ('Open reports', n_reports, 'c3', 'flag'),
    ]
    return render(request, 'communities/admin_dashboard.html', {
        'kpis': kpis,
        'growth': {'labels': day_labels(days),
                   'series': [{'name': 'New users', 'color': PALETTE[0], 'data': daily_counts(User.objects.all(), 'date_joined', days)},
                              {'name': 'New listings', 'color': PALETTE[1], 'data': daily_counts(Listing.objects.all(), 'created_at', days)}]},
        'pending': pending[:8], 'n_pending': n_pending,
        'community_requests': community_requests[:5], 'n_requests': n_requests,
        'open_reports': open_reports[:5], 'n_reports': n_reports,
        'recent_listings': Listing.objects.select_related('seller', 'community').order_by('-created_at')[:4],
        'recent_lost': LostFoundItem.objects.select_related('user', 'community').order_by('-created_at')[:2],
    })


# ---------- Reports: graphs ----------

@staff_only
def admin_reports(request):
    try:
        span = int(request.GET.get('days', 30))
    except ValueError:
        span = 30
    if span not in (7, 30, 90):
        span = 30
    today = timezone.localdate()
    days = [today - timedelta(days=i) for i in range(span - 1, -1, -1)]

    def kpi(label, qs, field, icon, colour, total=None, sub='new'):
        cur, change = period_stat(qs, field, span)
        return {'label': label, 'value': total if total is not None else cur, 'sub': '%s %s in %d days' % (cur, sub, span),
                'change': change, 'icon': icon, 'colour': colour}

    sales = Order.objects.filter(status='confirmed').aggregate(t=Sum('amount'))['t'] or 0
    kpis = [
        kpi('Users', User.objects.all(), 'date_joined', 'users', 'c1', total=User.objects.count()),
        kpi('Listings', Listing.objects.all(), 'created_at', 'tag', 'c6', total=Listing.objects.count()),
        kpi('Orders', Order.objects.all(), 'created_at', 'bag', 'c5', total=Order.objects.count()),
        kpi('Borrow requests', BorrowRequest.objects.all(), 'requested_at', 'repeat', 'c2', total=BorrowRequest.objects.count()),
        {'label': 'Confirmed sales', 'value': '₹{:,.0f}'.format(sales), 'sub': 'all time', 'change': None, 'icon': 'trend', 'colour': 'c4'},
    ]

    members = Community.objects.annotate(n=Count('membership', filter=Q(membership__status='approved'))).order_by('-n', 'name')[:8]
    activity = Community.objects.annotate(
        members=Count('membership', filter=Q(membership__status='approved'), distinct=True),
        listings=Count('listing', distinct=True),
        lost=Count('lostfounditem', filter=Q(lostfounditem__status='open'), distinct=True),
    ).order_by('-listings', '-members')[:8]
    sellers = Listing.objects.values('seller__username').annotate(n=Count('id')).order_by('-n')[:6]

    charts = {
        'growth': {'labels': day_labels(days), 'series': [
            {'name': 'New users', 'color': PALETTE[0], 'data': daily_counts(User.objects.all(), 'date_joined', days)},
            {'name': 'New listings', 'color': PALETTE[1], 'data': daily_counts(Listing.objects.all(), 'created_at', days)},
            {'name': 'Orders', 'color': PALETTE[2], 'data': daily_counts(Order.objects.all(), 'created_at', days)},
            {'name': 'Borrow requests', 'color': PALETTE[3], 'data': daily_counts(BorrowRequest.objects.all(), 'requested_at', days)}]},
        'members': [{'label': c.name, 'value': c.n} for c in members],
        'categories': pairs(Listing, 'category', Listing.CATEGORIES),
        'types': pairs(Listing, 'listing_type', Listing.LISTING_TYPES),
        'membership': pairs(Membership, 'status', Membership.STATUS_CHOICES),
        'borrow': pairs(BorrowRequest, 'status', BorrowRequest.STATUS_CHOICES),
        'orders': pairs(Order, 'status', Order.STATUS_CHOICES),
        'lostfound': pairs(LostFoundItem, 'item_type', LostFoundItem.ITEM_TYPES),
        'reports': pairs(Report, 'status', Report.STATUS_CHOICES),
    }
    return render(request, 'communities/admin_reports.html', {
        'kpis': kpis, 'charts': charts, 'span': span, 'activity': activity, 'sellers': sellers,
        'generated': timezone.localtime(), 'ranges': (7, 30, 90),
    })


# ---------- Communities list ----------

@staff_only
def admin_communities(request):
    search = request.GET.get('search', '').strip()
    communities = Community.objects.annotate(
        members=Count('membership', filter=Q(membership__status='approved'), distinct=True),
        pending=Count('membership', filter=Q(membership__status='pending'), distinct=True),
        listings=Count('listing', distinct=True),
        open_lf=Count('lostfounditem', filter=Q(lostfounditem__status='open'), distinct=True),
    ).order_by('name')
    if search:
        communities = communities.filter(Q(name__icontains=search) | Q(location__icontains=search))
    return render(request, 'communities/admin_communities.html', {'communities': communities, 'search': search})
