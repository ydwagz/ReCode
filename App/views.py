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

def leaderboard(request):
    players = [{"name": "Luca", "score": 100}, {"name": "Nia", "score": 50}, {"name": "Tamara", "score": 78}, {"name": "Dave", "score": 89}, {"name": "George", "score": 31}, {"name": "Matthew", "score": 45}, {"name": "emma", "score": 87}, {"name": "Oliver", "score": 92}, {"name": "Sophia", "score": 64}, {"name": "Noah", "score": 73}, {"name": "Mia", "score": 56}, {"name": "Ethan", "score": 81}, {"name": "Isabella", "score": 95}, {"name": "James", "score": 42}, {"name": "Amelia", "score": 68}, {"name": "Benjamin", "score": 37}, {"name": "Charlotte", "score": 88}, {"name": "Lucas", "score": 76}, {"name": "Harper", "score": 53}, {"name": "Henry", "score": 99}, {"name": "Ava", "score": 61}, {"name": "Alexander", "score": 84}, {"name": "Ella", "score": 47}, {"name": "Daniel", "score": 70}, {"name": "Grace", "score": 91}, {"name": "Michael", "score": 34}, {"name": "Chloe", "score": 79}, {"name": "William", "score": 58}, {"name": "Lily", "score": 96}, {"name": "Jack", "score": 44}, {"name": "Zoe", "score": 67}, {"name": "Samuel", "score": 82}, {"name": "Emily", "score": 39}, {"name": "David", "score": 74}, {"name": "Aria", "score": 90}, {"name": "Joseph", "score": 52}, {"name": "Scarlett", "score": 86}, {"name": "Leo", "score": 63}, {"name": "Victoria", "score": 97}, {"name": "Gabriel", "score": 41}, {"name": "Hannah", "score": 72}, {"name": "Ryan", "score": 55}, {"name": "Layla", "score": 93}, {"name": "Nathan", "score": 48}, {"name": "Sofia", "score": 80}, {"name": "Andrew", "score": 35}, {"name": "Maya", "score": 66}, {"name": "Christopher", "score": 85}, {"name": "Eva", "score": 59}, {"name": "Dylan", "score": 98}, {"name": "Lucy", "score": 46}, {"name": "Isaac", "score": 77}, {"name": "Penelope", "score": 62}, {"name": "Anthony", "score": 89}, {"name": "Stella", "score": 51}, {"name": "Thomas", "score": 94}, {"name": "Aurora", "score": 43}, {"name": "Adrian", "score": 71}, {"name": "Violet", "score": 83}, {"name": "Oscar", "score": 57}, {"name": "Elena", "score": 75}]
    sorted_players = sorted(players, key= lambda item: item["score"], reverse=True)
    context = {"players": sorted_players}

    return render(request, 'leaderboard.html', context)