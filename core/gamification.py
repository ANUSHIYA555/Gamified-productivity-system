import datetime
from django.utils import timezone
from django.db import transaction

# Configurable constants (NFR-11)
XP_PER_FOCUS_MINUTE = 1
XP_TASK_BONUS_LOW = 10
XP_TASK_BONUS_MEDIUM = 20
XP_TASK_BONUS_HIGH = 30
XP_DAILY_GOAL_BONUS = 25
DEFAULT_DAILY_GOAL_MINUTES = 120
STREAK_FREEZE_RESET_DAYS = 7


def calculate_level_info(total_xp):
    """
    Computes level and progress.
    Formula (FR-4.4): Level n to n+1 requires 100 * n XP.
    Total XP needed to reach Level L = sum_{i=1}^{L-1} (100 * i) = 50 * (L - 1) * L.
    For display matching, when level is L, XP required for next level is 100 * L.
    """
    level = 1
    accumulated = 0
    while True:
        needed = 100 * level
        if total_xp < accumulated + needed:
            current_level_xp = total_xp - accumulated
            next_level_xp = needed
            percent = min(100, int((current_level_xp / next_level_xp) * 100)) if next_level_xp > 0 else 0
            return {
                'level': level,
                'current_level_xp': current_level_xp,
                'next_level_xp': next_level_xp,
                'progress_percent': percent,
                'total_xp': total_xp
            }
        accumulated += needed
        level += 1


def award_xp(user, amount, reason, session=None, task=None):
    """
    FR-4.8: Every XP change is saved in a ledger with its reason.
    XP is calculated on the server only.
    """
    from .models import XPEvent
    if amount <= 0:
        return None
    
    with transaction.atomic():
        event = XPEvent.objects.create(
            user=user,
            amount=amount,
            reason=reason,
            session=session,
            task=task
        )
        user.total_xp += amount
        lvl_info = calculate_level_info(user.total_xp)
        user.level = lvl_info['level']
        user.save(update_fields=['total_xp', 'level'])
        return event


def check_and_award_daily_goal(user):
    """
    FR-4.7: Reaching daily focus goal awards 25 bonus XP once per day.
    """
    from .models import FocusSession, XPEvent
    today = timezone.localdate()
    today_sessions = FocusSession.objects.filter(
        user=user,
        status='completed',
        session_type='focus',
        ended_at__date=today
    )
    total_minutes_today = sum(s.planned_minutes for s in today_sessions)
    if total_minutes_today >= user.daily_goal_minutes:
        already_awarded = XPEvent.objects.filter(
            user=user,
            reason__icontains="Daily Focus Goal",
            created_at__date=today
        ).exists()
        if not already_awarded:
            return award_xp(user, XP_DAILY_GOAL_BONUS, f"Daily Focus Goal Reached ({user.daily_goal_minutes}m)")
    return None


def update_user_streak(user):
    """
    FR-4.5: The daily streak grows by 1 for each day with at least one completed focus session
    and resets to 0 after a missed day.
    FR-4.9: One 'streak freeze' per week protects the streak from a single missed day.
    """
    from .models import Streak
    streak_obj, _ = Streak.objects.get_or_create(user=user)
    today = timezone.localdate()
    yesterday = today - datetime.timedelta(days=1)
    two_days_ago = today - datetime.timedelta(days=2)
    
    if streak_obj.last_active_date == today:
        # Already counted for today
        return streak_obj
    
    # Check weekly streak freeze reset
    if user.streak_freeze_last_reset:
        days_since_reset = (today - user.streak_freeze_last_reset).days
        if days_since_reset >= STREAK_FREEZE_RESET_DAYS:
            user.streak_freeze_available = True
            user.streak_freeze_last_reset = today
            user.save(update_fields=['streak_freeze_available', 'streak_freeze_last_reset'])
    
    if streak_obj.last_active_date == yesterday:
        # Consecutive day
        streak_obj.current_streak += 1
    elif streak_obj.last_active_date == two_days_ago and user.streak_freeze_available:
        # Missed 1 day but protected by streak freeze!
        user.streak_freeze_available = False
        user.save(update_fields=['streak_freeze_available'])
        streak_obj.current_streak += 1
    elif streak_obj.last_active_date is None:
        streak_obj.current_streak = 1
    else:
        # Streak broken
        streak_obj.current_streak = 1
        
    streak_obj.last_active_date = today
    if streak_obj.current_streak > streak_obj.longest_streak:
        streak_obj.longest_streak = streak_obj.current_streak
    streak_obj.save()
    return streak_obj


def evaluate_badges(user):
    """
    FR-4.6: Badges unlock by rule:
    - first session
    - 7-day streak
    - 10 tasks done
    - 50-minute deep-work session
    - 10 hours focus (focus champ)
    - 50 tasks done (task master elite)
    Returns list of newly unlocked badge objects.
    """
    from .models import Badge, UserBadge, FocusSession, Task, Streak
    
    newly_unlocked = []
    all_badges = Badge.objects.all()
    existing_badge_ids = set(UserBadge.objects.filter(user=user).values_list('badge_id', flat=True))
    
    completed_sessions = FocusSession.objects.filter(user=user, status='completed', session_type='focus')
    session_count = completed_sessions.count()
    total_focus_minutes = sum(s.planned_minutes for s in completed_sessions)
    completed_tasks_count = Task.objects.filter(owner=user, status='Done').count()
    
    streak_obj, _ = Streak.objects.get_or_create(user=user)
    current_streak = streak_obj.current_streak
    
    has_50m_session = completed_sessions.filter(planned_minutes__gte=50).exists()
    
    for badge in all_badges:
        if badge.id in existing_badge_ids:
            continue
            
        unlocked = False
        if badge.code == 'first_session' and session_count >= 1:
            unlocked = True
        elif badge.code == 'streak_7' and current_streak >= 7:
            unlocked = True
        elif badge.code == 'task_master_10' and completed_tasks_count >= 10:
            unlocked = True
        elif badge.code == 'task_master_50' and completed_tasks_count >= 50:
            unlocked = True
        elif badge.code == 'deep_diver' and has_50m_session:
            unlocked = True
        elif badge.code == 'focus_champ_10h' and total_focus_minutes >= 600:
            unlocked = True
            
        if unlocked:
            ub = UserBadge.objects.create(user=user, badge=badge)
            if badge.xp_reward > 0:
                award_xp(user, badge.xp_reward, f"Unlocked Badge: {badge.name}")
            newly_unlocked.append(badge)
            
    return newly_unlocked
