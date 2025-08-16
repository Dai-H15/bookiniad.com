from django.urls import path
from main import views

urlpatterns = [
    path('', views.index, name="index"),
    path('search/', views.search_results, name="search_results"),
    path('accommodations/', views.accommodation_search, name="accommodation_search"),
    path('flights/', views.flight_search, name="flight_search"),
    path('booking/create/', views.create_booking, name="create_booking"),
    path('ai-comparison/', views.ai_comparison, name="ai_comparison"),
    path('chat/<str:system_type>/', views.chat_interface, name="chat_interface"),
    path('api/chat/', views.chat_message, name="chat_message"),
    path('performance/', views.performance_analysis, name="performance_analysis"),
]
