import datetime
from django.core.management.base import BaseCommand
from django.utils import timezone
from core.models import User, Task, Subtask, FocusSession, XPEvent, Badge, UserBadge, Streak

class Command(BaseCommand):
    help = 'Seeds database with realistic initial data matching FocusQuest UI and SRS'

    def handle(self, *args, **options):
        self.stdout.write("Seeding FocusQuest database...")

        # 1. Create or update primary user Anushiya (Learner)
        user, created = User.objects.get_or_create(username='anushiya', defaults={
            'email': 'anushiya@focusquest.app',
            'display_name': 'Anushiya',
            'role': 'Learner',
            'total_xp': 720,
            'level': 12,
            'daily_goal_minutes': 120,
            'focus_length_minutes': 25,
            'short_break_minutes': 5,
            'long_break_minutes': 15,
            'streak_freeze_available': True
        })
        if not created:
            user.display_name = 'Anushiya'
            user.total_xp = 720
            user.level = 12
            user.role = 'Learner'
            user.save()
        user.set_password('password123')
        user.save()

        # 2. Create Task Assigner
        assigner, _ = User.objects.get_or_create(username='prof_alan', defaults={
            'email': 'alan@focusquest.app',
            'display_name': 'Prof. Alan',
            'role': 'Task Assigner',
            'total_xp': 2500,
            'level': 20
        })
        assigner.set_password('password123')
        assigner.save()

        # 3. Create Admin
        admin, _ = User.objects.get_or_create(username='admin', defaults={
            'email': 'admin@focusquest.app',
            'display_name': 'Administrator',
            'role': 'Administrator',
            'is_staff': True,
            'is_superuser': True,
            'total_xp': 5000,
            'level': 35
        })
        admin.set_password('admin123')
        admin.save()

        # 4. Streak
        streak, _ = Streak.objects.get_or_create(user=user)
        streak.current_streak = 7
        streak.longest_streak = 14
        streak.last_active_date = timezone.localdate()
        streak.save()

        # 5. Badges
        badges_info = [
            {
                'code': 'task_master_10',
                'name': 'Task Master',
                'description': 'Complete 50 tasks across all priorities',
                'icon': 'star',
                'badge_color': 'purple',
                'unlock_rule': 'Complete 10 or more tasks',
                'xp_reward': 50
            },
            {
                'code': 'focus_champ_10h',
                'name': 'Focus Champ',
                'description': 'Focus for 10 hrs in deep work',
                'icon': 'crown',
                'badge_color': 'gold',
                'unlock_rule': 'Accumulate 10 hours of focus sessions',
                'xp_reward': 100
            },
            {
                'code': 'streak_7',
                'name': 'On Track',
                'description': 'Maintain 7-day streak',
                'icon': 'calendar',
                'badge_color': 'green',
                'unlock_rule': 'Maintain daily focus streak for 7 consecutive days',
                'xp_reward': 75
            },
            {
                'code': 'first_session',
                'name': 'First Step',
                'description': 'Complete your very first focus session',
                'icon': 'trophy',
                'badge_color': 'blue',
                'unlock_rule': 'Complete 1 focus session',
                'xp_reward': 25
            },
            {
                'code': 'deep_diver',
                'name': 'Deep Diver',
                'description': 'Complete a 50+ minute marathon session',
                'icon': 'zap',
                'badge_color': 'gold',
                'unlock_rule': 'Complete a focus session >= 50 minutes',
                'xp_reward': 50
            }
        ]

        badge_objects = {}
        for b_data in badges_info:
            b_obj, _ = Badge.objects.get_or_create(code=b_data['code'], defaults=b_data)
            badge_objects[b_data['code']] = b_obj

        # Assign featured badges to Anushiya
        for b_code in ['task_master_10', 'focus_champ_10h', 'streak_7']:
            UserBadge.objects.get_or_create(user=user, badge=badge_objects[b_code])

        # 6. Tasks
        Task.objects.filter(owner=user).delete()
        today = timezone.localdate()
        tomorrow = today + datetime.timedelta(days=1)
        next_week = today + datetime.timedelta(days=7)

        tasks_to_create = [
            {
                'title': 'Complete DBMS Assignment',
                'description': 'Implement B+ Tree indexing and SQL query optimization report.',
                'due_date': today,
                'priority': 'High',
                'status': 'Done',
                'completed_at': timezone.now() - datetime.timedelta(hours=2),
                'estimated_sessions': 3,
                'completed_sessions': 3,
                'is_today': True,
                'subtasks': ['Draft schema design', 'Write indexing benchmarks', 'Finalize PDF submission']
            },
            {
                'title': 'Read 2 chapters',
                'description': 'Chapters 4 and 5 of Operating System Concepts (Processes & CPU Scheduling).',
                'due_date': today,
                'priority': 'Medium',
                'status': 'Done',
                'completed_at': timezone.now() - datetime.timedelta(hours=1),
                'estimated_sessions': 2,
                'completed_sessions': 2,
                'is_today': True,
                'subtasks': ['Chapter 4 Process Scheduling', 'Chapter 5 Multi-threading models']
            },
            {
                'title': 'Prepare for OS Exam',
                'description': 'Review deadlock detection algorithms, paging, and memory management strategies.',
                'due_date': tomorrow,
                'priority': 'High',
                'status': 'To do',
                'estimated_sessions': 4,
                'completed_sessions': 1,
                'is_today': True,
                'subtasks': ["Banker's Algorithm practice", 'Page replacement simulation', 'Past paper revision']
            },
            {
                'title': 'Workout for 30 mins',
                'description': 'Cardio, core circuit, and light post-study stretch routine.',
                'due_date': today,
                'priority': 'Low',
                'status': 'To do',
                'estimated_sessions': 1,
                'completed_sessions': 0,
                'is_today': True,
                'subtasks': ['10 min warm-up', '15 min HIIT', '5 min cool-down stretch']
            },
            {
                'title': 'Plan next week',
                'description': 'Set weekly priorities, schedule assignment milestones, and organize lecture slides.',
                'due_date': next_week,
                'priority': 'Medium',
                'status': 'To do',
                'estimated_sessions': 1,
                'completed_sessions': 0,
                'is_today': False,
                'subtasks': ['Review upcoming syllabus', 'Sync calendar deadlines']
            },
            # Additional completed tasks to reflect 6 / 8 tasks on dashboard
            {
                'title': 'Computer Networks Quiz Revision',
                'description': 'TCP/UDP headers, 3-way handshake and subnet calculation review.',
                'due_date': today,
                'priority': 'Medium',
                'status': 'Done',
                'completed_at': timezone.now() - datetime.timedelta(hours=4),
                'estimated_sessions': 2,
                'completed_sessions': 2,
                'is_today': True,
                'subtasks': []
            },
            {
                'title': 'Algorithm Lab Submission: Dijkstra',
                'description': 'Shortest path implementation using min-heap in C++.',
                'due_date': today,
                'priority': 'High',
                'status': 'Done',
                'completed_at': timezone.now() - datetime.timedelta(hours=5),
                'estimated_sessions': 2,
                'completed_sessions': 2,
                'is_today': True,
                'subtasks': []
            },
            {
                'title': 'Software Architecture Notes Summary',
                'description': 'Microservices vs Monolith trade-offs synthesis.',
                'due_date': today,
                'priority': 'Low',
                'status': 'Done',
                'completed_at': timezone.now() - datetime.timedelta(hours=6),
                'estimated_sessions': 1,
                'completed_sessions': 1,
                'is_today': True,
                'subtasks': []
            }
        ]

        created_tasks = []
        for t_info in tasks_to_create:
            subtasks = t_info.pop('subtasks')
            t = Task.objects.create(owner=user, **t_info)
            for st_title in subtasks:
                Subtask.objects.create(task=t, title=st_title, done=(t.status == 'Done'), source='user')
            created_tasks.append(t)

        # 7. Seed Focus Sessions for Weekly Chart (Mon - Sun)
        FocusSession.objects.filter(user=user).delete()
        weekday = today.weekday()
        monday = today - datetime.timedelta(days=weekday)
        minutes_pattern = [45, 75, 90, 50, 85, 110, 135] # Mon - Sun
        
        for idx, mins in enumerate(minutes_pattern):
            session_date = monday + datetime.timedelta(days=idx)
            # Create completed focus session
            FocusSession.objects.create(
                user=user,
                task=created_tasks[0],
                session_type='focus',
                planned_minutes=mins,
                started_at=datetime.datetime.combine(session_date, datetime.time(10, 0), tzinfo=datetime.timezone.utc),
                ended_at=datetime.datetime.combine(session_date, datetime.time(10, 0), tzinfo=datetime.timezone.utc) + datetime.timedelta(minutes=mins),
                status='completed',
                outcome='task_done',
                xp_awarded=mins,
                distraction_count=1 if idx % 2 == 1 else 0
            )

        # 8. Seed XP Ledger Events
        XPEvent.objects.filter(user=user).delete()
        XPEvent.objects.create(user=user, amount=25, reason="Completed 25m Focus Session on DBMS Assignment")
        XPEvent.objects.create(user=user, amount=30, reason="Finished High Priority Task: Complete DBMS Assignment")
        XPEvent.objects.create(user=user, amount=20, reason="Finished Medium Priority Task: Read 2 chapters")
        XPEvent.objects.create(user=user, amount=25, reason="Daily Focus Goal Reached (120m)")
        XPEvent.objects.create(user=user, amount=50, reason="Unlocked Badge: Task Master")

        self.stdout.write(self.style.SUCCESS("FocusQuest successfully seeded!"))
