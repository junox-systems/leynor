from django.shortcuts import redirect


def home(request):
    """No marketing page: the app is private. Send people where they work."""
    if request.user.is_authenticated:
        return redirect("dashboard")
    return redirect("account_login")
