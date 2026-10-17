from django.shortcuts import render


def dashboard(request):
    """Render the educational Reserve Juggler overview dashboard."""
    return render(request, "main/dashboard.html")


def intro(request):
    """Render the landing page that introduces the Reserve Juggler sandbox."""
    return render(request, "main/intro.html")
