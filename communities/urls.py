from django.urls import path
from . import views, views_shop, views_admin

urlpatterns = [
    path('staff/dashboard/', views_admin.admin_dashboard, name='admin_dashboard'),
    path('staff/reports/', views_admin.admin_reports, name='admin_reports'),
    path('staff/communities/', views_admin.admin_communities, name='admin_communities'),
    path('staff/membership/<int:membership_id>/decide/', views.decide_membership, name='decide_membership'),
    path('communities/', views.community_list, name='community_list'),
    path('communities/join/<int:community_id>/', views.join_community, name='join_community'),
    path('communities/<int:community_id>/', views.community_detail, name='community_detail'),

    path('communities/<int:community_id>/marketplace/', views.marketplace, name='marketplace'),
    path('communities/<int:community_id>/marketplace/add/', views.add_listing, name='add_listing'),
    path('my-listings/', views.my_listings, name='my_listings'),
    path('listings/<int:listing_id>/edit/', views.edit_listing, name='edit_listing'),
    path('listings/<int:listing_id>/delete/', views.delete_listing, name='delete_listing'),
    path('listings/<int:listing_id>/status/', views.set_listing_status, name='set_listing_status'),
    path('borrow/<int:listing_id>/', views.borrow_item, name='borrow_item'),

    path('borrow-requests/', views.borrow_requests, name='borrow_requests'),
    path('borrow-requests/<int:request_id>/update/', views.update_borrow_request, name='update_borrow_request'),

    path('communities/<int:community_id>/lost-found/', views.lost_found_list, name='lost_found_list'),
    path('communities/<int:community_id>/lost-found/add/', views.add_lost_found, name='add_lost_found'),
    path('lost-found/<int:item_id>/resolve/', views.resolve_lost_found, name='resolve_lost_found'),

    path('communities/<int:community_id>/notices/', views.notice_list, name='notice_list'),
    path('communities/<int:community_id>/notices/add/', views.add_notice, name='add_notice'),

    path('notifications/', views.notification_list, name='notification_list'),
    path('notifications/read-all/', views.mark_all_notifications_read, name='mark_all_notifications_read'),
    path('notifications/<int:notification_id>/read/', views.mark_notification_read, name='mark_notification_read'),

    path('dashboard/', views.my_communities, name='my_communities'),
    path('communities/request/', views.request_community, name='request_community'),
    path('staff/community-request/<int:request_id>/decide/', views.decide_community_request, name='decide_community_request'),
    path('staff/export/memberships.csv', views.export_memberships_csv, name='export_memberships_csv'),
    path('communities/<int:community_id>/manage/', views.manage_community, name='manage_community'),
    path('members/<int:membership_id>/role/', views.set_member_role, name='set_member_role'),
    path('members/<int:membership_id>/remove/', views.remove_member, name='remove_member'),
    path('notices/<int:notice_id>/action/', views.notice_action, name='notice_action'),
    path('report/<str:kind>/<int:object_id>/', views.report_content, name='report_content'),
    path('reports/<int:report_id>/resolve/', views.resolve_report, name='resolve_report'),

    path('shop/', views_shop.shop, name='shop'),
    path('buy/<int:listing_id>/', views_shop.buy_item, name='buy_item'),
    path('orders/', views_shop.my_orders, name='my_orders'),
    path('orders/<int:order_id>/', views_shop.order_detail, name='order_detail'),
    path('orders/<int:order_id>/action/', views_shop.order_action, name='order_action'),
    path('profile/', views_shop.profile_edit, name='profile_edit'),
    path('chat/start/<int:listing_id>/', views_shop.start_chat, name='start_chat'),
    path('inbox/', views_shop.inbox, name='inbox'),
    path('chat/<int:convo_id>/', views_shop.chat, name='chat'),
]
