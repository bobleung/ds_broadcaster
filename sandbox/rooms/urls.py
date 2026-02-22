from django.urls import path
from . import views

urlpatterns = [
    path('', views.room_list, name='room_list'),
    path('<int:pk>/', views.room_detail, name='room_detail'),
    path('create/', views.room_create, name='room_create'),
    path('<int:pk>/edit/', views.room_edit, name='room_edit'),
    path('<int:pk>/delete/', views.room_delete, name='room_delete'),
    path('<int:pk>/connect/', views.room_connect, name='room_connect'),
    path('<int:pk>/send/', views.room_send_message, name='room_send_message'),
    path('<int:pk>/cursor/', views.room_cursor, name='room_cursor'),
]
