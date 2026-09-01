import os
import json
import urllib.request
import urllib.error
import uuid

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'stage_project.settings')
import django

django.setup()

email = f"testuser-{uuid.uuid4().hex[:8]}@example.com"
password = "Abcdef1!"

for endpoint, payload in [
    ('http://127.0.0.1:8000/api/auth/register/', {
        'email': email,
        'password': password,
        'first_name': 'Test',
        'last_name': 'User',
        'role': 'user',
    }),
    ('http://127.0.0.1:8000/api/auth/login/', {
        'email': email,
        'password': password,
    }),
]:
    data = json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(endpoint, data=data, headers={'Content-Type': 'application/json'})
    print('\nREQUEST', endpoint, 'PAYLOAD EMAIL', payload['email'])
    try:
        with urllib.request.urlopen(req) as res:
            print('STATUS', res.status)
            print(res.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        print('HTTPError', e.code)
        print(e.read().decode('utf-8'))
    except Exception as ex:
        print('ERROR', ex)
