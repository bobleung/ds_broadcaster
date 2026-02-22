import json

from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, StreamingHttpResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.template.loader import render_to_string
from .models import Room, Message
from .forms import RoomForm, RoomMemberForm
from ds_broadcaster import broadcast
from ds_broadcaster.formatting import format_patch_signals

PALETTE = [
    "#b91c1c",  # red-700
    "#0369a1",  # sky-700
    "#a16207",  # yellow-700
    "#6d28d9",  # violet-700
    "#134e4a",  # teal-900
    "#be123c",  # rose-700
    "#4d7c0f",  # lime-700
    "#7c2d12",  # orange-900
    "#556b2f",  # olive-600
    "#1a2e05",  # olive-950
]


def _member_colours(members):
    """Return a dict mapping user_id -> colour for a list of members."""
    return {u.pk: PALETTE[i % len(PALETTE)] for i, u in enumerate(members)}


def _room_presence(channel, online_ids):
    room_pk = channel.removeprefix("room-")
    room = Room.objects.get(pk=room_pk)
    online_set = set(online_ids)
    all_members = list(room.members.all())
    colours = _member_colours(all_members)
    online = [u for u in all_members if u.pk in online_set]
    offline = [u for u in all_members if u.pk not in online_set]
    users = (
        [{"user": u, "online": True, "colour": colours[u.pk]} for u in online] +
        [{"user": u, "online": False, "colour": colours[u.pk]} for u in offline]
    )
    cursor_signals = {f'cursor_{u.pk}_active': False for u in offline}
    if cursor_signals:
        broadcast.signals(channel, cursor_signals)
    html = render_to_string("rooms/_members.html", {"users": users})
    colour_signals = {f'user_{uid}_colour': colour for uid, colour in colours.items()}
    return (html, colour_signals)


@login_required
def room_list(request):
    rooms = request.user.rooms.all()
    return render(request, 'rooms/room_list.html', {'rooms': rooms})


@login_required
def room_detail(request, pk):
    room = get_object_or_404(Room, pk=pk, members=request.user)
    room_members = list(room.members.all())
    colours = _member_colours(room_members)
    members = [{"user": u, "online": False, "colour": colours[u.pk]} for u in room_members]
    chat_messages = room.messages.select_related('author').all()
    return render(request, 'rooms/room_detail.html', {
        'room': room,
        'user_id': request.user.pk,
        'members': members,
        'room_members': room_members,
        'chat_messages': chat_messages,
        'colours': colours,
    })


@login_required
def room_create(request):
    if request.method == 'POST':
        form = RoomForm(request.POST)
        if form.is_valid():
            room = form.save()
            room.members.add(request.user)
            messages.success(request, 'Room created.')
            return redirect('room_detail', pk=room.pk)
    else:
        form = RoomForm()
    return render(request, 'rooms/room_create.html', {'form': form})


@login_required
def room_edit(request, pk):
    room = get_object_or_404(Room, pk=pk, members=request.user)
    form = RoomForm(instance=room)
    member_form = RoomMemberForm()

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'update_name':
            form = RoomForm(request.POST, instance=room)
            if form.is_valid():
                form.save()
                messages.success(request, 'Room name updated.')
                return redirect('room_edit', pk=room.pk)

        elif action == 'add_member':
            member_form = RoomMemberForm(request.POST)
            if member_form.is_valid():
                room.members.add(member_form.user)
                messages.success(request, f'{member_form.user.email} added to the room.')
                return redirect('room_edit', pk=room.pk)

        elif action == 'remove_member':
            user_id = request.POST.get('user_id')
            room.members.remove(user_id)
            messages.success(request, 'Member removed.')
            return redirect('room_edit', pk=room.pk)

    return render(request, 'rooms/room_edit.html', {
        'room': room,
        'form': form,
        'member_form': member_form,
    })


@login_required
def room_delete(request, pk):
    room = get_object_or_404(Room, pk=pk, members=request.user)
    if request.method == 'POST':
        room.delete()
        messages.success(request, 'Room deleted.')
        return redirect('room_list')
    return render(request, 'rooms/room_delete.html', {'room': room})

@login_required
def room_connect(request, pk):
    room = get_object_or_404(Room, pk=pk, members=request.user)
    return broadcast.connect(f"room-{room.pk}", request, presence_callback=_room_presence)


@login_required
def room_send_message(request, pk):
    room = get_object_or_404(Room, pk=pk, members=request.user)
    try:
        signals = json.loads(request.body)
        body = signals.get('message_to_send', '').strip()
    except (json.JSONDecodeError, AttributeError):
        body = ''
    if body:
        msg = Message.objects.create(room=room, author=request.user, body=body)
        room_members = list(room.members.all())
        colours = _member_colours(room_members)
        html = render_to_string('rooms/_message.html', {
            'msg': msg,
            'colour': colours.get(msg.author.pk, PALETTE[0]),
        })
        broadcast(f'room-{room.pk}', html, selector='#chat-feed', mode='append')

    async def stream():
        yield format_patch_signals({'message_to_send': ''})

    return StreamingHttpResponse(stream(), content_type='text/event-stream')


@login_required
def room_cursor(request, pk):
    room = get_object_or_404(Room, pk=pk, members=request.user)
    try:
        data = json.loads(request.body)
        x = data.get('cursor_x', 0)
        y = data.get('cursor_y', 0)
    except (json.JSONDecodeError, AttributeError):
        x, y = 0, 0

    uid = request.user.pk
    broadcast.signals(f'room-{room.pk}', {
        f'cursor_{uid}_x': x,
        f'cursor_{uid}_y': y,
        f'cursor_{uid}_active': True,
    })

    return HttpResponse(status=204)
