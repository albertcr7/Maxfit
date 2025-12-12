from django.urls import path
from . import views

app_name = 'booking'

urlpatterns = [
    path('', views.home, name='home'),
    path('book/', views.book_turf, name='book'),
    path('my-bookings/', views.my_bookings, name='my_bookings'),
    path('register/', views.register_view, name='register'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('cancel/<int:booking_id>/', views.cancel_booking, name='cancel_booking'),

]
