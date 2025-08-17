from django.urls import path
from main import views

urlpatterns = [
    path('', views.index, name="index"),
    path('search/', views.search_results, name="search_results"),
    path('accommodations/', views.accommodation_search, name="accommodation_search"),
    path('flights/', views.flight_search, name="flight_search"),
    path('booking/create/', views.create_booking_from_cart, name="create_booking"),
    path('booking/inquiry/', views.booking_inquiry, name="booking_inquiry"),
    path('ai-comparison/', views.ai_comparison, name="ai_comparison"),
    path('chat/<str:system_type>/', views.chat_interface, name="chat_interface"),
    path('api/chat/', views.chat_message, name="chat_message"),
    path('api/conversation/history/', views.get_conversation_history, name="get_conversation_history"),
    path('api/conversation/clear/', views.clear_conversation_history, name="clear_conversation_history"),
    path('performance/', views.performance_analysis, name="performance_analysis"),
    
    # カート機能
    path('cart/', views.cart, name="cart"),
    path('api/cart/add-flight/', views.add_flight_to_cart, name="add_flight_to_cart"),
    path('api/cart/add-accommodation/', views.add_accommodation_to_cart, name="add_accommodation_to_cart"),
    path('api/cart/remove/', views.remove_from_cart, name="remove_from_cart"),
    path('api/cart/clear/', views.clear_cart, name="clear_cart"),
    path('booking/from-cart/', views.create_booking_from_cart, name="create_booking_from_cart"),
    
    # 予約完了
    path('booking-complete/', views.booking_complete, name="booking_complete"),
]
