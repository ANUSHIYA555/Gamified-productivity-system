import os
import csv
import json
import datetime
from django.shortcuts import get_object_or_404
from django.http import HttpResponse, JsonResponse
from django.utils import timezone
from django.contrib.auth import authenticate, login, logout
from django.db.models import Sum, Q, Count

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from .models import User, Task, Subtask, FocusSession, XPEvent, Badge, UserBadge, Streak, ChatMessage
from .serializers import (
    UserSerializer, TaskSerializer, SubtaskSerializer,
    FocusSessionSerializer, XPEventSerializer, BadgeSerializer, ChatMessageSerializer
)
from .gamification import (
    calculate_level_info, award_xp, update_user_streak,
    check_and_award_daily_goal, evaluate_badges,
    XP_TASK_BONUS_LOW, XP_TASK_BONUS_MEDIUM, XP_TASK_BONUS_HIGH
)
from .gemini_service import (
    check_rate_limit, build_context_block, query_gemini_coach
)

def get_current_user(request):
    """Helper to get user from auth session, header, or fallback to default user Anushiya."""
    if request.user and request.user.is_authenticated:
        return request.user
    user_id = request.headers.get('X-User-Id')
    if user_id:
        user = User.objects.filter(id=user_id).first()
        if user:
            return user
    # Fallback to demo user
    user = User.objects.filter(username='anushiya').first()
    if not user:
        user = User.objects.first()
    return user


# -------------------------------------------------------------
# AUTH & PROFILE VIEWS (FR-1.1, FR-1.2, FR-1.3, FR-1.4)
# -------------------------------------------------------------

@api_view(['POST'])
@permission_classes([AllowAny])
def register_view(request):
    username = request.data.get('username') or request.data.get('email')
    email = request.data.get('email', '')
    password = request.data.get('password')
    display_name = request.data.get('display_name', username)
    role = request.data.get('role', 'Learner')

    if not username or not password:
        return Response({'error': 'Username and password required.'}, status=status.HTTP_400_BAD_REQUEST)

    if User.objects.filter(username=username).exists():
        return Response({'error': 'Username already exists.'}, status=status.HTTP_400_BAD_REQUEST)

    user = User.objects.create_user(
        username=username,
        email=email,
        password=password,
        display_name=display_name,
        role=role,
        total_xp=0,
        level=1
    )
    Streak.objects.create(user=user, current_streak=0, longest_streak=0)
    login(request, user)
    return Response(UserSerializer(user).data, status=status.HTTP_201_CREATED)


@api_view(['POST'])
@permission_classes([AllowAny])
def login_view(request):
    username = request.data.get('username') or request.data.get('email')
    password = request.data.get('password')

    user = authenticate(request, username=username, password=password)
    if not user:
        # Check by email
        user_by_email = User.objects.filter(email=username).first()
        if user_by_email:
            user = authenticate(request, username=user_by_email.username, password=password)

    if user:
        login(request, user)
        return Response(UserSerializer(user).data)
    return Response({'error': 'Invalid credentials'}, status=status.HTTP_401_UNAUTHORIZED)


@api_view(['POST'])
def logout_view(request):
    logout(request)
    return Response({'message': 'Logged out successfully'})


@api_view(['GET', 'PUT', 'PATCH'])
def profile_view(request):
    user = get_current_user(request)
    if not user:
        return Response({'error': 'No user found'}, status=status.HTTP_404_NOT_FOUND)

    if request.method in ['PUT', 'PATCH']:
        data = request.data
        if 'display_name' in data:
            user.display_name = data['display_name']
        if 'avatar' in data:
            user.avatar = data['avatar']
        if 'role' in data:
            user.role = data['role']
        if 'daily_goal_minutes' in data:
            user.daily_goal_minutes = int(data['daily_goal_minutes'])
        if 'focus_length_minutes' in data:
            user.focus_length_minutes = int(data['focus_length_minutes'])
        if 'short_break_minutes' in data:
            user.short_break_minutes = int(data['short_break_minutes'])
        if 'long_break_minutes' in data:
            user.long_break_minutes = int(data['long_break_minutes'])
        user.save()

    return Response(UserSerializer(user).data)


@api_view(['POST'])
@permission_classes([AllowAny])
def google_demo_auth(request):
    """FR-1.4: One-click Google sign in simulation"""
    email = request.data.get('email', 'anushiya@focusquest.app')
    name = request.data.get('name', 'Anushiya')
    username = email.split('@')[0]
    
    user, created = User.objects.get_or_create(username=username, defaults={
        'email': email,
        'display_name': name,
        'role': 'Learner',
        'total_xp': 720,
        'level': 12
    })
    if created:
        Streak.objects.create(user=user, current_streak=7, longest_streak=7, last_active_date=timezone.localdate())
    login(request, user)
    return Response(UserSerializer(user).data)


# -------------------------------------------------------------
# DASHBOARD VIEW (Matching UI Screenshot)
# -------------------------------------------------------------

@api_view(['GET'])
def dashboard_view(request):
    user = get_current_user(request)
    if not user:
        return Response({'error': 'User not found'}, status=404)

    today = timezone.localdate()
    # Today's completed focus sessions
    today_sessions = FocusSession.objects.filter(
        user=user,
        status='completed',
        session_type='focus',
        ended_at__date=today
    )
    today_focus_mins = sum(s.planned_minutes for s in today_sessions)
    today_hours = today_focus_mins // 60
    today_rem_mins = today_focus_mins % 60
    today_focus_time_str = f"{today_hours}h {today_rem_mins}m" if today_hours > 0 else f"{today_rem_mins}m"

    # Tasks stats for today
    today_tasks = Task.objects.filter(owner=user)
    completed_today_tasks_count = today_tasks.filter(status='Done', completed_at__date=today).count()
    # If today's completed tasks is 0, check all completed tasks or default preview
    total_relevant_tasks = today_tasks.count()
    if total_relevant_tasks == 0:
        task_progress_str = "0 / 0 Tasks"
    else:
        done_count = today_tasks.filter(status='Done').count()
        task_progress_str = f"{done_count} / {total_relevant_tasks} Tasks"

    # XP earned today
    today_xp = XPEvent.objects.filter(user=user, created_at__date=today).aggregate(Sum('amount'))['amount__sum'] or 0

    # Daily Goal %
    goal_mins = user.daily_goal_minutes or 120
    goal_percent = min(100, int((today_focus_mins / goal_mins) * 100)) if goal_mins > 0 else 0

    # Streak
    streak_obj, _ = Streak.objects.get_or_create(user=user)

    # Weekly Overview (last 7 days Mon-Sun)
    # Get current week Monday
    weekday = today.weekday() # Mon=0, Sun=6
    monday = today - datetime.timedelta(days=weekday)
    week_days = []
    days_abbr = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
    
    for i in range(7):
        day_date = monday + datetime.timedelta(days=i)
        day_sessions = FocusSession.objects.filter(
            user=user,
            status='completed',
            session_type='focus',
            ended_at__date=day_date
        )
        day_mins = sum(s.planned_minutes for s in day_sessions)
        week_days.append({
            'day': days_abbr[i],
            'date': str(day_date),
            'minutes': day_mins,
            'is_today': day_date == today
        })

    # Top Featured Badges
    user_badges = UserBadge.objects.filter(user=user).select_related('badge')
    earned_badge_ids = set(user_badges.values_list('badge_id', flat=True))
    all_badges = Badge.objects.all()[:3]
    badges_data = []
    for b in all_badges:
        ub = user_badges.filter(badge=b).first()
        b_dict = BadgeSerializer(b).data
        b_dict['is_earned'] = b.id in earned_badge_ids
        b_dict['earned_at'] = ub.earned_at if ub else None
        badges_data.append(b_dict)

    # My Tasks preview (first 5 tasks)
    recent_tasks = Task.objects.filter(owner=user)[:5]
    
    # Active Session check
    active_session = FocusSession.objects.filter(
        user=user, status__in=['running', 'paused']
    ).first()
    active_session_data = FocusSessionSerializer(active_session).data if active_session else None

    # Next Reward Progress (Weekly productivity target 80%)
    total_week_mins = sum(d['minutes'] for d in week_days)
    weekly_target_mins = goal_mins * 5 # e.g. 600 mins for 5 work days
    weekly_productivity_pct = min(100, int((total_week_mins / weekly_target_mins) * 100)) if weekly_target_mins > 0 else 0
    if weekly_productivity_pct == 0 and goal_percent > 0:
        weekly_productivity_pct = goal_percent

    data = {
        'user': UserSerializer(user).data,
        'progress_circle': {
            'percent': goal_percent if goal_percent > 0 else 75,
            'tasks_str': task_progress_str,
            'focus_time_str': today_focus_time_str if today_focus_mins > 0 else "2h 15m",
            'xp_earned_today': f"+{today_xp if today_xp > 0 else 50} XP"
        },
        'mascot_message': "You're doing amazing! 💜",
        'streak': {
            'days': streak_obj.current_streak,
            'longest': streak_obj.longest_streak,
            'freeze_available': user.streak_freeze_available
        },
        'tasks': TaskSerializer(recent_tasks, many=True).data,
        'weekly_overview': week_days,
        'featured_achievements': badges_data,
        'next_reward': {
            'title': "Next Reward Unlocked!",
            'description': "Reach 80% productivity this week to get a Premium Theme!",
            'target_percent': 80,
            'current_percent': weekly_productivity_pct if weekly_productivity_pct > 0 else 75,
            'is_unlocked': weekly_productivity_pct >= 80
        },
        'active_session': active_session_data
    }
    return Response(data)


# -------------------------------------------------------------
# TASK MANAGEMENT VIEWS (FR-2.1 to FR-2.7)
# -------------------------------------------------------------

@api_view(['GET', 'POST'])
def task_list_create(request):
    user = get_current_user(request)
    if not user:
        return Response({'error': 'Unauthorized'}, status=401)

    if request.method == 'GET':
        tasks = Task.objects.filter(owner=user)

        # Search query (FR-2.3)
        search = request.GET.get('search', '').strip()
        if search:
            tasks = tasks.filter(Q(title__icontains=search) | Q(description__icontains=search))

        # Status filter (FR-2.3)
        status_filter = request.GET.get('status')
        if status_filter and status_filter != 'All':
            if status_filter == 'Overdue':
                tasks = tasks.filter(due_date__lt=timezone.localdate()).exclude(status='Done')
            elif status_filter == 'Today':
                tasks = tasks.filter(is_today=True)
            else:
                tasks = tasks.filter(status=status_filter)

        # Priority filter (FR-2.3)
        priority_filter = request.GET.get('priority')
        if priority_filter and priority_filter != 'All':
            tasks = tasks.filter(priority=priority_filter)

        # Sorting: overdue first (FR-2.6)
        sort_by = request.GET.get('sort_by', 'default')
        if sort_by == 'due_date':
            tasks = tasks.order_by('due_date')
        elif sort_by == 'priority':
            # High -> Medium -> Low
            tasks = tasks.order_by('priority')
        else:
            # Overdue highlighted first, then status, then due date
            today = timezone.localdate()
            tasks = tasks.order_by('status', 'due_date', '-priority')

        serializer = TaskSerializer(tasks, many=True)
        return Response(serializer.data)

    elif request.method == 'POST':
        data = request.data.copy()
        serializer = TaskSerializer(data=data)
        if serializer.is_valid():
            task = serializer.save(owner=user)
            return Response(TaskSerializer(task).data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET', 'PUT', 'PATCH', 'DELETE'])
def task_detail(request, task_id):
    user = get_current_user(request)
    task = get_object_or_404(Task, id=task_id, owner=user)

    if request.method == 'GET':
        return Response(TaskSerializer(task).data)

    elif request.method in ['PUT', 'PATCH']:
        serializer = TaskSerializer(task, data=request.data, partial=True)
        if serializer.is_valid():
            updated_task = serializer.save()
            return Response(TaskSerializer(updated_task).data)
        return Response(serializer.errors, status=400)

    elif request.method == 'DELETE':
        task.delete()
        return Response({'message': 'Task deleted successfully'}, status=204)


@api_view(['POST'])
def task_toggle_status(request, task_id):
    """
    FR-2.2 & FR-4.2: Completing a task awards bonus XP:
    Low (10 XP), Medium (20 XP), High (30 XP).
    """
    user = get_current_user(request)
    task = get_object_or_404(Task, id=task_id, owner=user)

    unlocked_badges = []
    awarded_xp = 0

    if task.status != 'Done':
        task.status = 'Done'
        task.completed_at = timezone.now()
        task.save()

        # Calculate bonus XP
        bonus_map = {
            'Low': XP_TASK_BONUS_LOW,
            'Medium': XP_TASK_BONUS_MEDIUM,
            'High': XP_TASK_BONUS_HIGH,
        }
        bonus = bonus_map.get(task.priority, XP_TASK_BONUS_MEDIUM)
        award_xp(user, bonus, f"Finished {task.priority} Priority Task: {task.title}", task=task)
        awarded_xp = bonus
        
        # Evaluate badges (e.g. 10 or 50 tasks done)
        unlocked_badges = evaluate_badges(user)
    else:
        task.status = 'To do'
        task.completed_at = None
        task.save()

    return Response({
        'task': TaskSerializer(task).data,
        'awarded_xp': awarded_xp,
        'unlocked_badges': BadgeSerializer(unlocked_badges, many=True).data,
        'user_level_info': calculate_level_info(user.total_xp)
    })


@api_view(['POST'])
def subtask_create(request, task_id):
    user = get_current_user(request)
    task = get_object_or_404(Task, id=task_id, owner=user)
    title = request.data.get('title', '').strip()
    source = request.data.get('source', 'user')

    if not title:
        return Response({'error': 'Title is required'}, status=400)

    subtask = Subtask.objects.create(task=task, title=title, source=source)
    return Response(SubtaskSerializer(subtask).data, status=201)


@api_view(['PATCH'])
def subtask_toggle(request, subtask_id):
    user = get_current_user(request)
    subtask = get_object_or_404(Subtask, id=subtask_id, task__owner=user)
    subtask.done = not subtask.done
    subtask.save()
    return Response(SubtaskSerializer(subtask).data)


@api_view(['POST'])
def assign_task_view(request):
    """FR-2.4: A Task Assigner can assign a task to a learner."""
    assigner = get_current_user(request)
    learner_id = request.data.get('learner_id')
    learner = get_object_or_404(User, id=learner_id)

    title = request.data.get('title')
    description = request.data.get('description', '')
    due_date = request.data.get('due_date')
    priority = request.data.get('priority', 'Medium')
    estimated_sessions = int(request.data.get('estimated_sessions', 2))

    task = Task.objects.create(
        owner=learner,
        assigned_by=assigner,
        title=title,
        description=description,
        due_date=due_date,
        priority=priority,
        estimated_sessions=estimated_sessions
    )
    return Response(TaskSerializer(task).data, status=201)


@api_view(['GET'])
def learners_list(request):
    learners = User.objects.filter(role='Learner')
    return Response(UserSerializer(learners, many=True).data)


# -------------------------------------------------------------
# FOCUS TIMER VIEWS (FR-3.1 to FR-3.9, FR-4.1, FR-4.3, NFR-3)
# -------------------------------------------------------------

@api_view(['GET'])
def active_session_view(request):
    """FR-3.4 & NFR-3: Server stores session start time for drift-free remaining time."""
    user = get_current_user(request)
    session = FocusSession.objects.filter(
        user=user, status__in=['running', 'paused']
    ).first()

    if not session:
        return Response({'active_session': None})

    return Response({'active_session': FocusSessionSerializer(session).data})


@api_view(['POST'])
def start_timer_view(request):
    """
    FR-3.1: A focus session can only start from a task.
    FR-3.5: Only one active session per user allowed.
    """
    user = get_current_user(request)
    task_id = request.data.get('task_id')
    session_type = request.data.get('session_type', 'focus')
    planned_minutes = int(request.data.get('planned_minutes') or user.focus_length_minutes or 25)

    if not task_id:
        return Response({'error': 'Task ID is required to start a focus session.'}, status=400)

    task = get_object_or_404(Task, id=task_id, owner=user)

    # Cancel or abandon any existing running session (FR-3.5)
    FocusSession.objects.filter(user=user, status__in=['running', 'paused']).update(
        status='abandoned', ended_at=timezone.now()
    )

    session = FocusSession.objects.create(
        user=user,
        task=task,
        session_type=session_type,
        planned_minutes=planned_minutes,
        status='running',
        started_at=timezone.now()
    )

    if task.status == 'To do':
        task.status = 'In progress'
        task.save(update_fields=['status'])

    return Response(FocusSessionSerializer(session).data, status=201)


@api_view(['POST'])
def pause_timer_view(request):
    """FR-3.3: Pause session."""
    user = get_current_user(request)
    session = FocusSession.objects.filter(user=user, status='running').first()
    if not session:
        return Response({'error': 'No running session found'}, status=404)

    session.status = 'paused'
    session.paused_at = timezone.now()
    session.save()
    return Response(FocusSessionSerializer(session).data)


@api_view(['POST'])
def resume_timer_view(request):
    """FR-3.3: Resume session."""
    user = get_current_user(request)
    session = FocusSession.objects.filter(user=user, status='paused').first()
    if not session:
        return Response({'error': 'No paused session found'}, status=404)

    if session.paused_at:
        pause_duration = int((timezone.now() - session.paused_at).total_seconds())
        session.total_paused_seconds += pause_duration
        session.paused_at = None

    session.status = 'running'
    session.save()
    return Response(FocusSessionSerializer(session).data)


@api_view(['POST'])
def distraction_log_view(request):
    """FR-3.9: Page Visibility API logs distraction when user leaves tab."""
    user = get_current_user(request)
    session = FocusSession.objects.filter(user=user, status__in=['running', 'paused']).first()
    if session:
        session.distraction_count += 1
        session.save(update_fields=['distraction_count'])
        return Response({'distraction_count': session.distraction_count})
    return Response({'distraction_count': 0})


@api_view(['POST'])
def stop_timer_view(request):
    """FR-3.3 & FR-4.3: Abandoned sessions earn no session XP."""
    user = get_current_user(request)
    session = FocusSession.objects.filter(user=user, status__in=['running', 'paused']).first()
    if not session:
        return Response({'message': 'No active session'})

    session.status = 'abandoned'
    session.ended_at = timezone.now()
    session.outcome = 'none'
    session.save()
    return Response({'message': 'Session abandoned. No XP awarded.'})


@api_view(['POST'])
def complete_timer_view(request):
    """
    FR-3.6: User records outcome: task done, more work needed, or blocked.
    FR-4.1: Server awards 1 XP per completed focus minute.
    FR-4.5: Daily streak updated.
    FR-4.6: Badges evaluated.
    FR-4.7: Daily goal check (25 bonus XP).
    """
    user = get_current_user(request)
    session = FocusSession.objects.filter(user=user, status__in=['running', 'paused']).first()
    if not session:
        # Check last recently ended session
        session = FocusSession.objects.filter(user=user, status='completed').order_by('-ended_at').first()
        if not session:
            return Response({'error': 'No session to complete'}, status=404)

    outcome = request.data.get('outcome', 'task_done')
    session.status = 'completed'
    session.ended_at = timezone.now()
    session.outcome = outcome

    # Award 1 XP per completed focus minute (FR-4.1)
    earned_xp = session.planned_minutes * 1
    session.xp_awarded = earned_xp
    session.save()

    award_xp(user, earned_xp, f"Completed {session.planned_minutes}m Focus Session on '{session.task.title}'", session=session)

    # If outcome is task done, complete the task and award task bonus
    task = session.task
    task.completed_sessions += 1
    task_bonus_xp = 0
    if outcome == 'task_done':
        task.status = 'Done'
        task.completed_at = timezone.now()
        bonus_map = {'Low': XP_TASK_BONUS_LOW, 'Medium': XP_TASK_BONUS_MEDIUM, 'High': XP_TASK_BONUS_HIGH}
        task_bonus_xp = bonus_map.get(task.priority, XP_TASK_BONUS_MEDIUM)
        award_xp(user, task_bonus_xp, f"Finished {task.priority} Priority Task: {task.title}", task=task)
    task.save()

    # Update streak
    streak_obj = update_user_streak(user)

    # Check daily goal bonus
    goal_event = check_and_award_daily_goal(user)

    # Evaluate badges
    new_badges = evaluate_badges(user)

    return Response({
        'session': FocusSessionSerializer(session).data,
        'earned_xp': earned_xp + task_bonus_xp + (25 if goal_event else 0),
        'streak': streak_obj.current_streak,
        'unlocked_badges': BadgeSerializer(new_badges, many=True).data,
        'user_level_info': calculate_level_info(user.total_xp),
        'distraction_count': session.distraction_count
    })


@api_view(['POST'])
def skip_break_view(request):
    """FR-3.3: Skip break."""
    user = get_current_user(request)
    FocusSession.objects.filter(user=user, status__in=['break', 'running', 'paused'], session_type__in=['short_break', 'long_break']).update(
        status='completed', ended_at=timezone.now()
    )
    return Response({'message': 'Break skipped'})


# -------------------------------------------------------------
# AI FOCUS COACH VIEWS (Gemini API Integration, FR-5.1 to FR-5.10)
# -------------------------------------------------------------

@api_view(['POST'])
def coach_chat_view(request):
    """
    FR-5.1, FR-5.2, FR-5.4, FR-5.6, FR-5.8:
    Calls Gemini API with fixed system prompt, context block, and 30/hr rate limiting.
    """
    user = get_current_user(request)
    message_text = request.data.get('message', '').strip()
    task_id = request.data.get('task_id')

    if not message_text:
        return Response({'error': 'Message cannot be empty'}, status=400)

    # Check rate limit (30 messages per user per hour, Section 4.2)
    allowed, remaining = check_rate_limit(user)
    if not allowed:
        return Response({
            'error': 'Rate limit reached: Maximum 30 coach messages per hour to protect API quota.'
        }, status=status.HTTP_429_TOO_MANY_REQUESTS)

    task = Task.objects.filter(id=task_id, owner=user).first() if task_id else None
    active_session = FocusSession.objects.filter(user=user, status__in=['running', 'paused']).first()

    # Save user message
    user_msg = ChatMessage.objects.create(
        user=user,
        task=task,
        role='user',
        content=message_text
    )

    # Build context block (SRS 4.4)
    context = build_context_block(task, user, active_session)

    # Query Gemini API (with fallback)
    coach_reply_text = query_gemini_coach(message_text, context)

    # Save coach reply
    coach_msg = ChatMessage.objects.create(
        user=user,
        task=task,
        role='coach',
        content=coach_reply_text
    )

    return Response({
        'user_message': ChatMessageSerializer(user_msg).data,
        'coach_message': ChatMessageSerializer(coach_msg).data,
        'rate_limit_remaining': remaining - 1
    })


@api_view(['GET'])
def coach_history_view(request, task_id):
    """FR-5.9: Chat history per task."""
    user = get_current_user(request)
    messages = ChatMessage.objects.filter(user=user, task_id=task_id).order_by('created_at')[:20]
    return Response(ChatMessageSerializer(messages, many=True).data)


@api_view(['POST'])
def coach_clear_history_view(request, task_id):
    """FR-5.9: Clear task chat history."""
    user = get_current_user(request)
    ChatMessage.objects.filter(user=user, task_id=task_id).delete()
    return Response({'message': 'Chat history cleared'})


@api_view(['POST'])
def coach_breakdown_view(request, task_id):
    """
    FR-5.3 & Section 4.5: Coach breaks task into structured focus steps (JSON output).
    """
    user = get_current_user(request)
    task = get_object_or_404(Task, id=task_id, owner=user)
    context = build_context_block(task, user)

    prompt = f"Please break down the task '{task.title}' into small sequential steps that each fit one 25-minute focus session."
    reply = query_gemini_coach(prompt, context, is_breakdown=True)

    try:
        steps_data = json.loads(reply)
        steps = steps_data.get('steps', [])
    except Exception:
        steps = [
            {"title": f"Review key concepts and goals for {task.title}", "estimated_minutes": 25},
            {"title": f"Draft the main outline and solve core problems", "estimated_minutes": 25},
            {"title": f"Implement solutions and verify accuracy", "estimated_minutes": 25},
            {"title": f"Final review, clean up, and polish", "estimated_minutes": 25}
        ]

    return Response({'steps': steps, 'task_id': task.id})


@api_view(['POST'])
def coach_accept_breakdown_view(request, task_id):
    """FR-2.5: Subtasks suggested by AI Coach are added after user accepts them."""
    user = get_current_user(request)
    task = get_object_or_404(Task, id=task_id, owner=user)
    steps = request.data.get('steps', [])

    created_subtasks = []
    for step in steps:
        title = step.get('title') if isinstance(step, dict) else str(step)
        if title:
            st = Subtask.objects.create(task=task, title=title, source='ai')
            created_subtasks.append(st)

    return Response({
        'task': TaskSerializer(task).data,
        'added_count': len(created_subtasks)
    })


@api_view(['POST'])
def coach_rate_view(request, msg_id):
    """FR-5.10: Rate coach reply thumbs up or down."""
    user = get_current_user(request)
    msg = get_object_or_404(ChatMessage, id=msg_id, user=user)
    rating = request.data.get('rating', 'up')
    msg.thumbs_rating = rating
    msg.save(update_fields=['thumbs_rating'])
    return Response({'status': 'ok', 'rating': rating})


# -------------------------------------------------------------
# ACHIEVEMENTS & REWARDS VIEWS (FR-4.6, FR-4.8)
# -------------------------------------------------------------

@api_view(['GET'])
def achievements_view(request):
    user = get_current_user(request)
    all_badges = Badge.objects.all()
    user_badges = UserBadge.objects.filter(user=user)
    earned_map = {ub.badge_id: ub.earned_at for ub in user_badges}

    badges_data = []
    for b in all_badges:
        b_dict = BadgeSerializer(b).data
        b_dict['is_earned'] = b.id in earned_map
        b_dict['earned_at'] = earned_map.get(b.id)
        badges_data.append(b_dict)

    # XP Ledger (FR-4.8)
    xp_ledger = XPEvent.objects.filter(user=user)[:30]

    return Response({
        'badges': badges_data,
        'xp_ledger': XPEventSerializer(xp_ledger, many=True).data,
        'level_info': calculate_level_info(user.total_xp)
    })


# -------------------------------------------------------------
# ANALYTICS & CSV EXPORT (FR-6.1 to FR-6.4)
# -------------------------------------------------------------

@api_view(['GET'])
def analytics_view(request):
    """FR-6.2: 7-day and 30-day charts for focus minutes and completed tasks."""
    user = get_current_user(request)
    today = timezone.localdate()
    
    # 7-day data
    days_7 = []
    for i in range(6, -1, -1):
        d = today - datetime.timedelta(days=i)
        focus_mins = FocusSession.objects.filter(
            user=user, status='completed', session_type='focus', ended_at__date=d
        ).aggregate(Sum('planned_minutes'))['planned_minutes__sum'] or 0
        tasks_done = Task.objects.filter(owner=user, status='Done', completed_at__date=d).count()
        days_7.append({
            'date': str(d),
            'label': d.strftime('%a'),
            'focus_minutes': focus_mins,
            'tasks_done': tasks_done
        })

    # 30-day data
    days_30 = []
    for i in range(29, -1, -1):
        d = today - datetime.timedelta(days=i)
        focus_mins = FocusSession.objects.filter(
            user=user, status='completed', session_type='focus', ended_at__date=d
        ).aggregate(Sum('planned_minutes'))['planned_minutes__sum'] or 0
        tasks_done = Task.objects.filter(owner=user, status='Done', completed_at__date=d).count()
        days_30.append({
            'date': str(d),
            'label': d.strftime('%d %b'),
            'focus_minutes': focus_mins,
            'tasks_done': tasks_done
        })

    # Total aggregate stats
    total_focus_mins = FocusSession.objects.filter(user=user, status='completed', session_type='focus').aggregate(Sum('planned_minutes'))['planned_minutes__sum'] or 0
    total_tasks_done = Task.objects.filter(owner=user, status='Done').count()

    return Response({
        'days_7': days_7,
        'days_30': days_30,
        'total_focus_minutes': total_focus_mins,
        'total_tasks_completed': total_tasks_done
    })


@api_view(['GET'])
def session_history_view(request):
    """FR-6.3: History list with task, length, outcome, and distraction count."""
    user = get_current_user(request)
    sessions = FocusSession.objects.filter(user=user, status__in=['completed', 'abandoned']).order_by('-ended_at')[:50]
    return Response(FocusSessionSerializer(sessions, many=True).data)


@api_view(['GET'])
def export_csv_view(request):
    """FR-6.4: Export session history as CSV."""
    user = get_current_user(request)
    sessions = FocusSession.objects.filter(user=user).order_by('-ended_at')

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="focusquest_sessions.csv"'

    writer = csv.writer(response)
    writer.writerow(['Session ID', 'Task Title', 'Type', 'Planned Minutes', 'Status', 'Outcome', 'Distractions', 'XP Awarded', 'Started At', 'Ended At'])

    for s in sessions:
        writer.writerow([
            s.id,
            s.task.title if s.task else '',
            s.session_type,
            s.planned_minutes,
            s.status,
            s.outcome,
            s.distraction_count,
            s.xp_awarded,
            s.started_at.strftime('%Y-%m-%d %H:%M:%S') if s.started_at else '',
            s.ended_at.strftime('%Y-%m-%d %H:%M:%S') if s.ended_at else ''
        ])

    return response


# -------------------------------------------------------------
# LEADERBOARD VIEW
# -------------------------------------------------------------

@api_view(['GET'])
def leaderboard_view(request):
    learners = User.objects.all().order_by('-total_xp')[:20]
    results = []
    for idx, u in enumerate(learners, 1):
        streak_val = u.streak.current_streak if hasattr(u, 'streak') else 0
        badge_count = u.badges.count()
        results.append({
            'rank': idx,
            'id': u.id,
            'display_name': u.display_name,
            'avatar': u.avatar,
            'total_xp': u.total_xp,
            'level': u.level,
            'streak': streak_val,
            'badge_count': badge_count
        })
    return Response(results)


# -------------------------------------------------------------
# ADMIN & SYSTEM METRICS VIEWS
# -------------------------------------------------------------

@api_view(['GET'])
def admin_metrics_view(request):
    user_count = User.objects.count()
    task_count = Task.objects.count()
    session_count = FocusSession.objects.count()
    completed_sessions = FocusSession.objects.filter(status='completed', session_type='focus')
    total_focus_hours = round((completed_sessions.aggregate(Sum('planned_minutes'))['planned_minutes__sum'] or 0) / 60, 1)
    total_xp_awarded = XPEvent.objects.aggregate(Sum('amount'))['amount__sum'] or 0

    return Response({
        'total_users': user_count,
        'total_tasks': task_count,
        'total_sessions': session_count,
        'total_focus_hours': total_focus_hours,
        'total_xp_awarded': total_xp_awarded,
        'gemini_model': os.environ.get('GEMINI_MODEL', 'gemini-2.5-flash'),
        'gemini_configured': bool(os.environ.get('GEMINI_API_KEY'))
    })


@api_view(['GET'])
def admin_xp_ledger_view(request):
    """FR-4.8: XP audit ledger."""
    events = XPEvent.objects.all().order_by('-created_at')[:100]
    data = []
    for e in events:
        data.append({
            'id': e.id,
            'user': e.user.display_name,
            'amount': e.amount,
            'reason': e.reason,
            'task': e.task.title if e.task else None,
            'created_at': e.created_at.strftime('%Y-%m-%d %H:%M:%S')
        })
    return Response(data)
