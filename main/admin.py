from django.contrib import admin
from django.utils.html import format_html
from .models import (
    Accommodations, Air, Booking, TravelPackage, StayTemplate,
    ChatSession, ChatMessage, SearchCondition,
    PerformanceMetrics, SystemResponse
)


# 宿泊施設管理
@admin.register(Accommodations)
class AccommodationsAdmin(admin.ModelAdmin):
    list_display = ['name', 'rank', 'location', 'amenities_count', 'has_image']
    list_filter = ['rank', 'location']
    search_fields = ['name', 'location', 'description']
    ordering = ['rank', 'name']
    
    fieldsets = (
        ('基本情報', {
            'fields': ('name', 'rank', 'location')
        }),
        ('詳細情報', {
            'fields': ('description', 'amenities', 'image_url'),
            'classes': ('collapse',)
        }),
    )
    
    def amenities_count(self, obj):
        if obj.amenities:
            return len(obj.amenities)
        return 0
    amenities_count.short_description = '設備数'
    
    def has_image(self, obj):
        if obj.image_url:
            return format_html('<span style="color: green;">✓</span>')
        return format_html('<span style="color: red;">✗</span>')
    has_image.short_description = '画像'


# 航空券管理
@admin.register(Air)
class AirAdmin(admin.ModelAdmin):
    list_display = ['flight_number', 'name', 'route', 'departure_time', 'fee', 'available_seats', 'flight_type']
    list_filter = ['flight_type', 'name', 'place_from', 'place_to']
    search_fields = ['flight_number', 'name', 'place_from', 'place_to']
    ordering = ['departure_time']
    date_hierarchy = 'departure_time'
    
    fieldsets = (
        ('航空会社情報', {
            'fields': ('name', 'flight_number', 'flight_type')
        }),
        ('路線情報', {
            'fields': ('place_from', 'place_to', 'departure_time', 'arrival_time')
        }),
        ('料金・座席', {
            'fields': ('fee', 'available_seats')
        }),
    )
    
    def route(self, obj):
        return f"{obj.place_from} → {obj.place_to}"
    route.short_description = '路線'


# 旅行パッケージ管理
@admin.register(TravelPackage)
class TravelPackageAdmin(admin.ModelAdmin):
    list_display = ['name', 'accommodation_name', 'route', 'stay_duration', 'total_price', 'is_available']
    list_filter = ['is_available', 'stay_duration', 'accommodation__location']
    search_fields = ['name', 'description', 'accommodation__name']
    ordering = ['total_price']
    raw_id_fields = ['outbound_flight', 'return_flight', 'accommodation']
    
    fieldsets = (
        ('パッケージ基本情報', {
            'fields': ('name', 'description', 'is_available')
        }),
        ('航空券', {
            'fields': ('outbound_flight', 'return_flight')
        }),
        ('宿泊', {
            'fields': ('accommodation', 'stay_duration')
        }),
        ('料金', {
            'fields': ('total_price',)
        }),
    )
    
    def accommodation_name(self, obj):
        return obj.accommodation.name
    accommodation_name.short_description = '宿泊施設'
    
    def route(self, obj):
        route = f"{obj.outbound_flight.place_from} → {obj.outbound_flight.place_to}"
        if obj.return_flight:
            route += " (往復)"
        return route
    route.short_description = '路線'


# 予約管理
@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = ['reservation_number', 'accommodation_name', 'from_date', 'to_date', 'num_of_people', 'total_fee']
    list_filter = ['from_date', 'accommodations__location', 'num_of_people']
    search_fields = ['reservation_number', 'accommodations__name', 'place']
    ordering = ['-from_date']
    date_hierarchy = 'from_date'
    readonly_fields = ['reservation_number']
    
    def accommodation_name(self, obj):
        return obj.accommodations.name
    accommodation_name.short_description = '宿泊施設'


# 宿泊テンプレート管理
@admin.register(StayTemplate)
class StayTemplateAdmin(admin.ModelAdmin):
    list_display = ['max_num_of_people', 'fee_per_people', 'discount_rate', 'date']
    list_filter = ['max_num_of_people', 'date']
    ordering = ['-date']


# チャットセッション管理
@admin.register(ChatSession)
class ChatSessionAdmin(admin.ModelAdmin):
    list_display = ['session_id_short', 'session_type', 'created_at', 'is_active', 'message_count']
    list_filter = ['session_type', 'is_active', 'created_at']
    search_fields = ['session_id']
    ordering = ['-created_at']
    readonly_fields = ['session_id', 'created_at']
    
    def session_id_short(self, obj):
        return obj.session_id[:8] + '...'
    session_id_short.short_description = 'セッションID'
    
    def message_count(self, obj):
        return obj.messages.count()
    message_count.short_description = 'メッセージ数'


# チャットメッセージ管理
@admin.register(ChatMessage)
class ChatMessageAdmin(admin.ModelAdmin):
    list_display = ['session_short', 'message_type', 'content_preview', 'timestamp']
    list_filter = ['message_type', 'timestamp', 'session__session_type']
    search_fields = ['content', 'session__session_id']
    ordering = ['-timestamp']
    readonly_fields = ['timestamp']
    raw_id_fields = ['session']
    
    def session_short(self, obj):
        return obj.session.session_id[:8] + '...'
    session_short.short_description = 'セッション'
    
    def content_preview(self, obj):
        return obj.content[:50] + '...' if len(obj.content) > 50 else obj.content
    content_preview.short_description = 'メッセージ内容'


# パフォーマンス指標管理
@admin.register(PerformanceMetrics)
class PerformanceMetricsAdmin(admin.ModelAdmin):
    list_display = ['session_short', 'session_type', 'response_time', 'successful_booking', 'user_satisfaction', 'created_at']
    list_filter = ['session__session_type', 'successful_booking', 'user_satisfaction', 'created_at']
    ordering = ['-created_at']
    readonly_fields = ['created_at']
    raw_id_fields = ['session']
    
    def session_short(self, obj):
        return obj.session.session_id[:8] + '...'
    session_short.short_description = 'セッション'
    
    def session_type(self, obj):
        return obj.session.get_session_type_display()
    session_type.short_description = 'システムタイプ'


# システム応答管理
@admin.register(SystemResponse)
class SystemResponseAdmin(admin.ModelAdmin):
    list_display = ['session_short', 'intent_detected', 'confidence_score', 'processing_time', 'timestamp']
    list_filter = ['intent_detected', 'session__session_type', 'timestamp']
    search_fields = ['intent_detected', 'response_generated']
    ordering = ['-timestamp']
    readonly_fields = ['timestamp']
    raw_id_fields = ['session']
    
    def session_short(self, obj):
        return obj.session.session_id[:8] + '...'
    session_short.short_description = 'セッション'


# 検索条件管理
@admin.register(SearchCondition)
class SearchConditionAdmin(admin.ModelAdmin):
    list_display = ['session_short', 'departure_place', 'destination_place', 'departure_date', 'num_of_people', 'created_at']
    list_filter = ['departure_place', 'destination_place', 'departure_date', 'created_at']
    search_fields = ['departure_place', 'destination_place']
    ordering = ['-created_at']
    readonly_fields = ['created_at']
    raw_id_fields = ['session']
    
    def session_short(self, obj):
        return obj.session.session_id[:8] + '...'
    session_short.short_description = 'セッション'


# 管理サイトのカスタマイズ
admin.site.site_header = 'bookiniad.com 管理サイト'
admin.site.site_title = 'bookiniad.com Admin'
admin.site.index_title = 'AI予約比較サイト管理'
