from .models import Nation, Level, Crewman, Tank, BattleRecord
from django.views.generic import TemplateView

class AllDataView(TemplateView):
    template_name = 'base.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['nations'] = Nation.objects.all()
        context['levels'] = Level.objects.all()
        context['crewmen'] = Crewman.objects.all()
        context['tanks'] = Tank.objects.all()
        context['battles'] = BattleRecord.objects.all()
        return context