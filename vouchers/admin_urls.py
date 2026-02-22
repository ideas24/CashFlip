from django.urls import path
from vouchers import views

urlpatterns = [
    path('stats/', views.admin_voucher_stats, name='voucher-admin-stats'),
    path('list/', views.admin_voucher_list, name='voucher-admin-list'),
    path('create/', views.admin_voucher_create, name='voucher-admin-create'),
    path('<uuid:voucher_id>/disable/', views.admin_voucher_disable, name='voucher-admin-disable'),
    path('batches/', views.admin_batch_list, name='voucher-admin-batches'),
    path('batches/create/', views.admin_batch_create, name='voucher-admin-batch-create'),
]
