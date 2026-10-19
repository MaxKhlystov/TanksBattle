from django.contrib.auth.mixins import UserPassesTestMixin
from django.views.generic import TemplateView

from .models import Nation, Level, Crewman, Tank, BattleRecord
from .permissions import is_admin


class AllDataView(UserPassesTestMixin, TemplateView):
    template_name = 'base.html'
    raise_exception = True

    def test_func(self):
        return is_admin(self.request)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['nations'] = Nation.objects.all()
        context['levels'] = Level.objects.all()
        context['crewmen'] = Crewman.objects.all()
        context['tanks'] = Tank.objects.all()
        context['battles'] = BattleRecord.objects.all()
        return context
