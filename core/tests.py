import datetime
from django.test import TestCase
from django.utils import timezone
from core.models import User, Task, Subtask, FocusSession, XPEvent, Badge, UserBadge, Streak
from core.gamification import (
    calculate_level_info, award_xp, update_user_streak,
    check_and_award_daily_goal, evaluate_badges,
    XP_PER_FOCUS_MINUTE, XP_TASK_BONUS_LOW, XP_TASK_BONUS_MEDIUM, XP_TASK_BONUS_HIGH, XP_DAILY_GOAL_BONUS
)
from core.gemini_service import build_context_block, fallback_coach_reply, check_rate_limit

class GamificationAndCoreTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='tester',
            email='tester@focusquest.app',
            password='testpassword',
            display_name='Test Learner',
            role='Learner',
            total_xp=0,
            level=1,
            daily_goal_minutes=120,
            focus_length_minutes=25,
            streak_freeze_available=True
        )
        self.streak = Streak.objects.create(
            user=self.user,
            current_streak=0,
            longest_streak=0,
            last_active_date=None
        )
        # Seed badges
        self.b_first = Badge.objects.create(code='first_session', name='First Step', description='First session', unlock_rule='1 session', xp_reward=25)
        self.b_streak7 = Badge.objects.create(code='streak_7', name='On Track', description='7-day streak', unlock_rule='7 streak', xp_reward=75)
        self.b_task10 = Badge.objects.create(code='task_master_10', name='Task Master', description='10 tasks done', unlock_rule='10 tasks', xp_reward=50)
        self.b_deep = Badge.objects.create(code='deep_diver', name='Deep Diver', description='50m session', unlock_rule='50m', xp_reward=50)
        self.b_champ = Badge.objects.create(code='focus_champ_10h', name='Focus Champ', description='10 hrs focus', unlock_rule='600m', xp_reward=100)

    def test_level_formula(self):
        """FR-4.4: Level n to n+1 requires 100 * n XP."""
        lvl1 = calculate_level_info(0)
        self.assertEqual(lvl1['level'], 1)
        self.assertEqual(lvl1['next_level_xp'], 100)
        self.assertEqual(lvl1['progress_percent'], 0)

        lvl1_half = calculate_level_info(50)
        self.assertEqual(lvl1_half['level'], 1)
        self.assertEqual(lvl1_half['current_level_xp'], 50)
        self.assertEqual(lvl1_half['progress_percent'], 50)

        # 100 XP reaches Level 2
        lvl2 = calculate_level_info(100)
        self.assertEqual(lvl2['level'], 2)
        self.assertEqual(lvl2['current_level_xp'], 0)
        self.assertEqual(lvl2['next_level_xp'], 200)

        # Level 2 needs 200 XP (total 300 to reach Level 3)
        lvl3 = calculate_level_info(300)
        self.assertEqual(lvl3['level'], 3)
        self.assertEqual(lvl3['next_level_xp'], 300)

    def test_award_xp_and_ledger(self):
        """FR-4.1, FR-4.8: XP calculated on server and saved in ledger."""
        event = award_xp(self.user, 25, "Completed 25m Focus Session")
        self.assertIsNotNone(event)
        self.assertEqual(self.user.total_xp, 25)
        self.assertEqual(XPEvent.objects.filter(user=self.user).count(), 1)
        self.assertEqual(XPEvent.objects.first().reason, "Completed 25m Focus Session")

    def test_task_completion_bonus(self):
        """FR-4.2: Bonus XP for task completion (10 Low, 20 Med, 30 High)."""
        t_low = Task.objects.create(owner=self.user, title="Low task", priority="Low")
        t_med = Task.objects.create(owner=self.user, title="Med task", priority="Medium")
        t_high = Task.objects.create(owner=self.user, title="High task", priority="High")

        award_xp(self.user, XP_TASK_BONUS_LOW, "Finished Low", task=t_low)
        award_xp(self.user, XP_TASK_BONUS_MEDIUM, "Finished Med", task=t_med)
        award_xp(self.user, XP_TASK_BONUS_HIGH, "Finished High", task=t_high)

        self.assertEqual(self.user.total_xp, 60)
        self.assertEqual(XPEvent.objects.filter(user=self.user).count(), 3)

    def test_streak_progression_and_reset(self):
        """FR-4.5: Daily streak grows by 1 for consecutive days and resets after missed day."""
        today = timezone.localdate()
        yesterday = today - datetime.timedelta(days=1)
        three_days_ago = today - datetime.timedelta(days=3)

        # First day
        s = update_user_streak(self.user)
        self.assertEqual(s.current_streak, 1)

        # Same day again shouldn't duplicate
        s = update_user_streak(self.user)
        self.assertEqual(s.current_streak, 1)

        # Yesterday active -> today active
        s.last_active_date = yesterday
        s.current_streak = 5
        s.save()
        s = update_user_streak(self.user)
        self.assertEqual(s.current_streak, 6)
        self.assertEqual(s.longest_streak, 6)

        # Missed 2 days (3 days ago) without freeze -> resets to 1
        self.user.streak_freeze_available = False
        self.user.save()
        s.last_active_date = three_days_ago
        s.current_streak = 10
        s.save()
        s = update_user_streak(self.user)
        self.assertEqual(s.current_streak, 1)

    def test_streak_freeze_protection(self):
        """FR-4.9: One streak freeze protects streak from single missed day."""
        today = timezone.localdate()
        two_days_ago = today - datetime.timedelta(days=2) # Missed 1 day (yesterday)

        self.user.streak_freeze_available = True
        self.user.save()
        self.user.streak.last_active_date = two_days_ago
        self.user.streak.current_streak = 12
        self.user.streak.save()

        s = update_user_streak(self.user)
        self.user.refresh_from_db()
        # Streak was saved and incremented!
        self.assertEqual(s.current_streak, 13)
        # Freeze consumed
        self.assertFalse(self.user.streak_freeze_available)

    def test_badge_evaluation(self):
        """FR-4.6: Badges unlock by rule."""
        task = Task.objects.create(owner=self.user, title="Study Session", priority="High")
        
        # 1. First session badge
        FocusSession.objects.create(
            user=self.user,
            task=task,
            session_type='focus',
            planned_minutes=25,
            status='completed',
            ended_at=timezone.now()
        )
        newly_unlocked = evaluate_badges(self.user)
        self.assertTrue(any(b.code == 'first_session' for b in newly_unlocked))
        self.assertTrue(UserBadge.objects.filter(user=self.user, badge=self.b_first).exists())

        # 2. Deep diver badge (50 min session)
        FocusSession.objects.create(
            user=self.user,
            task=task,
            session_type='focus',
            planned_minutes=50,
            status='completed',
            ended_at=timezone.now()
        )
        newly_unlocked = evaluate_badges(self.user)
        self.assertTrue(any(b.code == 'deep_diver' for b in newly_unlocked))

    def test_daily_goal_bonus(self):
        """FR-4.7: Daily focus goal reached awards 25 bonus XP."""
        task = Task.objects.create(owner=self.user, title="Deep Work Task")
        # Log 120 minutes of focus sessions today
        FocusSession.objects.create(
            user=self.user,
            task=task,
            session_type='focus',
            planned_minutes=120,
            status='completed',
            ended_at=timezone.now()
        )
        event = check_and_award_daily_goal(self.user)
        self.assertIsNotNone(event)
        self.assertEqual(event.amount, 25)
        self.assertIn("Daily Focus Goal", event.reason)

        # Checking again today shouldn't award twice
        second_event = check_and_award_daily_goal(self.user)
        self.assertIsNone(second_event)

    def test_timer_drift_free_remaining(self):
        """FR-3.4, NFR-3: Timer calculates remaining time from timestamps."""
        task = Task.objects.create(owner=self.user, title="Focus Timer Task")
        session = FocusSession.objects.create(
            user=self.user,
            task=task,
            session_type='focus',
            planned_minutes=25,
            started_at=timezone.now() - datetime.timedelta(minutes=5),
            status='running'
        )
        rem = session.remaining_seconds()
        # 25m - 5m = ~20m = ~1200 seconds (tolerance +/- 2s)
        self.assertAlmostEqual(rem, 1200, delta=3)

    def test_gemini_context_privacy(self):
        """SRS 4.4, NFR-6: Privacy context never sends password, real name, or email."""
        task = Task.objects.create(owner=self.user, title="Confidential Task", description="Testing privacy boundaries")
        context = build_context_block(task, self.user)
        
        context_str = str(context)
        self.assertNotIn(self.user.email, context_str)
        self.assertNotIn("testpassword", context_str)
        self.assertEqual(context["current_task"]["title"], "Confidential Task")
        self.assertEqual(context["user_level"], self.user.level)

    def test_gemini_coach_rules_fallback(self):
        """FR-5.4, FR-5.6, FR-5.8: Coach rules and fallback compliance."""
        task = Task.objects.create(owner=self.user, title="Algorithmic Complexity")
        context = build_context_block(task, self.user)

        # Rule 1: Redirect off-topic
        reply_offtopic = fallback_coach_reply("What is the recipe for lasagna?", context)
        self.assertIn("Algorithmic Complexity", reply_offtopic)

        # Rule 3: If running focus, reply under 60 words
        context["timer_state"] = "focus"
        reply_focus = fallback_coach_reply("What should I do?", context)
        self.assertLessEqual(len(reply_focus.split()), 60)
