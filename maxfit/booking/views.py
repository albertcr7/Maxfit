from datetime import datetime, date, timedelta
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.auth.models import User
from django.conf import settings

from .models import TimeSlot, Booking, UserProfile
from twilio.rest import Client


# ---------------------------
# HOME PAGE
# ---------------------------
def home(request):
    turf_details = {
        "name": "MaxFit Premium Turf",
        "price_per_hour": 800,
        "location": "MaxFit Arena",
        "opening_hours": "5:00 AM – 11:00 PM",
        "features": [
            "High-quality artificial grass",
            "LED flood lights",
            "Ample parking space",
            "Drinking water",
            "Changing room & washroom"
        ]
    }
    return render(request, 'booking/home.html', {"turf": turf_details})


# ---------------------------
# BOOK TURF PAGE
# ---------------------------
@login_required
def book_turf(request):
    time_slots = TimeSlot.objects.all().order_by('start_time')

    # ➤ Default selected date = TODAY
    selected_date = request.GET.get('date')
    if not selected_date:
        selected_date = date.today().strftime("%Y-%m-%d")

    selected_date_obj = datetime.strptime(selected_date, "%Y-%m-%d").date()

    # ➤ Fetch booked slots for this date
    booked_slot_ids = Booking.objects.filter(
        date=selected_date_obj,
        status='CONFIRMED'
    ).values_list('timeslot_id', flat=True)

    # ➤ CURRENT TIME (for disabling past slots)
    current_time = datetime.now().time()

    # ----------------------
    # HANDLE BOOKING SUBMIT
    # ----------------------
    if request.method == 'POST':
        timeslot_id = request.POST.get('timeslot')

        if not timeslot_id:
            messages.error(request, "Please select a time slot.")
            return redirect(f"/book/?date={selected_date}")

        slot = get_object_or_404(TimeSlot, id=timeslot_id)

        # ❌ Prevent booking past time on today
        if selected_date_obj == date.today() and slot.end_time <= current_time:
            messages.error(request, "This slot time has already passed.")
            return redirect(f"/book/?date={selected_date}")

        # ❌ Prevent double booking
        if Booking.objects.filter(date=selected_date_obj, timeslot=slot, status='CONFIRMED').exists():
            messages.error(request, "This slot is already booked.")
            return redirect(f"/book/?date={selected_date}")

        # ✔ Create booking
        new_booking = Booking.objects.create(
            user=request.user,
            date=selected_date_obj,
            timeslot=slot,
            status='CONFIRMED'
        )

        # --------------------------
        # SEND ADMIN SMS
        # --------------------------
        try:
            client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
            profile = UserProfile.objects.get(user=request.user)

            msg = (
                f"New Booking ✔\n"
                f"User: {request.user.username}\n"
                f"Phone: {profile.phone}\n"
                f"Date: {new_booking.date}\n"
                f"Time: {new_booking.timeslot}"
            )

            client.messages.create(
                body=msg,
                from_=settings.TWILIO_PHONE_NUMBER,
                to=settings.ADMIN_PHONE_NUMBER
            )

        except Exception as e:
            print("SMS Failed:", e)

        messages.success(request, "Your booking is confirmed!")
        return redirect('booking:my_bookings')

    # ----------------------
    # RENDER TEMPLATE
    # ----------------------
    return render(request, 'booking/book_turf.html', {
        "time_slots": time_slots,
        "today": date.today(),
        "selected_date": selected_date,
        "booked_slot_ids": booked_slot_ids,
        "now": current_time,   # <-- IMPORTANT
    })


    return render(request, 'booking/book_turf.html', {
        "time_slots": time_slots,
        "today": date.today(),
        "booked_slot_ids": booked_slot_ids
    })


# ---------------------------
# USER BOOKINGS PAGE
# ---------------------------
@login_required
def my_bookings(request):
    bookings = Booking.objects.filter(user=request.user).order_by('-date', '-created_at')
    return render(request, 'booking/my_bookings.html', {"bookings": bookings})


# ---------------------------
# CANCEL BOOKING
# ---------------------------
@login_required
def cancel_booking(request, booking_id):
    booking = get_object_or_404(Booking, id=booking_id, user=request.user)

    if booking.status == "CANCELLED":
        messages.error(request, "This booking is already cancelled.")
        return redirect('booking:my_bookings')

    now = datetime.now()
    booking_start = datetime.combine(booking.date, booking.timeslot.start_time)

    # ❗ Allow cancellation only before 1 hour
    if booking_start - now < timedelta(hours=1):
        messages.error(request, "You can cancel only 1 hour before the slot time.")
        return redirect('booking:my_bookings')

    booking.status = "CANCELLED"
    booking.save()

    # --------------------------
    # 📲 SMS ADMIN ON CANCEL
    # --------------------------
    try:
        client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
        profile = UserProfile.objects.get(user=request.user)

        sms_msg = (
            f"Booking Cancelled ❌\n"
            f"User: {request.user.username}\n"
            f"Phone: {profile.phone}\n"
            f"Date: {booking.date}\n"
            f"Time: {booking.timeslot}"
        )

        client.messages.create(
            body=sms_msg,
            from_=settings.TWILIO_PHONE_NUMBER,
            to=settings.ADMIN_PHONE_NUMBER
        )
    except Exception as e:
        print("Cancel SMS failed:", e)

    messages.success(request, "Booking cancelled successfully.")
    return redirect('booking:my_bookings')


# ---------------------------
# REGISTER USER
# ---------------------------
def register_view(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        phone = request.POST.get('phone')
        email = request.POST.get('email')
        p1 = request.POST.get('password1')
        p2 = request.POST.get('password2')

        if p1 != p2:
            messages.error(request, "Passwords do not match.")
            return redirect('booking:register')

        if UserProfile.objects.filter(phone=phone).exists():
            messages.error(request, "Phone number already registered!")
            return redirect('booking:register')

        # Create user
        user = User.objects.create_user(username=username, email=email, password=p1)

        # Save phone number in profile
        UserProfile.objects.create(user=user, phone=phone)

        messages.success(request, "Account created successfully! Please login.")
        return redirect('booking:login')

    return render(request, 'booking/register.html')


# ---------------------------
# LOGIN USER (PHONE LOGIN)
# ---------------------------
def login_view(request):
    if request.method == 'POST':
        phone = request.POST.get('phone')
        password = request.POST.get('password')

        try:
            profile = UserProfile.objects.get(phone=phone)
            user = profile.user
        except UserProfile.DoesNotExist:
            messages.error(request, "Phone number not found.")
            return redirect('booking:login')

        user_auth = authenticate(request, username=user.username, password=password)

        if user_auth is not None:
            login(request, user_auth)
            return redirect('booking:home')
        else:
            messages.error(request, "Incorrect password.")
            return redirect('booking:login')

    return render(request, 'booking/login.html')


# ---------------------------
# LOGOUT
# ---------------------------
def logout_view(request):
    logout(request)
    return redirect('booking:home')
