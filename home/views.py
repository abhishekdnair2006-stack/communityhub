from django.shortcuts import render, redirect


def home(request):
    if request.user.is_authenticated and request.user.is_staff:
        return redirect('admin_dashboard')  # admins live in the dashboard
    my_communities = []
    if request.user.is_authenticated:
        from communities.models import Membership
        my_communities = Membership.objects.filter(user=request.user, status='approved').select_related('community')
    return render(request, 'home/home.html', {'my_communities': my_communities})
