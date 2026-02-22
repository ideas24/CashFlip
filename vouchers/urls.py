from django.urls import path
from vouchers import views

urlpatterns = [
    # Public
    path('redeem/', views.redeem_voucher, name='voucher-redeem'),
    # Admin
    path('admin/stats/', views.admin_voucher_stats, name='voucher-admin-stats'),
    path('admin/list/', views.admin_voucher_list, name='voucher-admin-list'),
    path('admin/create/', views.admin_voucher_create, name='voucher-admin-create'),
    path('admin/<uuid:voucher_id>/disable/', views.admin_voucher_disable, name='voucher-admin-disable'),
    path('admin/batches/', views.admin_batch_list, name='voucher-admin-batches'),
    path('admin/batches/create/', views.admin_batch_create, name='voucher-admin-batch-create'),
]
