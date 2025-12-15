# app/integrations/mock_notifications.py
def notify_affected_staff(employee_id, start_date, end_date):
    print(f"[mock_notify] staff {employee_id} absent {start_date} to {end_date}")
    return True

def send_email(to, subject, body):
    print(f"[mock_email] to={to} subject={subject}")
    return True
