# -*- coding: utf-8 -*-
import datetime

from django import forms
from django.contrib.auth.models import User, Group
from django.core.exceptions import ObjectDoesNotExist
from django.db import models
from django.db.models import Q
from django.forms import formsets
from django.forms.formsets import formset_factory, BaseFormSet
from django.forms.models import model_to_dict, inlineformset_factory

from common.forms import UnclearDateField
from cemetery_app.models import Cemetery, Operation, Place, Burial, UserProfile, Service, ServicePosition, Comment
from geo.models import Location, Country, Region, City, Street
from organizations.models import Doverennost, Organization, Agent, BankAccount
from persons.models import Person, DeathCertificate, PersonID, DocumentSource
from utils.models import PER_PAGE_VALUES, ORDER_BY_VALUES

class UserChoiceForm(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        if obj.get_full_name():
            return obj.get_full_name()
        try:
            return u'%s' % obj.person or obj.username
        except:
            return obj.username

CREATORS_QS = User.objects.filter(Q(is_superuser=True) | Q(user_permissions__codename='add_burial') | Q(groups__permissions__codename='add_burial')).distinct()

class SearchForm(forms.Form):
    """
    Форма поиска на главной странице.
    """
    CUSTOMER_TYPES = (
        ('', u"Все"),
        ('client_person', u"ФЛ"),
        ('client_organization', u"ЮЛ"),
    )

    fio = forms.CharField(required=False, max_length=100, label="ФИО")
    no_last_name = forms.BooleanField(required=False, initial=False, label=u"Неизв.")
    birth_date_from = forms.DateField(required=False, label="Дата рождения с")
    birth_date_to = forms.DateField(required=False, label="по")
    death_date_from = forms.DateField(required=False, label="Дата смерти с")
    death_date_to = forms.DateField(required=False, label="по")
    burial_date_from = forms.DateField(required=False, label="Дата захоронения с")
    burial_date_to = forms.DateField(required=False, label="по")
    account_number_from = forms.CharField(required=False, max_length=16, label="Номер от")
    account_number_to = forms.CharField(required=False, max_length=16, label="до")
    customer = forms.CharField(required=False, max_length=30, label="Заказчик")
    customer_type = forms.ChoiceField(required=False, choices=CUSTOMER_TYPES, label=u"Тип зак.")
    responsible = forms.CharField(required=False, max_length=30, label="Ответственный")
    operation = forms.ModelChoiceField(required=False, queryset=Operation.objects.all(), label="Услуга", empty_label="Все")
    cemetery = forms.ModelChoiceField(required=False, queryset=Cemetery.objects.all(), empty_label="Все", label="Кладбища")
    area = forms.CharField(required=False, max_length=9, label="Участок")
    row = forms.CharField(required=False, max_length=9, label="Ряд")
    seat = forms.CharField(required=False, max_length=9, label="Место")
    no_exhumated = forms.BooleanField(required=False, initial=False, label=u"Убрать эксгум.")
    deleted = forms.BooleanField(required=False, initial=False, label=u"Корзина")
    unowned = forms.BooleanField(required=False, initial=False, label=u"Бесхоз.")
    no_responsible = forms.BooleanField(required=False, initial=False, label=u"Без отв.")

    records_order_by = forms.ChoiceField(required=False, choices=ORDER_BY_VALUES, label=u"Сортировка по")
    per_page = forms.ChoiceField(required=False, choices=PER_PAGE_VALUES, label=u"Записей на страницу")
    creator = UserChoiceForm(required=False, label=u"Автор", queryset=CREATORS_QS)

class PlaceForm(forms.ModelForm):
    class Meta:
        model = Place
        exclude = ['rooms', 'unowned']

    def clean_seat(self):
        a = self.cleaned_data['seat']
        if not a:
            return a
        if len(a) != 8:
            raise forms.ValidationError(u"Необходимо ровно 8 цифр")
        if not a.isdigit():
            raise forms.ValidationError(u"Допустимы только цифры")
        if int(a[:4]) > datetime.datetime.now().year:
            raise forms.ValidationError(u"Номер больше текущего года")
        if a.endswith('0000'):
            raise forms.ValidationError(u"Последние 4 цифры не могут быть нулями")
        return a

    def save(self, user=None, commit=True):
        filter_fields = ['cemetery', 'row', 'area', 'seat']
        data = dict(filter(lambda i: i[0] in filter_fields, self.cleaned_data.items()))
        try:
            if self.cleaned_data['seat']:
                try:
                    return Place.objects.get(**data)
                except Place.MultipleObjectsReturned:
                    return Place.objects.filter(**data)[0]
        except Place.DoesNotExist:
            pass

        place = super(PlaceForm, self).save(commit=False)
        place.creator = user
        if commit:
            place.save()
        return place

class BurialForm(forms.ModelForm):
    allow_duplicates = forms.BooleanField(required=False, initial=False, label=u"Да, сохранить дубликат")
    responsible = forms.ModelChoiceField(queryset=Person.objects.all(), widget=forms.HiddenInput, required=False)

    class Meta:
        model = Burial
        exclude = ['payment_type', ]
        widgets = {
            'place': forms.HiddenInput(),
            'person': forms.HiddenInput(),
            'client_person': forms.HiddenInput(),
            'client_organization': forms.HiddenInput(),
            'doverennost': forms.HiddenInput(),
            'agent': forms.HiddenInput(),
        }

    def clean_account_number(self):
        a = self.cleaned_data['account_number']
        if not a:
            return a
        if len(a) != 8:
            raise forms.ValidationError(u"Необходимо ровно 8 цифр")
        if not a.isdigit():
            raise forms.ValidationError(u"Допустимы только цифры")
        if a.endswith('0000'):
            raise forms.ValidationError(u"Последние 4 цифры не могут быть нулями")


        place = Place.objects.get(pk=self.data['place'])
        burials = Burial.objects.all().filter(place__cemetery=place.cemetery)
        if self.instance:
            burials = burials.exclude(pk=self.instance.pk)
        try:
            burials.filter(account_number=a)[0]
        except IndexError:
            return a
        else:
            raise forms.ValidationError(u"Этот номер уже используется")

    def clean(self):
        account_number = self.cleaned_data.get('account_number')
        if account_number and self.cleaned_data.get('date_fact'):
            if str(account_number)[:4] != str(self.cleaned_data['date_fact'].year):
                raise forms.ValidationError(u"Номер не соответствует дате")

        if not account_number:
            try:
                account_number = unicode(int(Burial.objects.filter(deleted=False).order_by('-account_number')[0].account_number) + 1)
            except:
                pass

        customer = self.cleaned_data.get('client_person')
        try:
            personid = customer and customer.personid or None
        except ObjectDoesNotExist:
            personid = None
        if customer and personid and personid.date and self.cleaned_data.get('date_fact'):
            try:
                if personid.date < self.cleaned_data['date_fact'] - datetime.timedelta(75 * 365):
                    raise forms.ValidationError(u"Дата документа заказчика раньше 75 лет до даты захоронения")
            except ObjectDoesNotExist:
                pass

        place = self.cleaned_data.get('place')
        if place and place.seat:
            if self.cleaned_data.get('operation').op_type == u'Захоронение':
                others = Burial.objects.filter(place=place).select_related()
                if self.instance and self.instance.pk:
                    others = others.exclude(pk=self.instance.pk)
                if any(filter(lambda o: not o.operation.is_empty(), others)):
                    raise forms.ValidationError(u"Место не пустое, Операция не должна быть \"Захоронение\"")

            if account_number and account_number < place.seat:
                raise forms.ValidationError(u"Рег. № меньше номера места")

        operation = self.cleaned_data.get('operation')
        if operation and place:
            try:
                instance_op = self.instance.operation
            except ObjectDoesNotExist:
                instance_op = None
            old_empty = not self.instance or not instance_op or instance_op.is_empty()
            try:
                instance_place = self.instance.place
            except ObjectDoesNotExist:
                instance_place = None
            global_change = not self.instance or not self.instance.pk or instance_op != operation or instance_place != place
            rooms_free = place.rooms_free
            if not operation.is_empty() and old_empty and rooms_free <= 0 and global_change:
                raise forms.ValidationError(u"Нет свободных могил в указанном месте")

            if operation.is_empty() and not place.seat:
                raise forms.ValidationError(u"Для указанного типа захоронения необходим номер места")

            if operation.is_empty() and self.cleaned_data['date_fact']:
                min_date = min([b.date_fact for b in place.burial_set.all() if not b.operation.is_empty()], None)
                if min_date and self.cleaned_data['date_fact'] < min_date:
                    raise forms.ValidationError(u"В указанном месте должно быть хотя бы одно Захоронение раньше, чем это Подзахоронение")

        if self.cleaned_data['date_fact'] and self.cleaned_data['exhumated_date']:
            if self.cleaned_data['date_fact'] >= self.cleaned_data['exhumated_date']:
                raise forms.ValidationError(u"Дата эксгумации должна быть позже даты захоронения")

        place = self.cleaned_data.get('place')
        if account_number:
            an = account_number
        else:
            an = Burial(place=self.cleaned_data['place']).generate_account_number()
        if an and place and place.seat and place.seat != an and operation.op_type == u'Захоронение':
            raise forms.ValidationError(u"Для Захоронений номер места должен совпадать с учетным номером захоронения")

        if self.cleaned_data['date_fact'] and self.cleaned_data['doverennost']:
            if self.cleaned_data['date_fact'] >= datetime.date.today():
                if self.cleaned_data['agent']:
                    dov =  self.cleaned_data['doverennost']
                    if not dov or not dov.number or not dov.issue_date or not dov.expire_date:
                        raise forms.ValidationError(u"Для неархивных захоронений необходимы данные доверенности агента")

        if self.cleaned_data['date_fact'] and self.cleaned_data['doverennost']:
            dov = self.cleaned_data['doverennost']
            doc_date = min(self.cleaned_data['date_fact'], datetime.date.today())
            if dov.expire_date and doc_date > dov.expire_date:
                raise forms.ValidationError(u"Дата окончания действия доверенности раньше даты захоронения")
            if dov.issue_date and self.cleaned_data['date_fact'] < dov.issue_date:
                raise forms.ValidationError(u"Дата выпуска доверенности позже даты захоронения")

        person = self.cleaned_data.get('person')
        if person and person.first_name or person.first_name or person.first_name:
            kwargs = dict(
                date_fact = self.cleaned_data['date_fact'],
                place__cemetery = self.cleaned_data['place'].cemetery,
                person__first_name = self.cleaned_data['person'].first_name,
                person__last_name = self.cleaned_data['person'].last_name,
                person__middle_name = self.cleaned_data['person'].middle_name,
                person__birth_date = self.cleaned_data['person'].birth_date,
                person__death_date = self.cleaned_data['person'].death_date,
            )
            duplicates = Burial.objects.filter(**kwargs)
            if self.instance and self.instance.pk:
                duplicates = duplicates.exclude(pk=self.instance.pk)
            if duplicates.exists() and not self.cleaned_data['allow_duplicates']:
                self.duplicates_found = True
                self.duplicates_list = duplicates
                raise forms.ValidationError(u"Обнаружены дубликаты")

        return self.cleaned_data

    def __init__(self, *args, **kwargs):
        instance = kwargs.get('instance')
        if instance and instance.pk and instance.place and instance.place.responsible:
            kwargs.setdefault('initial', {}).update({
                'responsible': instance.place.responsible,
            })
        super(BurialForm, self).__init__(*args, **kwargs)

    def save(self, commit=True):
        burial = super(BurialForm, self).save(commit=False)
        if burial.place and self.cleaned_data.get('responsible'):
            if burial.place.unowned:
                burial.place.unowned = False
            burial.place.responsible = self.cleaned_data['responsible']
            burial.place.save()
        if commit:
            burial.save()

        if burial.place and not burial.place.seat:
            burial.place.seat = unicode(burial.account_number or burial.pk)
            burial.place.save()

        return burial

class PersonForm(forms.ModelForm):
    instance = forms.ChoiceField(widget=forms.RadioSelect, required=False)
    birth_date = UnclearDateField(label=u"Дата рождения", required=False)
    skip_last_name = forms.BooleanField(label=u"Фамилия не известна", initial=False, required=False)

    INSTANCE_CHOICES = [
        ('', u'Не выбрано'),
        ('NEW', u'Новый'),
    ]

    class Meta:
        model = Person
        widgets = {
            'phones': forms.TextInput(),
        }

    def __init__(self, dead=None, need_name=False, *args, **kwargs):
        data = dict(kwargs.get('data') or {})
        instance_pk = data.get('instance')
        self.need_name = need_name
        if instance_pk and instance_pk not in [None, '', 'NEW']:
            kwargs['instance'] = Person.objects.get(pk=instance_pk)
            kwargs['instance'].birth_date = kwargs['instance'].unclear_birth_date

            real_initial = kwargs.get('initial', {}).copy()
            kwargs['initial'] = model_to_dict(kwargs['instance'], [], [])
            kwargs['initial'].update({'instance': instance_pk})
            if data and not data.get('last_name') and not data.get('skip_last_name'):
                old_data = dict(kwargs['data'].copy())
                old_data.update(kwargs['initial'])
                kwargs['data'] = old_data
            kwargs['initial'].update(real_initial)

        super(PersonForm, self).__init__(*args, **kwargs)
        self.data = dict(self.data.items())
        if not any(self.data.values()) or self.data.keys() == ['instance']:
            if not self.initial.keys() == ['death_date']:
                self.data = self.initial.copy()
        if self.data and self.data.get('last_name') or self.data.get('instance') or self.data.get('skip_last_name'):
            person_kwargs = {
                'first_name__istartswith': self.data.get('first_name', ''),
                'last_name__istartswith': self.data.get('last_name', ''),
                'middle_name__istartswith': self.data.get('middle_name', ''),
            }
            if self.data.get('instance') not in [None, '', 'NEW']:
                self.instance = Person.objects.get(pk=self.data.get('instance'))
                self.fields['instance'].choices = self.INSTANCE_CHOICES + [
                    (str(p.pk), self.full_person_data(p)) for p in Person.objects.filter(pk=self.data.get('instance'))
                ]
                if not self.data.get('selected'):
                    self.data = None
                    self.is_bound = False
                    dead = self.initial and self.initial.get('death_date')
                    self.initial = model_to_dict(self.instance, self._meta.fields, self._meta.exclude)
                    self.initial.update({
                        'instance': self.instance.pk,
                        'death_date': dead,
                        'birth_date': self.instance.unclear_birth_date
                    })
            else:
                if self.data.get('instance') == 'NEW':
                    if dead and not self.data.get('death_date') :
                        self.data['death_date'] = datetime.date.today() - datetime.timedelta(1)
                if self.data and self.data.get('skip_last_name'):
                    self.fields['instance'].choices = self.INSTANCE_CHOICES
                else:
                    self.fields['instance'].choices = self.INSTANCE_CHOICES + [
                        (str(p.pk), self.full_person_data(p)) for p in Person.objects.filter(**person_kwargs)
                    ]
        else:
            self.fields['instance'].widget = forms.HiddenInput()

        if self.instance and not self.instance.last_name:
            self.fields['last_name'].required = False
            self.fields['skip_last_name'].initial = True

        if self.data and self.data.get('skip_last_name'):
            self.fields['last_name'].required = False

    def full_person_data(self, p):
        dates = ''
        if p.get_birth_date():
            if p.death_date:
                dates = '%s - %s' % (p.get_birth_date().strftime('%d.%m.%Y'), p.death_date.strftime('%d.%m.%Y'))
            else:
                dates = u'род. %s' % p.get_birth_date().strftime('%d.%m.%Y')
        else:
            if p.death_date:
                dates = u'ум. %s' % p.death_date.strftime('%d.%m.%Y')

        if dates:
            dates = u'%s, ' % dates

        params = (p.full_name_complete(), dates, p.address or u'', self.get_person_status(p))
        return u'%s (%sадрес: %s), Статус: %s' % params

    def get_person_status(self, p):
        if p.buried.filter(exhumated_date__isnull=False).count() > 0:
            return u'Эксгумированный'
        if p.buried.all().count() > 0:
            return u'Усопший'
        if p.ordr_customer.all().count() > 0:
            return u'Заказчик'
        if p.place_set.all().count() > 0:
            return u'Ответственный'
        return u'Н/д'

    def clean_birth_date(self):
        if self.cleaned_data.get('birth_date') and self.cleaned_data['birth_date'] >= datetime.date.today():
            raise forms.ValidationError(u"Дата должна быть раньше текущей")
        return self.cleaned_data['birth_date']

    def clean_death_date(self):
        if self.cleaned_data.get('death_date') and self.cleaned_data['death_date'] > datetime.date.today():
            raise forms.ValidationError(u"Дата должна быть не позже текущей")
        return self.cleaned_data['death_date']

    def clean(self):
        if self.cleaned_data.get('birth_date') and self.cleaned_data.get('death_date'):
            if self.cleaned_data['birth_date'] > self.cleaned_data['death_date']:
                raise forms.ValidationError(u"Дата рождения позже даты смерти")
            if self.cleaned_data['birth_date'] < self.cleaned_data['death_date'] - datetime.timedelta(365*150):
                raise forms.ValidationError(u"Дата рождения раньше 150 лет до даты смерти")

        if self.need_name and self.cleaned_data['last_name'].replace('*', '').replace(' ', '') == '':
            raise forms.ValidationError(u"Нужно указать ФИО")

        return self.cleaned_data

    def is_valid(self):
        if not self.is_bound or not self.data:
            return False

        if not self.data.get('instance'):
            return False

        if not self.data.get('selected'):
            return False

        return super(PersonForm, self).is_valid()

    def is_selected(self):
        is_old = self.instance and self.instance.pk
        is_new = self.data and self.data.get('instance')
        return is_old or is_new or False

    def save(self, location=None, commit=True):
        person = super(PersonForm, self).save(commit=False)
        if self.instance:
            person.pk = self.instance.pk
        if self.cleaned_data.get('skip_last_name') and not self.cleaned_data.get('last_name'):
            person.last_name = ''
        person.address = location
        person.birth_date_no_month = person.birth_date and self.fields['birth_date'].widget.no_month or False
        person.birth_date_no_day = person.birth_date and self.fields['birth_date'].widget.no_day or False
        if commit:
            person.save()
        return person

class LocationForm(forms.ModelForm):
    country_name = forms.CharField(max_length=255, widget=forms.TextInput(attrs={'class': 'autocomplete'}), label=u"Страна")
    region_name = forms.CharField(max_length=255, widget=forms.TextInput(attrs={'class': 'autocomplete'}), label=u"Область")
    city_name = forms.CharField(max_length=255, widget=forms.TextInput(attrs={'class': 'autocomplete'}), label=u"Город")
    street_name = forms.CharField(max_length=255, widget=forms.TextInput(attrs={'class': 'autocomplete'}), required=False, label=u"Улица")

    class Meta:
        model = Location
        widgets = {
            'country': forms.HiddenInput(),
            'region': forms.HiddenInput(),
            'city': forms.HiddenInput(),
            'street': forms.HiddenInput(),
        }

    def __init__(self, person=None, *args, **kwargs):
        kwargs.setdefault('initial', {})
        if person and person.address:
            kwargs['initial'] = dict(kwargs['initial']).copy()
            kwargs.update({'instance': person.address})
            if person.address.country:
                kwargs['initial'].update({
                    'country_name': person.address.country.name,
                })
            if person.address.region:
                kwargs['initial'].update({
                    'region_name': person.address.region.name,
                })
            if person.address.city:
                kwargs['initial'].update({
                    'city_name': person.address.city.name,
                })
            if person.address.street:
                kwargs['initial'].update({
                    'street_name': person.address.street.name,
                })
        if kwargs.get('instance', {}):
            l = kwargs.get('instance', {})
            street = l.street
            city = l.city or (street and street.city)
            region = l.region or (city and city.region)
            country = l.country or (region and region.country)
            kwargs.setdefault('initial', {}).update(
                country_name=country and country.name,
                region_name=region and region.name,
                city_name=city and city.name,
                street_name=street and street.name,
            )

        def intellectual_get_or_create(data_name, ModelKlass, **kwargs):
            """
            Not so intellectual yet
            """
            dn = data_name.strip()
            try:
                return ModelKlass.objects.get(name=dn, **kwargs)
            except ModelKlass.MultipleObjectsReturned:
                return ModelKlass.objects.filter(name=dn, **kwargs)[0]
            except ModelKlass.DoesNotExist:
                try:
                    return ModelKlass.objects.filter(name__iexact=dn, **kwargs)[0]
                except IndexError:
                    return ModelKlass.objects.create(name=dn, **kwargs)

        if kwargs.get('data', {}):
            kwargs['data'] = kwargs['data'] and kwargs['data'].copy() or {}
            if kwargs['data'].get('country_name').strip():
                d = kwargs['data']

                country = intellectual_get_or_create(d['country_name'], Country)
                kwargs['data']['country'] = country.pk
                if kwargs.get('data', {}).get('region_name').strip():
                    region = intellectual_get_or_create(d['region_name'], Region, country=country)
                    kwargs['data']['region'] = region.pk
                    if kwargs.get('data', {}).get('city_name').strip():
                        city = intellectual_get_or_create(d['city_name'], City, region=region)
                        kwargs['data']['city'] = city.pk
                        if kwargs.get('data', {}).get('street_name').strip():
                            street = intellectual_get_or_create(d['street_name'], Street, city=city)
                            kwargs['data']['street'] = street.pk
        super(LocationForm, self).__init__(*args, **kwargs)
        self.fields.keyOrder = self.fields.keyOrder[-4:] + self.fields.keyOrder[:-4]

    def is_valid(self):
        result = super(LocationForm, self).is_valid()
        if not result:
            if self.data.get('country') and isinstance(self.data['country'], int):
                self.data['country'] = Country.objects.get_or_create(pk=self.data['country'])
            if self.data.get('region') and isinstance(self.data['region'], int):
                self.data['region'] = Region.objects.get_or_create(pk=self.data['region'])
            if self.data.get('city') and isinstance(self.data['city'], int):
                self.data['city'] = City.objects.get_or_create(pk=self.data['city'])
            if self.data.get('street') and isinstance(self.data['street'], int):
                self.data['street'] = Street.objects.get_or_create(pk=self.data['street'])
        return result

class DeathCertificateForm(forms.ModelForm):
    class Meta:
        model = DeathCertificate
        exclude = ['person']

    def clean_release_date(self):
        if self.cleaned_data['release_date']:
            if self.cleaned_data['release_date'] > datetime.date.today():
                raise forms.ValidationError(u"Дата позже текущей")

            death_date = self.data.get('death_date')
            if death_date:
                if self.cleaned_data['release_date'] < datetime.datetime.strptime(death_date, '%d.%m.%Y').date():
                    raise forms.ValidationError(u"Дата раньше даты смерти")

        return self.cleaned_data['release_date']

    def save(self, person=None, commit=True):
        dc = super(DeathCertificateForm, self).save(commit=False)
        dc.person = person
        if commit:
            dc.save()
        return dc

OPF_FIZIK = 0
OPF_YURIK = 1
OPF_TYPES = (
    (OPF_FIZIK, u'Физ. лицо'),
    (OPF_YURIK, u'Юр. лицо'),
)

class CustomerForm(forms.Form):
    customer_type = forms.ChoiceField(label=u'Организационно-правовая форма*', choices=OPF_TYPES)
    organization = forms.ModelChoiceField(label=u'Организация', queryset=Organization.objects.all(), required=False)
    agent_director = forms.BooleanField(label=u'Директор - агент', required=False)
    agent_person = forms.ModelChoiceField(label=u'Агент', queryset=Person.objects.none(), required=False)
    agent_doverennost = forms.ModelChoiceField(label=u'Доверенность', queryset=Doverennost.objects.none(), required=False)

    def __init__(self, *args, **kwargs):
        super(CustomerForm, self).__init__(*args, **kwargs)
        qs = Person.objects.filter(agent__organization__isnull=False).distinct()

        if self.data.get('customer-agent_person') == '---------------':
            self.data = self.data.copy()
            self.data['customer-agent_person'] = None

        if not self.is_person():
            self.fields['organization'].required = True
            self.fields['agent_person'].queryset = qs
            if not self.is_agent_director():
                self.fields['agent_doverennost'].required = True
                agent = self.data.get('customer-agent_person', '')
                if agent:
                    self.fields['agent_doverennost'].queryset = Doverennost.objects.filter(agent__person__pk=agent)

    def is_person(self):
        return str(self.data.get('customer-customer_type', '')) == str(OPF_FIZIK)

    def is_agent_director(self):
        return bool(self.data.get('customer-agent_director', ''))

    def get_agent(self):
        if self.cleaned_data['agent_director']:
            org = self.cleaned_data['organization']
            return org.ceo
        else:
            return self.cleaned_data['agent_person']

class CustomerIDForm(forms.ModelForm):
    source = forms.CharField(label=u'Кем выдан')

    class Meta:
        model = PersonID
        exclude = ['person']

    def __init__(self, *args, **kwargs):
        cid = kwargs.get('instance')
        if cid:
            kwargs.setdefault('initial', {}).update(source=cid.source)
        super(CustomerIDForm, self).__init__(*args, **kwargs)

    def clean_source(self):
        ds = None
        if self.cleaned_data['source']:
            ds, _ = DocumentSource.objects.get_or_create(name=self.cleaned_data['source'])
        return ds

    def clean_date(self):
        if self.cleaned_data['date']:
            if self.cleaned_data['date'] > datetime.date.today():
                raise forms.ValidationError(u"Дата позже текущей")
        return self.cleaned_data['date']

    def save(self, person=None, commit=True):
        cid = super(CustomerIDForm, self).save(commit=False)
        cid.person = person
        if commit:
            cid.save()
        return cid

class DoverennostForm(forms.ModelForm):
    agent = forms.ModelChoiceField(queryset=Agent.objects.all(), widget=forms.HiddenInput)

    class Meta:
        model = Doverennost

    def clean_issue_date(self):
        if self.cleaned_data['issue_date'] and self.cleaned_data['issue_date'] > datetime.date.today():
            raise forms.ValidationError(u"Дата выпуска позже текущей")
        return self.cleaned_data['issue_date']

    def clean(self):
        if self.cleaned_data.get('issue_date') and self.cleaned_data.get('expire_date') and self.cleaned_data['issue_date'] > self.cleaned_data['expire_date']:
            raise forms.ValidationError(u"Дата выпуска позже даты окончания")
        return self.cleaned_data

    def save(self, commit=True, agent=None):
        if agent:
            self.cleaned_data.update({'agent': agent})
        try:
            d = Doverennost.objects.get(**self.cleaned_data)
        except Doverennost.DoesNotExist:
            d = super(DoverennostForm, self).save(commit=False)
            if agent:
                d.agent = agent
            if commit:
                d.save()
        return d

class UserProfileForm(forms.ModelForm):
    """
    Форма значений по умолчанию для профиля пользователя.
    """

    class Meta:
        model = UserProfile

class OrderPositionForm(forms.ModelForm):
    active = forms.BooleanField(required=False)

    def __init__(self, *args, **kwargs):
        if kwargs.get('data'):
            kwargs['data'] = kwargs['data'].copy()
            for k,v in kwargs['data'].items():
                if k.endswith('service') and not v.isdigit():
                    try:
                        kwargs['data'][k] = Service.objects.get(name=v).pk
                    except Service.DoesNotExist:
                        pass
        super(OrderPositionForm, self).__init__(*args, **kwargs)

    class Meta:
        model = ServicePosition
        fields = ['service', 'count', 'price']
        widgets = {
            'service': forms.HiddenInput,
        }

class BaseOrderPositionsFormset(formsets.BaseFormSet):
    def __init__(self, *args, **kwargs):
        if kwargs.get('initial'):
            real_initial = []
            for i in kwargs['initial']:

                if isinstance(i['service'], Service):
                    q = models.Q(pk=i['service'].pk)
                else:
                    q = models.Q(name=i['service'])
                try:
                    Service.objects.get(q)
                except Service.DoesNotExist:
                    pass
                else:
                    real_initial.append(i)
            kwargs['initial'] = real_initial

        super(BaseOrderPositionsFormset, self).__init__(*args, **kwargs)

OrderPositionsFormset = forms.formsets.formset_factory(OrderPositionForm, extra=0, formset=BaseOrderPositionsFormset)

class OrderPaymentForm(forms.ModelForm):
    class Meta:
        model = Burial
        fields = ['payment_type', ]
        widgets = {
            'payment_type': forms.RadioSelect,
        }

class PrintOptionsForm(forms.Form):
    catafalque = forms.BooleanField(label=u"наряд на автокатафалк", required=False, initial=False)
    lifters = forms.BooleanField(label=u"наряд на грузчиков", required=False, initial=False)
    graving = forms.BooleanField(label=u"наряд на рытье могилы", required=False, initial=True)
    receipt = forms.BooleanField(label=u"справка о захоронении", required=False, initial=False)
    dogovor = forms.BooleanField(label=u"договор ответственного", required=False, initial=False)

    catafalque_route = forms.CharField(label=u"маршрут а/к", required=False, widget=forms.Textarea)
    catafalque_start = forms.CharField(label=u"подача а/к", required=False)
    catafalque_time = forms.TimeField(label=u"время а/к", required=False)

    coffin_size = forms.CharField(label=u"размер гроба", required=False)

    print_now = forms.BooleanField(label=u"отправить на печать", required=False)

    add_info = forms.CharField(label=u"доп. инфо", required=False, widget=forms.Textarea)

    org = forms.ModelChoiceField(label=u"организация", required=False, queryset=Organization.objects.all())

    def __init__(self, *args, **kwargs):
        self.burial = kwargs.pop('burial')
        super(PrintOptionsForm, self).__init__(*args, **kwargs)

class UserForm(forms.ModelForm):
    username = forms.SlugField(max_length=255, label=u'Имя пользователя')
    groups = forms.ModelMultipleChoiceField(queryset=Group.objects.all(), label=u'Группы', required=False, widget=forms.CheckboxSelectMultiple)
    password1 = forms.CharField(widget=forms.PasswordInput, max_length=255, label=u'Пароль', required=False)
    password2 = forms.CharField(widget=forms.PasswordInput, max_length=255, label=u'Пароль (еще раз)', required=False)

    class Meta:
        model = Person
        fields = ['last_name', 'first_name', 'middle_name', 'phones', ]
        widgets = {
            'phones': forms.TextInput()
        }

    def __init__(self, *args, **kwargs):
        if kwargs.get('instance'):
            person = kwargs.get('instance')
            kwargs.setdefault('initial', {}).update(
                username=person.user and person.user.username,
                groups=person.user and person.user.groups.all(),
            )
        super(UserForm, self).__init__(*args, **kwargs)
        self.fields['last_name'].required = True
        if not self.instance or not self.instance.pk:
            self.fields['password1'].required = True

    def clean_username(self):
        users = Person.objects.filter(user__username=self.cleaned_data['username'])
        if self.instance and self.instance.pk:
            users = users.exclude(pk=self.instance.pk)
        if users.exists():
            raise forms.ValidationError(u'Имя пользователя уже занято')
        return self.cleaned_data['username']

    def clean(self):
        if self.cleaned_data.get('password1') and self.cleaned_data['password1'] != self.cleaned_data['password2']:
            raise forms.ValidationError(u'Пароли не совпадают')
        return self.cleaned_data

    def save(self, creator=None, *args, **kwargs):
        person = super(UserForm, self).save(*args, **kwargs)
        if not person.user:
            person.user = User()
        person.user.last_name = self.cleaned_data['last_name'].capitalize()
        person.user.first_name = self.cleaned_data['first_name'].capitalize()
        person.user.username = self.cleaned_data['username']
        person.user.is_staff = True

        if self.cleaned_data.get('password1'):
            person.user.set_password(self.cleaned_data['password1'])

        person.user.save()
        person.user = person.user
        person.creator = creator
        person.save()

        person.user.groups = self.cleaned_data['groups']
        person.user.save()

        return person

class CemeteryForm(forms.ModelForm):
    class Meta:
        model = Cemetery
        fields = ['organization', 'name', 'phones', 'ordering']
        widgets = {
            'phones': forms.TextInput(),
        }

    def save(self, location=None, *args, **kwargs):
        cemetery = super(CemeteryForm, self).save(*args, **kwargs)
        cemetery.location = location
        if kwargs.get('commit'):
            cemetery.save()
        return cemetery

class CeoForm(forms.ModelForm):
    class Meta:
        model = Person
        fields = ['last_name', 'first_name', 'middle_name']

class OrganizationForm(forms.ModelForm):
    allow_duplicate = forms.BooleanField(label=u'Добавить дубль', required=False, widget=forms.HiddenInput)

    class Meta:
        model = Organization
        exclude = ['location', 'ceo']
        widgets = {
            'phones': forms.TextInput(),
        }

    def clean(self):
        orgs = Organization.objects.filter(inn=self.cleaned_data['inn'])
        if self.instance and self.instance.pk:
            orgs = orgs.exclude(pk=self.instance.pk)
        if orgs.exists():
            if not self.cleaned_data.get('allow_duplicate'):
                self.fields['allow_duplicate'].widget = forms.CheckboxInput()
                self.fields['allow_duplicate'].required = True
                raise forms.ValidationError(u"<span class=\"alert alert-error\">ИНН дублируется. Вы уверены?</a>")
        return self.cleaned_data

    def save(self, location=None, ceo=None, *args, **kwargs):
        org = super(OrganizationForm, self).save(*args, **kwargs)
        org.location = location
        org.ceo = ceo
        org.save()
        return org

class CommentForm(forms.ModelForm):
    class Meta:
        model = Comment
        widgets = {
            'comment': forms.TextInput(),
        }

    def clean(self):
        if not self.cleaned_data.get('comment') and not self.cleaned_data.get('file'):
            raise forms.ValidationError(u"Комментарий пустой")
        return self.cleaned_data

    def save(self, burial=None, user=None, commit=True, *args, **kwargs):
        comment = super(CommentForm, self).save(commit=False, *args, **kwargs)
        comment.burial = burial
        comment.user = user
        if commit:
            comment.save()
        return comment

class PlaceRoomsForm(forms.ModelForm):
    class Meta:
        model = Place
        fields = ['rooms', 'unowned']

    def save(self, *args, **kwargs):
        place = super(PlaceRoomsForm, self).save(*args, **kwargs)
        Burial.objects.filter(place=place, grave_id__gte=place.rooms).update(grave_id=None)
        return place

class PlaceBurialForm(forms.Form):
    burial = forms.ModelChoiceField(queryset=Burial.objects.none(), required=False)

class BasePlaceBurialsFormset(BaseFormSet):
    def __init__(self, place=None, *args, **kwargs):
        self.place = place
        self.filled_burials = place.burial_set.filter(grave_id__isnull=False, exhumated_date__isnull=True).order_by('id')
        self.free_burials = place.burial_set.filter(grave_id__isnull=True, exhumated_date__isnull=True).order_by('id')
        self.exhumated_burials = place.burial_set.filter(exhumated_date__isnull=False).order_by('id')

        places_initial = []
        for i in range(place.rooms):
            places_initial.append({})
        for b in self.filled_burials:
            places_initial[b.grave_id].setdefault('burials', []).append(b)

        limit = datetime.date.today() - datetime.timedelta(365*20)
        if self.free_burials:
            for i,d in enumerate(places_initial):
                burials = d.get('burials') or []
                all_empty = lambda b: not b.operation.is_urn() or b.date_fact < limit
                places_initial[i]['available'] = all(filter(all_empty, burials))
        super(BasePlaceBurialsFormset, self).__init__(initial=places_initial, *args, **kwargs)

        for i, f in enumerate(self.forms):
            if places_initial[i].get('burial'):
                f.fields['burial'].queryset = place.burial_set.filter(grave_id=i, exhumated_date__isnull=True)
            else:
                f.fields['burial'].queryset = self.free_burials
        self.pbf_data = zip(places_initial, self.forms)

    def clean(self):
        for i, f in enumerate(self.forms):
            burial = f.cleaned_data.get('burial')
            if not burial:
                continue

            burials = list(Burial.objects.filter(place=self.place, grave_id=i, exhumated_date__isnull=True))

            other_here = filter(lambda b: not b.operation.is_empty(), burials)
            if any(other_here):
                if burial.operation.is_urn():
                    continue
                if burial.operation.is_additional():
                    limit = datetime.date.today() - datetime.timedelta(20*365)
                    if any(filter(lambda b: b.date_fact > limit, other_here)):
                        raise forms.ValidationError(u'Ошибка в позиции %s: попытка подзахоронения в занятую могилу.' % i)
                raise forms.ValidationError(u'Ошибка в позиции %s: попытка захоронения не-урны в занятую могилу.' % i)

    def save(self):
        for i,f in enumerate(self.forms):
            if f.cleaned_data.get('burial'):
                f.cleaned_data['burial'].grave_id = i
                f.cleaned_data['burial'].save()

PlaceBurialsFormset = formset_factory(form=PlaceBurialForm, formset=BasePlaceBurialsFormset, extra=0)

class AddAgentForm(forms.ModelForm):
    organization = forms.ModelChoiceField(queryset=Organization.objects.all(), widget=forms.HiddenInput)

    class Meta:
        model = Person
        exclude = ['death_date', 'birth_date']
        widgets = {'phones': forms.TextInput}

    def save(self, *args, **kwargs):
        person = super(AddAgentForm, self).save()
        return Agent.objects.create(person=person, organization=self.cleaned_data['organization'])

class OrganizationAgentForm(forms.ModelForm):
    last_name = forms.CharField(label=u'Фамилия')
    first_name = forms.CharField(required=False, label=u'Имя')
    middle_name = forms.CharField(required=False, label=u'Отчество')

    class Meta:
        model = Agent
        fields = ['id']

    def __init__(self, *args, **kwargs):
        if kwargs.get('instance'):
            i = kwargs.get('instance')
            kwargs.setdefault('initial', {}).update({
                'last_name': i.person.last_name,
                'middle_name': i.person.middle_name,
                'first_name': i.person.first_name,
                })
        super(OrganizationAgentForm, self).__init__(*args, **kwargs)

    def save(self, commit=True):
        obj = super(OrganizationAgentForm, self).save(commit=commit)
        if self.instance.person_id:
            self.instance.person.last_name = self.cleaned_data['last_name']
            self.instance.person.middle_name = self.cleaned_data['middle_name']
            self.instance.person.first_name = self.cleaned_data['first_name']
            self.instance.person.save()
        else:
            self.instance.person = Person.objects.create(
                last_name=self.cleaned_data['last_name'],
                middle_name=self.cleaned_data['middle_name'],
                first_name=self.cleaned_data['first_name']
            )
            self.instance.save()
        return obj

AccountsFormset = inlineformset_factory(Organization, BankAccount)
AgentsFormset = inlineformset_factory(Organization, Agent, form=OrganizationAgentForm, can_delete=False)

class CatafalquesPrintForm(forms.Form):
    date = forms.DateField(label=u"Дата")