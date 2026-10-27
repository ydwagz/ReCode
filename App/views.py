from django.shortcuts import render

def home(request):
    context= {}
    return render(request, 'home.html')

def dashboard(request):
    context= {}
    return render(request, 'dashboard.html')

def profile(request):
    context= {}
    return render(request, 'profile.html')

def recode(request):
    context= {}
    return render(request, 'recode.html')


def register(request):
    context= {}
    return render(request, 'register.html')

def login(request):
    context= {}
    return render(request, 'login.html')

def settings(request):
    context= {}
    return render(request, 'settings.html')