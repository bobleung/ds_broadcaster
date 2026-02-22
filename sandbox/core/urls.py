from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('login/', auth_views.LoginView.as_view(template_name='core/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('signup/', views.signup, name='signup'),
    path('profile/', views.profile, name='profile'),
    path('profile/change-password/', views.change_password, name='change_password'),
    path('toast-test/', views.toast_test, name='toast_test'),
    path('toast-test/sse/', views.toast_test_sse, name='toast_test_sse'),
    path('toast-test/html/', views.toast_test_html, name='toast_test_html'),
]
