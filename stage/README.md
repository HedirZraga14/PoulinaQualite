# Stage project

Minimal Django project with an email-based `User` entity.

Setup (Windows PowerShell):

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python manage.py makemigrations
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Using SQL Server in real time:

1. Install the ODBC Driver 18 for SQL Server, then install the Python dependencies:

```powershell
pip install -r requirements.txt
```

2. Copy `.env.example` to `.env`, then set the SQL Server parameters. SQL Server is enabled by default and the example below uses Windows authentication:

```powershell
Copy-Item .env.example .env
```

Main variables:

```powershell
$env:DB_ENGINE='sqlserver'
$env:MSSQL_NAME='stage_db'
$env:MSSQL_HOST='HEDIRE\MSSQLSERVER05'
$env:MSSQL_PORT='1433'
$env:MSSQL_TRUSTED_CONNECTION='yes'
```

For SQL Server authentication, also set:

```powershell
$env:MSSQL_TRUSTED_CONNECTION='no'
$env:MSSQL_USER='sa'
$env:MSSQL_PASSWORD='your-password'
```

3. Run migrations and start the server:

```powershell
python manage.py migrate
python manage.py runserver
```

4. Quick live connection check:

```powershell
python manage.py shell -c "from django.db import connection; c=connection.cursor(); c.execute('SELECT DB_NAME(), @@SERVERNAME'); print(c.fetchone())"
```

Security: use environment variables or a secrets manager for production; do not hard-code credentials in `stage_project/settings.py`.
