from django.contrib import admin
from .models import (Profile, Order, Conversation, Message, Community, Membership, Listing, BorrowRequest, LostFoundItem, Notice, Notification,
                     CommunityRequest, Report)


@admin.register(Community)
class CommunityAdmin(admin.ModelAdmin):
    list_display = ('name', 'community_type', 'location', 'created_at')
    search_fields = ('name', 'location')
    list_filter = ('community_type',)
    ordering = ('name',)


@admin.register(Membership)
class MembershipAdmin(admin.ModelAdmin):
    list_display = ('user', 'community', 'status', 'role', 'joined_at')
    list_filter = ('status', 'role', 'community')
    list_editable = ('role',)
    search_fields = ('user__username', 'community__name')
    ordering = ('-joined_at',)
    actions = ['approve_requests', 'reject_requests']

    def _decide(self, request, queryset, status):
        for m in queryset:
            m.status = status
            m.save(update_fields=['status'])
            Notification.objects.create(
                user=m.user, message=f"Your request to join {m.community.name} was {status}.")
        self.message_user(request, f"{queryset.count()} request(s) {status}.")

    @admin.action(description='Approve selected membership requests')
    def approve_requests(self, request, queryset):
        self._decide(request, queryset, 'approved')

    @admin.action(description='Reject selected membership requests')
    def reject_requests(self, request, queryset):
        self._decide(request, queryset, 'rejected')


@admin.register(Listing)
class ListingAdmin(admin.ModelAdmin):
    list_display = ('title', 'seller', 'community', 'listing_type', 'category', 'price', 'status', 'created_at')
    list_filter = ('listing_type', 'category', 'status', 'community')
    search_fields = ('title', 'description', 'seller__username')
    list_editable = ('status',)
    ordering = ('-created_at',)


@admin.register(BorrowRequest)
class BorrowRequestAdmin(admin.ModelAdmin):
    list_display = ('listing', 'borrower', 'return_date', 'status', 'requested_at')
    list_filter = ('status',)
    search_fields = ('listing__title', 'borrower__username')
    readonly_fields = ('requested_at',)
    ordering = ('-requested_at',)


@admin.register(LostFoundItem)
class LostFoundItemAdmin(admin.ModelAdmin):
    list_display = ('title', 'item_type', 'user', 'community', 'status', 'created_at')
    list_filter = ('item_type', 'status', 'community')
    search_fields = ('title', 'description', 'user__username')
    ordering = ('-created_at',)


@admin.register(Notice)
class NoticeAdmin(admin.ModelAdmin):
    list_display = ('title', 'community', 'notice_type', 'created_by', 'is_pinned', 'created_at')
    list_filter = ('notice_type', 'community', 'is_pinned')
    search_fields = ('title', 'content')
    list_editable = ('is_pinned',)
    ordering = ('-is_pinned', '-created_at')


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('user', 'message', 'is_read', 'created_at')
    list_filter = ('is_read',)
    search_fields = ('user__username', 'message')
    readonly_fields = ('created_at',)
    ordering = ('-created_at',)


@admin.register(CommunityRequest)
class CommunityRequestAdmin(admin.ModelAdmin):
    list_display = ('name', 'community_type', 'location', 'user', 'status', 'created_at')
    list_filter = ('status', 'community_type')
    search_fields = ('name', 'location', 'user__username')
    ordering = ('-created_at',)


@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    list_display = ('reporter', 'community', 'listing', 'lost_item', 'status', 'created_at')
    list_filter = ('status', 'community')
    search_fields = ('reason', 'reporter__username')
    ordering = ('-created_at',)


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'phone', 'upi_id')
    search_fields = ('user__username', 'phone', 'upi_id')


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('id', 'listing', 'buyer', 'amount', 'method', 'status', 'created_at')
    list_filter = ('status', 'method')
    search_fields = ('listing__title', 'buyer__username', 'upi_ref')


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ('starter', 'other', 'listing', 'status', 'updated_at')
    list_filter = ('status',)


admin.site.register(Message)
