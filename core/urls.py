from django.urls import path
from . import views

urlpatterns = [
    # Auth & Profile
    path('auth/register/', views.register_view, name='register'),
    path('auth/login/', views.login_view, name='login'),
    path('auth/logout/', views.logout_view, name='logout'),
    path('auth/profile/', views.profile_view, name='profile'),
    path('auth/google/', views.google_demo_auth, name='google_auth'),
    
    # Dashboard
    path('dashboard/', views.dashboard_view, name='dashboard'),
    
    # Tasks
    path('tasks/', views.task_list_create, name='task_list_create'),
    path('tasks/<int:task_id>/', views.task_detail, name='task_detail'),
    path('tasks/<int:task_id>/toggle_status/', views.task_toggle_status, name='task_toggle_status'),
    path('tasks/<int:task_id>/subtasks/', views.subtask_create, name='subtask_create'),
    path('tasks/assign/', views.assign_task_view, name='assign_task'),
    path('learners/', views.learners_list, name='learners_list'),
    path('subtasks/<int:subtask_id>/toggle/', views.subtask_toggle, name='subtask_toggle'),
    
    # Focus Timer
    path('timer/active/', views.active_session_view, name='active_session'),
    path('timer/start/', views.start_timer_view, name='start_timer'),
    path('timer/pause/', views.pause_timer_view, name='pause_timer'),
    path('timer/resume/', views.resume_timer_view, name='resume_timer'),
    path('timer/distraction/', views.distraction_log_view, name='distraction_log'),
    path('timer/stop/', views.stop_timer_view, name='stop_timer'),
    path('timer/complete/', views.complete_timer_view, name='complete_timer'),
    path('timer/skip_break/', views.skip_break_view, name='skip_break'),
    
    # AI Focus Coach (Gemini)
    path('coach/chat/', views.coach_chat_view, name='coach_chat'),
    path('coach/history/<int:task_id>/', views.coach_history_view, name='coach_history'),
    path('coach/clear/<int:task_id>/', views.coach_clear_history_view, name='coach_clear_history'),
    path('coach/breakdown/<int:task_id>/', views.coach_breakdown_view, name='coach_breakdown'),
    path('coach/accept_breakdown/<int:task_id>/', views.coach_accept_breakdown_view, name='coach_accept_breakdown'),
    path('coach/rate/<int:msg_id>/', views.coach_rate_view, name='coach_rate'),
    
    # Achievements & Rewards
    path('achievements/', views.achievements_view, name='achievements'),
    
    # Analytics & CSV
    path('analytics/', views.analytics_view, name='analytics'),
    path('analytics/history/', views.session_history_view, name='session_history'),
    path('analytics/export_csv/', views.export_csv_view, name='export_csv'),
    
    # Leaderboard
    path('leaderboard/', views.leaderboard_view, name='leaderboard'),
    
    # Admin
    path('admin/metrics/', views.admin_metrics_view, name='admin_metrics'),
    path('admin/xp_ledger/', views.admin_xp_ledger_view, name='admin_xp_ledger'),
]
