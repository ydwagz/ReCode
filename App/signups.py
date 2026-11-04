def remove_broken_signups(User):
    """Delete accounts left half-created by a failed sign-up: no profile and never logged in.

    Every real account gets a profile when it is created, so these can never be used —
    they only block their username and email. Works with real and migration models.
    """
    broken = User.objects.filter(profile__isnull=True, last_login__isnull=True)
    count = broken.count()
    broken.delete()
    return count
