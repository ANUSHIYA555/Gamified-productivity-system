from rest_framework import serializers
from .models import User, Task, Subtask, FocusSession, XPEvent, Badge, UserBadge, Streak, ChatMessage
from .gamification import calculate_level_info

class SubtaskSerializer(serializers.ModelSerializer):
    class Meta:
        model = Subtask
        fields = ['id', 'title', 'done', 'source', 'created_at']

class TaskSerializer(serializers.ModelSerializer):
    subtasks = SubtaskSerializer(many=True, read_only=True)
    assigned_by_name = serializers.CharField(source='assigned_by.display_name', read_only=True)
    owner_name = serializers.CharField(source='owner.display_name', read_only=True)
    is_overdue = serializers.SerializerMethodField()

    class Meta:
        model = Task
        fields = [
            'id', 'owner', 'owner_name', 'assigned_by', 'assigned_by_name',
            'title', 'description', 'due_date', 'priority', 'status',
            'estimated_sessions', 'completed_sessions', 'is_today',
            'completed_at', 'subtasks', 'is_overdue', 'created_at'
        ]
        read_only_fields = ['owner', 'completed_at', 'created_at']

    def get_is_overdue(self, obj):
        import datetime
        from django.utils import timezone
        if obj.due_date and obj.status != 'Done':
            return obj.due_date < timezone.localdate()
        return False

class UserSerializer(serializers.ModelSerializer):
    level_info = serializers.SerializerMethodField()
    current_streak = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'display_name', 'role', 'avatar',
            'daily_goal_minutes', 'focus_length_minutes', 'short_break_minutes',
            'long_break_minutes', 'long_break_interval', 'total_xp', 'level',
            'level_info', 'current_streak', 'streak_freeze_available'
        ]
        read_only_fields = ['total_xp', 'level']

    def get_level_info(self, obj):
        return calculate_level_info(obj.total_xp)

    def get_current_streak(self, obj):
        try:
            return obj.streak.current_streak
        except Exception:
            return 0

class FocusSessionSerializer(serializers.ModelSerializer):
    task_title = serializers.CharField(source='task.title', read_only=True)
    task_priority = serializers.CharField(source='task.priority', read_only=True)
    remaining_seconds = serializers.IntegerField(read_only=True)
    elapsed_minutes = serializers.IntegerField(read_only=True)

    class Meta:
        model = FocusSession
        fields = [
            'id', 'task', 'task_title', 'task_priority', 'session_type',
            'planned_minutes', 'started_at', 'paused_at', 'ended_at',
            'status', 'distraction_count', 'outcome', 'xp_awarded',
            'remaining_seconds', 'elapsed_minutes'
        ]

class XPEventSerializer(serializers.ModelSerializer):
    task_title = serializers.CharField(source='task.title', read_only=True)
    
    class Meta:
        model = XPEvent
        fields = ['id', 'amount', 'reason', 'task_title', 'created_at']

class BadgeSerializer(serializers.ModelSerializer):
    is_earned = serializers.BooleanField(default=False)
    earned_at = serializers.DateTimeField(default=None)

    class Meta:
        model = Badge
        fields = ['id', 'code', 'name', 'description', 'icon', 'badge_color', 'unlock_rule', 'xp_reward', 'is_earned', 'earned_at']

class ChatMessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ChatMessage
        fields = ['id', 'role', 'content', 'thumbs_rating', 'created_at']
