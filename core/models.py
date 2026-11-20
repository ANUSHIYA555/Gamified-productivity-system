from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils import timezone
import datetime

class User(AbstractUser):
    ROLE_CHOICES = (
        ('Learner', 'Learner'),
        ('Task Assigner', 'Task Assigner'),
        ('Administrator', 'Administrator'),
    )
    
    display_name = models.CharField(max_length=150, default='Anushiya')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='Learner')
    avatar = models.CharField(max_length=255, default='anushiya')
    
    # User Preferences (FR-1.2, FR-3.2, FR-4.7)
    daily_goal_minutes = models.PositiveIntegerField(default=120)
    focus_length_minutes = models.PositiveIntegerField(default=25)
    short_break_minutes = models.PositiveIntegerField(default=5)
    long_break_minutes = models.PositiveIntegerField(default=15)
    long_break_interval = models.PositiveIntegerField(default=4)
    
    # Gamification Stats (FR-4.1 - FR-4.4)
    total_xp = models.PositiveIntegerField(default=720)
    level = models.PositiveIntegerField(default=12)
    
    # Streak Freeze (FR-4.9)
    streak_freeze_available = models.BooleanField(default=True)
    streak_freeze_last_reset = models.DateField(default=datetime.date.today)
    
    def __str__(self):
        return f"{self.username} ({self.role})"


class Task(models.Model):
    PRIORITY_CHOICES = (
        ('Low', 'Low'),
        ('Medium', 'Medium'),
        ('High', 'High'),
    )
    STATUS_CHOICES = (
        ('To do', 'To do'),
        ('In progress', 'In progress'),
        ('Done', 'Done'),
    )
    
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='tasks')
    assigned_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_tasks'
    )
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, default='')
    due_date = models.DateField(null=True, blank=True)
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default='Medium')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='To do')
    estimated_sessions = models.PositiveIntegerField(default=2)
    completed_sessions = models.PositiveIntegerField(default=0)
    is_today = models.BooleanField(default=False)
    order_index = models.PositiveIntegerField(default=0)
    
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['status', 'due_date', '-priority']

    def __str__(self):
        return self.title


class Subtask(models.Model):
    SOURCE_CHOICES = (
        ('user', 'User'),
        ('ai', 'AI Coach'),
    )
    
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name='subtasks')
    title = models.CharField(max_length=255)
    done = models.BooleanField(default=False)
    source = models.CharField(max_length=10, choices=SOURCE_CHOICES, default='user')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.title} ({'Done' if self.done else 'Pending'})"


class FocusSession(models.Model):
    SESSION_TYPES = (
        ('focus', 'Focus'),
        ('short_break', 'Short Break'),
        ('long_break', 'Long Break'),
    )
    STATUS_CHOICES = (
        ('idle', 'Idle'),
        ('running', 'Running'),
        ('paused', 'Paused'),
        ('completed', 'Completed'),
        ('break', 'Break'),
        ('abandoned', 'Abandoned'),
    )
    OUTCOME_CHOICES = (
        ('none', 'None'),
        ('task_done', 'Task Done'),
        ('more_work_needed', 'More Work Needed'),
        ('blocked', 'Blocked'),
    )
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='focus_sessions')
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name='sessions')
    session_type = models.CharField(max_length=20, choices=SESSION_TYPES, default='focus')
    planned_minutes = models.PositiveIntegerField(default=25)
    
    # Timestamp tracking for drift-free and persistence across tab reloads (FR-3.4, NFR-3)
    started_at = models.DateTimeField(default=timezone.now)
    paused_at = models.DateTimeField(null=True, blank=True)
    total_paused_seconds = models.PositiveIntegerField(default=0)
    ended_at = models.DateTimeField(null=True, blank=True)
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='running')
    distraction_count = models.PositiveIntegerField(default=0)
    outcome = models.CharField(max_length=20, choices=OUTCOME_CHOICES, default='none')
    xp_awarded = models.PositiveIntegerField(default=0)

    def remaining_seconds(self):
        if self.status in ['completed', 'abandoned']:
            return 0
        total_planned_secs = self.planned_minutes * 60
        now = timezone.now()
        if self.status == 'paused' and self.paused_at:
            elapsed = (self.paused_at - self.started_at).total_seconds() - self.total_paused_seconds
        else:
            elapsed = (now - self.started_at).total_seconds() - self.total_paused_seconds
        remaining = max(0, int(total_planned_secs - elapsed))
        return remaining

    def elapsed_minutes(self):
        total_planned_secs = self.planned_minutes * 60
        rem = self.remaining_seconds()
        return max(0, int((total_planned_secs - rem) / 60))

    def __str__(self):
        return f"{self.user.username} - {self.task.title} ({self.status})"


class XPEvent(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='xp_events')
    amount = models.IntegerField()
    reason = models.CharField(max_length=255)
    session = models.ForeignKey(FocusSession, on_delete=models.SET_NULL, null=True, blank=True)
    task = models.ForeignKey(Task, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.username}: +{self.amount} XP ({self.reason})"


class Badge(models.Model):
    code = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=100)
    description = models.TextField()
    icon = models.CharField(max_length=50, default='award') # trophy, flame, star, crown, check-circle, zap
    badge_color = models.CharField(max_length=20, default='purple') # purple, gold, green, blue
    unlock_rule = models.CharField(max_length=255)
    xp_reward = models.PositiveIntegerField(default=50)

    def __str__(self):
        return self.name


class UserBadge(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='badges')
    badge = models.ForeignKey(Badge, on_delete=models.CASCADE, related_name='awarded_users')
    earned_at = models.DateTimeField(auto_now_add=True)
    notified = models.BooleanField(default=False)

    class Meta:
        unique_together = ('user', 'badge')

    def __str__(self):
        return f"{self.user.username} earned {self.badge.name}"


class Streak(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='streak')
    current_streak = models.PositiveIntegerField(default=7)
    longest_streak = models.PositiveIntegerField(default=7)
    last_active_date = models.DateField(null=True, blank=True)

    def __str__(self):
        return f"{self.user.username} Streak: {self.current_streak} days"


class ChatMessage(models.Model):
    ROLE_CHOICES = (
        ('user', 'User'),
        ('coach', 'Focus Coach'),
    )
    THUMBS_CHOICES = (
        ('none', 'None'),
        ('up', 'Thumbs Up'),
        ('down', 'Thumbs Down'),
    )
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='chat_messages')
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name='chat_messages', null=True, blank=True)
    role = models.CharField(max_length=10, choices=ROLE_CHOICES)
    content = models.TextField()
    thumbs_rating = models.CharField(max_length=10, choices=THUMBS_CHOICES, default='none')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f"[{self.role}] {self.content[:30]}..."
