from tools.calendar.service import get_calendar_service

service = get_calendar_service()

calendars = service.calendarList().list().execute()
print(calendars)
