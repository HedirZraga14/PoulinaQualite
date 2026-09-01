from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.http import HttpResponseRedirect
from django.shortcuts import render
from django.urls import reverse

from .models import Branch, DateDim, Evaluation, Laboratoire, Sector, User

admin.site.site_header = 'Administration Stage'
admin.site.site_title = 'Administration Stage'
admin.site.index_title = 'Gestion des utilisateurs'


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    model = User
    ordering = ('email',)
    list_display = ('email', 'role', 'branch', 'is_staff', 'is_active')
    list_filter = ('role', 'is_staff', 'is_superuser', 'is_active')
    search_fields = ('email', 'first_name', 'last_name')
    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Personal info', {'fields': ('first_name', 'last_name', 'role', 'branch')}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Important dates', {'fields': ('last_login', 'date_joined')}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'password1', 'password2', 'is_staff', 'is_active'),
        }),
    )


@admin.register(Branch)
class BranchAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'sector')
    search_fields = ('code', 'name')
    list_filter = ('sector',)
    ordering = ('code',)
    actions = ['change_sector_action']

    @admin.action(description='Changer le secteur des filiales sélectionnées')
    def change_sector_action(self, request, queryset):
        if 'sector_id' in request.POST:
            sector_id = request.POST.get('sector_id')
            if sector_id:
                try:
                    sector = Sector.objects.get(pk=sector_id)
                    updated = queryset.update(sector=sector)
                    self.message_user(request, f'{updated} filiale(s) mise(s) à jour vers le secteur « {sector.name} ».')
                except Sector.DoesNotExist:
                    self.message_user(request, 'Secteur invalide.', level='error')
            return HttpResponseRedirect(reverse('admin:user_branch_changelist'))

        sectors = Sector.objects.all()
        return render(request, 'admin/branch_change_sector.html', {
            'branches': queryset,
            'sectors': sectors,
            'action_checkbox_name': admin.helpers.ACTION_CHECKBOX_NAME,
        })


@admin.register(Sector)
class SectorAdmin(admin.ModelAdmin):
    list_display = ('name', 'manager')
    search_fields = ('name',)
    ordering = ('name',)


@admin.register(Laboratoire)
class LaboratoireAdmin(admin.ModelAdmin):
    list_display = ('id', 'name')
    search_fields = ('name',)
    ordering = ('name',)


@admin.register(DateDim)
class DateDimAdmin(admin.ModelAdmin):
    list_display = ('id', 'mois', 'trimestre', 'annee')
    list_filter = ('annee', 'trimestre')
    search_fields = ('mois', 'annee')
    ordering = ('annee', 'mois')


@admin.register(Evaluation)
class EvaluationAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'filiale',
        'laboratoire',
        'date',
        'axe_evaluation',
        'note',
        'moy_ponderation',
        'tx_conformite',
        'created_at',
    )
    list_filter = ('date__annee', 'date__trimestre', 'laboratoire', 'filiale__sector')
    search_fields = ('axe_evaluation', 'criteres', 'observations', 'filiale__name', 'laboratoire__name')
    autocomplete_fields = ('filiale', 'laboratoire', 'date', 'user')
    ordering = ('-created_at',)
