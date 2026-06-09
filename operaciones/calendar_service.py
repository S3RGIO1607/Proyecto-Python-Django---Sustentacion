from google.oauth2 import service_account
from googleapiclient.discovery import build

SCOPES = ['https://www.googleapis.com/auth/calendar']

def get_calendar_service():
    creds = service_account.Credentials.from_service_account_file(
        'credentials.json', scopes=SCOPES
    )
    service = build('calendar', 'v3', credentials=creds)
    return service

def crear_evento(reserva):
    print("🔥 SE ESTÁ INTENTANDO CREAR EVENTO")
    
    service = get_calendar_service()

    event = {
        'summary': f"Evento: {reserva.paquete.nombre}",
        'location': 'Bogotá, Colombia',
        'description': f"Cliente: {reserva.usuario.nombre}",
        'start': {
            'dateTime': f"{reserva.fecha_evento}T09:00:00",
            'timeZone': 'America/Bogota',
        },
        'end': {
            'dateTime': f"{reserva.fecha_evento}T18:00:00",
            'timeZone': 'America/Bogota',
        },
    }

    event_result = service.events().insert(
        calendarId='elflacoalex752@gmail.com',  # 👈 TU CORREO
        body=event
    ).execute()

    print("✅ EVENTO CREADO EN GOOGLE:", event_result.get('htmlLink'))

    return event_result