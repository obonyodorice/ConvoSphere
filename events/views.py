from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from .models import Event, EventAgenda

def event_list(request):
    upcoming_events = Event.objects.filter(start_time__gte=timezone.now()).order_by('start_time')
    return render(request, 'events/list.html', {'events': upcoming_events})

def event_detail(request, slug):
    event = get_object_or_404(Event, slug=slug)
    agenda = event.agenda_items.all()
    return render(request, 'events/detail.html', {'event': event, 'agenda': agenda})

@login_required
def join_event(request, slug):
    event = get_object_or_404(Event, slug=slug)
    if request.user not in event.attendees.all():
        event.attendees.add(request.user)
    return redirect('events:detail', slug=slug)
