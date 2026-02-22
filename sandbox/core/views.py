import time
from django.shortcuts import render, redirect
from django.contrib.auth import login, update_session_auth_hash
from django.http import HttpResponse, StreamingHttpResponse
from .forms import SignupForm, ProfileForm, ChangePasswordForm
from django.contrib import messages


def home(request):
    return render(request, 'core/home.html')

def signup(request):
    if request.method == 'POST':
        form = SignupForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect('home')
    else:
        form = SignupForm()

    return render(request, 'core/signup.html', {'form': form})

def profile(request):
    if request.method == 'POST':
        form = ProfileForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            return redirect('profile')
    else:
        form = ProfileForm(instance=request.user)

    password_form = ChangePasswordForm(user=request.user)
    return render(request, 'core/profile.html', {'form': form, 'password_form': password_form})

def change_password(request):
    if request.method == 'POST':
        password_form = ChangePasswordForm(request.POST, user=request.user)
        if password_form.is_valid():
            request.user.set_password(password_form.cleaned_data['new_password'])
            request.user.save()
            update_session_auth_hash(request, request.user)
            messages.success(request, 'Password changed successfully!')
            return redirect('profile')
        form = ProfileForm(instance=request.user)
        return render(request, 'core/profile.html', {'form': form, 'password_form': password_form})
    return redirect('profile')

def toast_test(request):
    return render(request, 'core/toast_test.html')

async def toast_test_sse(request):
    async def event_stream():
        toast_id = f"toast-{int(time.time() * 1000)}"
        fragment = (
            f'<div id="{toast_id}" class="autodismiss">'
            '<div class="alert alert-success">'
            '<span>This toast arrived via Datastar SSE!</span>'
            '</div></div>'
        )
        yield f"event: datastar-patch-elements\ndata: mode append\ndata: selector #toast-area\ndata: elements {fragment}\n\n"

    return StreamingHttpResponse(event_stream(), content_type='text/event-stream')

def toast_test_html(request):
    toast_id = f"toast-{int(time.time() * 1000)}"
    fragment = (
        f'<div id="{toast_id}" class="autodismiss">'
        '<div class="alert alert-info">'
        '<span>This toast arrived via HTML response!</span>'
        '</div></div>'
    )
    response = HttpResponse(fragment, content_type='text/html')
    response['Datastar-Selector'] = '#toast-area'
    response['Datastar-Mode'] = 'append'
    return response
