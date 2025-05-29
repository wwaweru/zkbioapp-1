@echo off
cd /d "C:\Users\Walter\zkbioapp"
call .zkbiosync\Scripts\activate
python manage.py start_scheduler
pause