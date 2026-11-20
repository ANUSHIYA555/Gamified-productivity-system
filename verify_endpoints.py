import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'focusquest.settings')
django.setup()

from django.test import Client

client = Client()

print("--- 1. Testing Home page / ---")
r1 = client.get('/')
print("Status:", r1.status_code, "Length:", len(r1.content))
assert r1.status_code == 200
assert b'FocusQuest' in r1.content

print("\n--- 2. Testing /api/dashboard/ ---")
r2 = client.get('/api/dashboard/')
print("Status:", r2.status_code)
assert r2.status_code == 200
d = r2.json()
print("User:", d['user']['display_name'], "| Level:", d['user']['level'], "| Total XP:", d['user']['total_xp'])
print("Progress Circle:", d['progress_circle'])
print("Streak:", d['streak'])
print("Recent Tasks:", len(d['tasks']), "items")
print("Featured Badges:", [b['name'] for b in d['featured_achievements']])

print("\n--- 3. Testing /api/tasks/ ---")
r3 = client.get('/api/tasks/')
print("Status:", r3.status_code, "Total Tasks:", len(r3.json()))
assert r3.status_code == 200

print("\n--- 4. Testing /api/coach/chat/ ---")
r4 = client.post('/api/coach/chat/', data={'message': 'What should I do first?'}, content_type='application/json')
print("Status:", r4.status_code)
assert r4.status_code == 200
print("Coach Reply:", r4.json()['coach_message']['content'])

print("\n--- 5. Testing /api/analytics/export_csv/ ---")
r5 = client.get('/api/analytics/export_csv/')
print("Status:", r5.status_code, "Content-Type:", r5['Content-Type'])
assert r5.status_code == 200
assert 'text/csv' in r5['Content-Type']

print("\n--- 6. Testing /api/achievements/ ---")
r6 = client.get('/api/achievements/')
print("Status:", r6.status_code, "Badges Count:", len(r6.json()['badges']))
assert r6.status_code == 200

print("\n--- 7. Testing /api/leaderboard/ ---")
r7 = client.get('/api/leaderboard/')
print("Status:", r7.status_code, "Leaderboard Entries:", len(r7.json()))
assert r7.status_code == 200

print("\n--- 8. Testing /api/admin/metrics/ ---")
r8 = client.get('/api/admin/metrics/')
print("Status:", r8.status_code, "Metrics:", r8.json())
assert r8.status_code == 200

print("\nALL ENDPOINT VERIFICATIONS PASSED SUCCESSFULLY!")
