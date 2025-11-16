from django.http import HttpResponseForbidden
from .models import Tournament

def staff_or_tadmin(view):
    def _wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return HttpResponseForbidden()
        if request.user.is_staff:
            return view(request, *args, **kwargs)
        t_pk = kwargs.get("pk") or kwargs.get("t_pk")
        if not t_pk:
            return HttpResponseForbidden()
        try:
            t = Tournament.objects.only("id").get(pk=t_pk)
        except Tournament.DoesNotExist:
            return HttpResponseForbidden()
        if t.admins.filter(id=request.user.id).exists():
            return view(request, *args, **kwargs)
        return HttpResponseForbidden()
    return _wrapped
