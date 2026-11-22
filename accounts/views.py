from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.forms import UserCreationForm
from django.shortcuts import render, redirect
from django.utils.http import url_has_allowed_host_and_scheme


def register(request):
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect('my_communities')
    else:
        form = UserCreationForm()
    return render(request, 'accounts/register.html', {'form': form})


def user_login(request):
    next_url = request.POST.get('next') or request.GET.get('next', '')
    if request.method == 'POST':
        user = authenticate(request, username=request.POST.get('username'), password=request.POST.get('password'))
        if user is not None:
            login(request, user)
            if next_url and url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}):
                return redirect(next_url)
            if user.is_staff:
                return redirect('admin_dashboard')
            return redirect('shop')
        return render(request, 'accounts/login.html', {'error': 'Invalid username or password.', 'next': next_url})
    return render(request, 'accounts/login.html', {'next': next_url})


def user_logout(request):
    logout(request)
    return redirect('login')
