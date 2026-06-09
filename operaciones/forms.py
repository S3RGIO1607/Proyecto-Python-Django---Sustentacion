from django import forms
from .models import ReservaEvento

class ReservaEventoForm(forms.ModelForm):
    class Meta:
        model = ReservaEvento
        fields = ['paquete', 'lugar', 'menu_comida', 'fecha_evento', 'hora_inicio', 'asistentes']
        widgets = {
            'fecha_evento': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'hora_inicio': forms.TimeInput(attrs={'type': 'time', 'class': 'form-control'}),
            'asistentes': forms.NumberInput(attrs={'class': 'form-control'}),
            'paquete': forms.Select(attrs={'class': 'form-select'}),
            'lugar': forms.Select(attrs={'class': 'form-select'}),
            'menu_comida': forms.Select(attrs={'class': 'form-select'}),
        }
