from django.contrib.auth.mixins import UserPassesTestMixin
from django.db.models import Count, F
from django.views.generic import TemplateView

from .models import Nation, Level, Crewman, Tank, BattleRecord
from .permissions import has_2fa


class AllDataView(UserPassesTestMixin, TemplateView):
    template_name = 'base.html'
    raise_exception = True

    def test_func(self):
        user = self.request.user
        return user.is_authenticated and user.is_staff and has_2fa(self.request)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['nations'] = Nation.objects.all()
        context['levels'] = Level.objects.all()
        context['crewmen'] = Crewman.objects.select_related('user').annotate(
            free_slots=F('garage_slots') - Count('tanks')
        )
        context['tanks'] = Tank.objects.select_related('owner__user', 'nation', 'level')
        context['battles'] = BattleRecord.objects.select_related(
            'tank', 'crewman__user', 'battle_level'
        )
        return context