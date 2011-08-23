# -*- coding: utf-8 -*-

from django.db import models
from django.contrib.auth.models import User, Group
from django.core.exceptions import ObjectDoesNotExist
from django.core.validators import RegexValidator
from django.conf import settings
from django.utils.safestring import mark_safe

from contrib.constants import UNKNOWN_NAME

from south.modelsinspector import add_introspection_rules

import datetime
import os
import re

from django_extensions.db.fields import UUIDField

class DigitsValidator(RegexValidator):
    regex = '^\d+$'
    message = u'Допускаются только цифры'

    def __init__(self):
        super(DigitsValidator, self).__init__(regex=self.regex, message=self.message, code=None)

PER_PAGE_VALUES = (
    (5, '5'),
    (10, '10'),
    (15, '15'),
    (25, '25'),
    (50, '50'),
)

ORDER_BY_VALUES = (
    ('person__last_name', '+фамилии'),
    ('-person__last_name', '-фамилии'),
    ('person__first_name', '+имени'),
    ('-person__first_name', '-имени'),
    ('person__patronymic', '+отчеству'),
    ('-person__patronymic', '-отчеству'),
    ('bur_date', '+дате захоронения'),
    ('-bur_date', '-дате захоронения'),
    ('account_book_n', '+номеру в книге учета'),
    ('-account_book_n', '-номеру в книге учета'),
    ('place__area', '+участку'),
    ('-place__area', '-участку'),
    ('place__row', '+ряду'),
    ('-place__row', '-ряду'),
    ('place__seat', '+месту'),
    ('-place__seat', '-месту'),
    ('place__cemetery', '+кладбищу'),
    ('-place__cemetery', '-кладбищу'),
    #('comment', '+комментарию'),
    #('-comment', '-комментарию'),
)


class GeoCountry(models.Model):
    """
    Страна.
    """
    uuid = UUIDField(primary_key=True)
    name = models.CharField(u"Название", max_length=24, db_index=True, unique=True)
    def __unicode__(self):
        return self.name[:16]
    class Meta:
        #managed = False
        #db_table = "common_country"
        ordering = ['name']
        verbose_name = u'страна'
        verbose_name_plural = u'страны'


class GeoRegion(models.Model):
    """
    Регион.
    """
    uuid = UUIDField(primary_key=True)
    country = models.ForeignKey(GeoCountry)
    name = models.CharField(u"Название", max_length=36, db_index=True)
    def __unicode__(self):
        return self.name[:24]
    class Meta:
        unique_together = (("country", "name"),)
        verbose_name = u'регион'
        verbose_name_plural = u'регионы'


class GeoCity(models.Model):
    """
    Город.
    """
    uuid = UUIDField(primary_key=True)
    country = models.ForeignKey(GeoCountry)
    region = models.ForeignKey(GeoRegion)
    name = models.CharField(u"Название", max_length=36, db_index=True)
    def __unicode__(self):
        return self.name[:24]
    class Meta:
        unique_together = (("region", "name"),)
        verbose_name = u'населенный пункт'
        verbose_name_plural = u'населенные пункты'


class Metro(models.Model):
    """
    Метро.
    """
    uuid = UUIDField(primary_key=True)
    city = models.ForeignKey(GeoCity)  # Город.
    name = models.CharField(max_length=99)  # Название.
    class Meta:
        ordering = ['city', 'name']
    def __unicode__(self):
        return self.name


class Street(models.Model):
    """
    Улица.
    """
    uuid = UUIDField(primary_key=True)
    city = models.ForeignKey(GeoCity)  # Город.
    name = models.CharField(max_length=99, db_index=True)  # Название.

    class Meta:
        ordering = ['city', 'name']
        unique_together = (("city", "name"),)
        verbose_name = (u'улица')
        verbose_name_plural = (u'улицы')

    def __unicode__(self):
        return self.name


class Location(models.Model):
    """
    Адрес.
    """
    uuid = UUIDField(primary_key=True)
    post_index = models.CharField(u"Почтовый индекс", max_length=16, blank=True)             # Индекс.
    street = models.ForeignKey(Street, verbose_name=u"Улица", blank=True, null=True)
    city = models.ForeignKey(GeoCity, verbose_name=u"Город", blank=True, null=True)
    region = models.ForeignKey(GeoRegion, verbose_name=u"Регион", blank=True, null=True)
    country = models.ForeignKey(GeoCountry, verbose_name=u"Страна", blank=True, null=True)
    house = models.CharField(u"Дом", max_length=16, blank=True)                              # Дом.
    block = models.CharField(u"Корпус", max_length=16, blank=True)                           # Корпус.
    building = models.CharField(u"Строение", max_length=16, blank=True)                      # Строение.
    flat = models.CharField(u"Квартира", max_length=16, blank=True)                          # Квартира.
    gps_x = models.FloatField(u"Координата X", blank=True, null=True)                        # GPS X-ось.
    gps_y = models.FloatField(u"Координата Y", blank=True, null=True)                        # GPS Y-ось.
    gps_z = models.FloatField(u"Координата Z", blank=True, null=True)                        # GPS Z-ось.
    info = models.TextField(u"Дополнительная информация", blank=True, null=True)             # Дополнительная информация

    def __unicode__(self):
        if self.street:
            return u'%s (дом %s, корп. %s, строен. %s, кв. %s)' % (self.street,
                                self.house, self.block, self.building, self.flat)
        else:
            return u"незаполненный адрес"

    def save(self, *args, **kwargs):
        if self.pk:
            Cemetery.objects.filter(location=self).update(last_sync_date=datetime.datetime(2000, 1, 1, 0, 0))
        super(Location, self).save(*args, **kwargs)


class Soul(models.Model):
    """
    Душа.
    """
    uuid = UUIDField(primary_key=True)
    birth_date = models.DateField(u"Дата рождения", blank=True, null=True)
    death_date = models.DateField(u"Дата смерти", blank=True, null=True)
    location = models.OneToOneField(Location, blank=True, null=True)  # Адрес орг-ии или человека (Person).
    creator = models.ForeignKey(u"Soul", blank=True, null=True)  # Создатель записи.
    date_of_creation = models.DateTimeField(auto_now_add=True)  # Дата создания записи.

    def __unicode__(self):
        if hasattr(self, "person"):
            return u"Физ. лицо: %s" % self.person
        elif hasattr(self, "organization"):
            return u"Юр. лицо: %s" % self.organization
        else:
            return self.uuid

    def save(self, *args, **kwargs):
        if hasattr(self, "person"):
            Burial.objects.filter(person=self.person).update(last_sync_date=datetime.datetime(2000, 1, 1, 0, 0))
        super(Soul, self).save(*args, **kwargs)

    class Meta:
        ordering = ['uuid']


class Phone(models.Model):
    """
    Телефонный номер.
    """
    uuid = UUIDField(primary_key=True)
    soul = models.ForeignKey(Soul)
    f_number = models.CharField(u"Номер телефона", max_length=20)  # Телефон.

    class Meta:
        unique_together = (("soul", "f_number"),)

    def __unicode__(self):
        return self.f_number
    
    def save(self, *args, **kwargs):
        soul = self.soul
        if hasattr(soul, "organization"):
            Cemetery.objects.filter(organization=soul.organization).update(last_sync_date=datetime.datetime(2000, 1, 1, 0, 0))
        super(Phone, self).save(*args, **kwargs)


class Email(models.Model):
    """
    Адрес электронной почты.
    """
    uuid = UUIDField(primary_key=True)
    soul = models.ForeignKey(Soul)
    e_addr = models.EmailField()  # e-mail.


class IDDocumentType(models.Model):
    name = models.CharField(u"Тип документа", max_length=255)

    def __unicode__(self):
        return self.name
    
class Person(Soul):
    """
    Физическое лицо (клиент, сотрудник, кто угодно).
    """
    last_name = models.CharField(u"Фамилия", max_length=128)  # Фамилия.
    first_name = models.CharField(u"Имя", max_length=30, blank=True)  # Имя.
    patronymic = models.CharField(u"Отчество", max_length=30, blank=True)  # Отчество.
    roles = models.ManyToManyField(u"Role", through="PersonRole", verbose_name="Роли")

    def __unicode__(self):
        if self.last_name:
            result = self.last_name
            if self.first_name:
                result += " %s." % self.first_name[0].upper()
                if self.patronymic:
                    result += "%s." % self.patronymic[0].upper()
        else:
            result = self.uuid
        return result

    def filled(self):
        return self.last_name and self.last_name != UNKNOWN_NAME
    
    def save(self, *args, **kwargs):
        Burial.objects.filter(person=self).update(last_sync_date=datetime.datetime(2000, 1, 1, 0, 0))
        super(Person, self).save(*args, **kwargs)
        
    def get_initials(self):
        initials = u""
        if self.first_name:
            initials = u"%s." % self.first_name[:1].upper()
            if self.patronymic:
                initials = u"%s%s." % (initials, self.patronymic[:1].upper())
        return initials

    def full_name(self):
        fio = u"%s %s" % (self.last_name, self.get_initials())
        return fio.strip()

    class Meta:
        verbose_name = (u'физ. лицо')
        verbose_name_plural = (u'физ. лица')

class PersonID(models.Model):
    person = models.OneToOneField(Person)
    id_type = models.ForeignKey(IDDocumentType, verbose_name=u"Тип документа")
    series = models.CharField(u"Серия", max_length=4, blank=True, null=True)
    number = models.CharField(u"Номер", max_length=16)
    who = models.CharField(u"Кем выдан", max_length=255, blank=True, null=True)
    when = models.DateField(u"Дата выдачи")

class ZAGS(models.Model):
    name = models.CharField(u"Название", max_length=255)

    def __unicode__(self):
        return self.name

    class Meta:
        verbose_name = (u'ЗАГС')
        verbose_name_plural = (u'ЗАГС')

class DeathCertificate(models.Model):
    """
    Свидетельство о смерти.
    """
    uuid = UUIDField(primary_key=True)
    soul = models.OneToOneField(Soul)

    s_number = models.CharField(u"Номер свидетельства", max_length=30)
    series = models.CharField(u"Серия свидетельства", max_length=30, blank=True, null=True)
    release_date = models.DateField(u"Дата выдачи", null=True)
    zags = models.ForeignKey(ZAGS, verbose_name=u"ЗАГС", blank=True, null=True)

    def __unicode__(self):
        return u"Свид. о смерти (%s)" % self.soul.__unicode__()

    class Meta:
        verbose_name = (u'свидетельство о смерти')
        verbose_name_plural = (u'свидетельства о смерти')


class Organization(Soul):
    """
    Юридическое лицо.
    """
    ogrn = models.CharField(u"ОГРН/ОГРИП", max_length=15, blank=True)                                  # ОГРН
    inn = models.CharField(u"ИНН", max_length=12, blank=True)                                    # ИНН
    kpp = models.CharField(u"КПП", max_length=9, blank=True)                                     # КПП
    name = models.CharField(u"Краткое название организации", max_length=99)                      # Название краткое
    full_name = models.CharField(u"Полное название организации", max_length=255, null=True)      # Название полное

    def __unicode__(self):
        return self.name or self.full_name

    def phone(self):
        try:
            return self.phone_set.all()[0]
        except IndexError:
            return

    class Meta:
        verbose_name = (u'юр. лицо')
        verbose_name_plural = (u'юр. лица')

class BankAccount(models.Model):
    """
    Банковские реквизиты
    """
    organization = models.ForeignKey(Organization, verbose_name=u"Организация")      # Владелец счета
    rs = models.CharField(u"Расчетный счет", max_length=20, validators=[DigitsValidator(), ]) # Расчетный счет
    ks = models.CharField(u"Корреспондентский счет", max_length=20, blank=True, validators=[DigitsValidator(), ]) # Корреспондентский счет
    bik = models.CharField(u"БИК", max_length=9, blank=True, validators=[DigitsValidator(), ])                         # Банковский идентификационный код
    bankname = models.CharField(u"Наименование банка", max_length=64)    # Название банка


class Role(models.Model):
    """
    Роль в организации.
    """
    uuid = UUIDField(primary_key=True)
    organization = models.ForeignKey(Organization, verbose_name=u"Организация", related_name="orgrole")  # Связь с юр. лицом.
    name = models.CharField(u"Роль", max_length=50, blank=True)  # Название.
    djgroups = models.ManyToManyField(Group, verbose_name=u"Django-группы", blank=True, null=True)
    creator = models.ForeignKey(Soul, verbose_name=u"Автор")  # Создатель записи.
    date_of_creation = models.DateTimeField(auto_now_add=True)  # Дата создания записи.

    def __unicode__(self):
        return u"%s - %s" % (self.organization, self.name)

    class Meta:
        verbose_name = (u'роль в организации')
        verbose_name_plural = (u'роли в организациях')


class RoleTree(models.Model):
    """
    Кто кому подчиняется в организации.
    Собираемся в будущем усовершенствовать - чтобы у одного начальника сразу несколько подчиненных хранить.
    """
    uuid = UUIDField(primary_key=True)
    master = models.ForeignKey(Role, related_name='rltree_master')  # Начальник.
    slave = models.ForeignKey(Role, related_name='rltree_slave') # Подчиненный.


class PersonRole(models.Model):
    """
    Роль персоны. Фактически, это сотрудники, которым есть доступ в систему.
    """
    uuid = UUIDField(primary_key=True)
    person = models.ForeignKey(Person, related_name="personrole")  # Персона.
    role = models.ForeignKey(Role)  # Роль.
    hire_date = models.DateField(u"Дата приема на работу", blank=True, null=True)
    discharge_date = models.DateField(u"Дата увольнения", blank=True, null=True)
    creator = models.ForeignKey(Soul)  # Создатель записи.
    date_of_creation = models.DateTimeField(auto_now_add=True)  # Дата создания записи.

    def __unicode__(self):
        return u"%s - %s" % (self.person.__unicode__(), self.role.__unicode__())
    class Meta:
        unique_together = (("person", "role"),)

class Agent(models.Model):
    uuid = UUIDField(primary_key=True)
    person = models.ForeignKey(Person, related_name="is_agent_of", verbose_name="Персона", limit_choices_to={
        'is_agent_of__pk__isnull': False,
    })
    organization = models.ForeignKey(Organization, related_name="agents", verbose_name="Организация")

    def __unicode__(self):
        return unicode(self.person)

class Doverennost(models.Model):
    agent = models.ForeignKey(Agent, related_name="doverennosti", verbose_name="Доверенность")

    number = models.CharField(verbose_name="Номер доверенности", max_length=255, blank=True, null=True)
    date = models.DateField(verbose_name="Дата выдачи", blank=True, null=True)
    expire = models.DateField(verbose_name="Действует до", blank=True, null=True)

    def __unicode__(self):
        return unicode(self.agent) + ' - ' + self.dover_number

class Cemetery(models.Model):
    """
    Кладбище.
    """
    uuid = UUIDField(primary_key=True)
    organization = models.ForeignKey(Organization, related_name="cemetery")  # Связь с душой.
    location = models.ForeignKey(Location, blank=True, null=True)  # Адрес.
    name = models.CharField(u"Название", max_length=99, blank=True)  # Название.
    creator = models.ForeignKey(Soul)  # Создатель записи.
    date_of_creation = models.DateTimeField(auto_now_add=True)  # Дата создания записи.
    last_sync_date = models.DateTimeField(u"Дата последней синхронизации", default=datetime.datetime(2000, 1, 1, 0, 0))

    class Meta:
        #ordering = ['name']
        verbose_name = (u'кладбище')
        verbose_name_plural = (u'кладбища')

    def __unicode__(self):
        return self.name

    def save(self, *args, **kwargs):
        self.last_sync_date = datetime.datetime(2000, 1, 1, 0, 0)
        super(Cemetery, self).save(*args, **kwargs)


class ProductType(models.Model):
    """
    Тип продукта.
    """
    uuid = UUIDField(primary_key=True)
    name = models.CharField(u"Имя типа продукта", max_length=24)

    def __unicode__(self):
        return self.name

    class Meta:
        verbose_name = (u'тип продукта')
        verbose_name_plural = (u'типы продуктов')


class Product(models.Model):
    """
    Продукт.
    """
    uuid = UUIDField(primary_key=True)
    soul = models.ForeignKey(Soul, verbose_name=u"Душа")  # Кому принадлежит?
    name = models.CharField(u"Название", max_length=50)  # Название продукта.
    measure = models.CharField(u"Единицы измерения", max_length=50, blank=True)  # Размерность.
    p_type = models.ForeignKey(ProductType, verbose_name=u"Тип продукта")

    def add_comment(self, txt, creator):
        comment = ProductComments(product=self, comment=txt,
                                  creator=creator)
        comment.save()
    def __unicode__(self):
        return self.name

class ProductFiles(models.Model):
    """
    Файлы, связанные с продуктом.
    """
    uuid = UUIDField(primary_key=True)
    product = models.ForeignKey(Product)
    pfile = models.FileField(upload_to="pfiles")
    creator = models.ForeignKey(Soul, null=True)  # Создатель записи.
    date_of_creation = models.DateTimeField(auto_now_add=True)  # Дата создания записи.


class ProductComments(models.Model):
    """
    Комментарии, связанные с продуктом.
    """
    uuid = UUIDField(primary_key=True)
    product = models.ForeignKey(Product)
    comment = models.TextField()  # Комментарий.
    creator = models.ForeignKey(Soul)  # Создатель записи.
    date_of_creation = models.DateTimeField(auto_now_add=True)  # Дата создания записи.
    class Meta:
        ordering = ['date_of_creation']


def split_number(s):
    try:
        p1 = re.findall('^([^\d]*)(\d+)', s, re.I)[0][0]
    except IndexError:
        p1 = ''
    try:
        p2 = int(re.findall('^([^\d]*)(\d+)', s, re.I)[0][1])
    except (IndexError, ValueError):
        p2 = 1999999999
    try:
        p3 = re.findall('^([^\d]*)(\d+)(.*)', s, re.I)[0][2]
    except IndexError:
        p3 = s
    return p1, p2, p3

class Place(Product):
    """
    Место.
    """
    cemetery = models.ForeignKey(Cemetery, verbose_name=u"Кладбище")  # Связь с кладбищем.
    area = models.CharField(u"Участок", max_length=9)  # Участок.
    row = models.CharField(u"Ряд", max_length=9, blank=True, null=True)  # Ряд.
    seat = models.CharField(u"Место", max_length=9)  # Место.
    gps_x = models.FloatField(u"Координата X", blank=True, null=True)  # GPS X-ось.
    gps_y = models.FloatField(u"Координата Y", blank=True, null=True)  # GPS Y-ось.
    gps_z = models.FloatField(u"Координата Z", blank=True, null=True)  # GPS Z-ось.

    rooms = models.PositiveIntegerField(u"Мест в ограде", default=1, blank=True)
    rooms_free = models.PositiveIntegerField(u"Мест в ограде свободно", default=1, blank=True)
    
    creator = models.ForeignKey(Soul, verbose_name=u"Создатель записи")  # Создатель записи.
    date_of_creation = models.DateTimeField(u"Дата создания записи", auto_now_add=True)  # Дата создания записи.

    area_str1 = models.CharField(editable=False, null=True, max_length=9)
    area_num = models.PositiveIntegerField(editable=False, null=True)
    area_str2 = models.CharField(editable=False, null=True, max_length=9)

    row_str1 = models.CharField(editable=False, null=True, max_length=9)
    row_num = models.PositiveIntegerField(editable=False, null=True)
    row_str2 = models.CharField(editable=False, null=True, max_length=9)

    seat_str1 = models.CharField(editable=False, null=True, max_length=9)
    seat_num = models.PositiveIntegerField(editable=False, null=True)
    seat_str2 = models.CharField(editable=False, null=True, max_length=9)

    @staticmethod
    def split_parts(self):
        for f in ['area', 'row', 'seat']:
            p1, p2, p3 = split_number(getattr(self, f))
            setattr(self, f+'_str1', p1)
            setattr(self, f+'_num', p2)
            setattr(self, f+'_str2', p3)

    def save(self, *args, **kwargs):
        """
        Всегда приводим area/row/seat к нижнему регистру.
        """
        self.area = self.area.lower()
        self.row = self.row.lower()

        if self.seat:
            self.seat = self.seat.lower()

        self.split_parts(self)

        Burial.objects.filter(product__place=self).update(last_sync_date=datetime.datetime(2000, 1, 1, 0, 0))
        super(Place, self).save(*args, **kwargs)

    def generate_seat(self):
        y = str(datetime.date.today().year)
        max_seat = str(Place.objects.filter(cemetery=self.cemetery).aggregate(models.Max('seat'))['seat__max']) or ''
        if max_seat.startswith(y):
            current_seat = int(float(max_seat)) + 1
        else:
            current_seat = y + '0001'
        self.seat = str(current_seat)
        return self.seat

    @property
    def rooms_occupied(self):
        return (self.rooms or 0) - (self.rooms_free or 0)

    def count_burials(self):
        siblings = Burial.objects.filter(
            product__place__cemetery = self.cemetery,
            product__place__area = self.area,
            product__place__row = self.row,
            product__place__seat = self.seat,
            exhumated_date__isnull = True,
            is_trash = False,
        )
        return siblings.distinct().count()

    def __unicode__(self):
        return  '%s, %s, %s (%s)' % (self.area, self.row, self.seat,
                                     self.cemetery)

class Operation(models.Model):
    """
    Операция с продуктом.
    """
    uuid = UUIDField(primary_key=True)
    op_type = models.CharField(u"Имя операции", max_length=100)
    def __unicode__(self):
        return self.op_type[:24]
    class Meta:
        verbose_name = (u'операция с продуктом')
        verbose_name_plural = (u'операции с продуктом')


class Order(models.Model):
    """
    Заказ.
    """
    uuid = UUIDField(primary_key=True)
    responsible = models.ForeignKey(Soul, related_name='ordr_responsible')          # Исполнитель. Ответственный за исполнение Заказа. Организация кладбища
    customer = models.ForeignKey(Soul, related_name='ordr_customer')                # Заказчик (физ- или юрлицо)
    responsible_agent = models.ForeignKey(Agent, blank=True, null=True)             # Агент Заказчика-юрлица
    responsible_customer = models.ForeignKey(Soul, related_name='ordr_responsible_customer', blank=True, null=True) # Ответственный за захоронением

    doer = models.ForeignKey(Soul, blank=True, null=True, related_name="doerorder")  # Исполнитель (работник).
    date_plan = models.DateTimeField(blank=True, null=True)  # Планируемая дата исполнения.
    date_fact = models.DateTimeField(u"Фактическая дата исполнения", blank=True, null=True)  # Фактическая дата исполнения.
    product = models.ForeignKey(Product, related_name="order")
    operation = models.ForeignKey(Operation)
    is_trash = models.BooleanField(default=False)  # Удален.
    creator = models.ForeignKey(Soul, related_name="order")  # Создатель записи.
    date_of_creation = models.DateTimeField(auto_now_add=True)  # Дата создания записи.
    payment_type = models.CharField(u"Платеж", max_length=16, choices=[
        ('nal', u"Нал"),
        ('beznal', u"Безнал"),
    ], default='nal', blank=False)

    def add_comment(self, txt, creator):
        comment = OrderComments(order=self, comment=txt, creator=creator)
        comment.save()

    def get_responsible_customer(self):
        return self.responsible_customer or self.customer

class OrderFiles(models.Model):
    """
    Файлы, связанные с заказом.
    """
    uuid = UUIDField(primary_key=True)
    order = models.ForeignKey(Order)
    ofile = models.FileField(u"Файл", upload_to="ofiles")
    comment = models.CharField(max_length=96, blank=True)
    creator = models.ForeignKey(Soul, null=True)  # Создатель записи.
    date_of_creation = models.DateTimeField(auto_now_add=True)  # Дата создания записи.
    
    def delete(self):
        if self.ofile != "":
            if os.path.exists(self.ofile.path):
                os.remove(self.ofile.path)
            self.ofile = ""
        super(OrderFiles, self).delete()

    @property
    def name(self):
        return mark_safe(os.path.basename(self.ofile.url))

class OrderComments(models.Model):
    """
    Комментарии, связанные с заказом.
    """
    uuid = UUIDField(primary_key=True)
    order = models.ForeignKey(Order)
    comment = models.TextField()  # Комментарий.
    creator = models.ForeignKey(Soul)  # Создатель записи.
    date_of_creation = models.DateTimeField(auto_now_add=True)  # Дата создания записи.
    
    class Meta:
        ordering = ['date_of_creation']

class Burial(Order):
    """
    Захоронение.
    """
    person = models.ForeignKey(Person, verbose_name=u"Похороненный", related_name='buried')
    account_book_n = models.CharField(u"Номер в книге учета", max_length=16)
    exhumated_date = models.DateTimeField(u"Дата эксгумации", blank=True, null=True)
    last_sync_date = models.DateTimeField(u"Дата последней синхронизации", default=datetime.datetime(2000, 1, 1, 0, 0))

    acct_num_str1 = models.CharField(editable=False, null=True, max_length=16)
    acct_num_num = models.PositiveIntegerField(editable=False, null=True)
    acct_num_str2 = models.CharField(editable=False, null=True, max_length=16)

    doverennost = models.ForeignKey(Doverennost, null=True)

    class Meta:
        verbose_name = (u'захоронение')
        verbose_name_plural = (u'захоронения')
        #ordering = ['person__last_name',]

    def __unicode__(self):
        return u"захоронение: %s" % self.person.__unicode__()

    @staticmethod
    def split_parts(self):
        p1, p2, p3 = split_number(self.account_book_n)
        self.acct_num_str1 = p1
        self.acct_num_num = p2
        self.acct_num_str2 = p3

    def save(self, *args, **kwargs):
        self.last_sync_date = datetime.datetime(2000, 1, 1, 0, 0)
        self.split_parts(self)
        super(Burial, self).save(*args, **kwargs)

    def generate_account_number(self):
        y = str(datetime.date.today().year)
        siblings = Burial.objects.filter(product__place__cemetery=self.product.place.cemetery, account_book_n__istartswith=y)
        max_num = str(siblings.aggregate(models.Max('account_book_n'))['account_book_n__max']) or ''
        if max_num.startswith(y):
            current_num = int(float(max_num)) + 1
        else:
            current_num = y + '0001'
        self.account_book_n = str(current_num)
        return self.account_book_n

def recount_free_rooms_burial(sender, instance, **kwargs):
    place = instance.product.place
    place.rooms_free = max(0, place.rooms - place.count_burials())
    place.save()
models.signals.post_save.connect(recount_free_rooms_burial, sender=Burial)

def recount_free_rooms_place(sender, instance, **kwargs):
    instance.rooms_free = max(0, instance.rooms - instance.count_burials())
models.signals.pre_save.connect(recount_free_rooms_place, sender=Place)

class UserProfile(models.Model):
    """
    Профиль пользователя.
    """
    user = models.OneToOneField(User, primary_key=True)
    soul = models.OneToOneField(Soul)
    default_cemetery = models.ForeignKey(Cemetery, verbose_name=u"Кладбище",
                                         blank=True, null=True)  # Связь с кладбищем.
    default_operation = models.ForeignKey(Operation, verbose_name=u"Операция", blank=True, null=True)
    default_country = models.ForeignKey(GeoCountry, verbose_name=u"Страна",
                                        blank=True, null=True)  # Страна.
    default_region = models.ForeignKey(GeoRegion, verbose_name=u"Регион",
                                       blank=True, null=True)  # Регион.
    default_city = models.ForeignKey(GeoCity, verbose_name=u"Город",
                                     blank=True, null=True)  # Город.
    records_per_page = models.PositiveSmallIntegerField(u"Записей на странице",
                                                    blank=True, null=True,
                                                    choices=PER_PAGE_VALUES)
    records_order_by = models.CharField(u"Сортировка по", max_length=50,
                                        blank=True, choices=ORDER_BY_VALUES)
    def __unicode__(self):
        return self.user.username


class SoulProducttypeOperation(models.Model):
    """
    Таблица для связи трех моделей.
    """
    uuid = UUIDField(primary_key=True)
    soul = models.ForeignKey(Soul, verbose_name=u"Душа")
    p_type = models.ForeignKey(ProductType, verbose_name=u"Тип продукта")
    operation = models.ForeignKey(Operation,
                                  verbose_name=u"Операция с продуктом")
    def __unicode__(self):
        return u"%s  -  %s  -  %s" % (self.soul.__unicode__(), self.p_type.name,
                             self.operation.op_type[:24])
    class Meta:
        verbose_name = (u'связь типа продукта с операцией')
        verbose_name_plural = (u'связи типов продуктов с операциями')
        unique_together = (("soul", "p_type", "operation"),)


class Env(models.Model):
    """
    Таблица для хранения уникального uuid сервера.
    """
    uuid = UUIDField()

    
class ImpCem(models.Model):
    """
    Таблица для импорта данных кладбищ.
    """
    cem_pk = models.CharField(u"uuid", max_length=36, primary_key=True)
    name = models.CharField(u"Название", max_length=99, blank=True)
    country = models.CharField(u"Страна", max_length=24, blank=True)
    region = models.CharField(u"Регион", max_length=36, blank=True)
    city = models.CharField(u"Город", max_length=36, blank=True)
    street = models.CharField(u"Улица", max_length=99, blank=True)
    post_index = models.CharField(u"Почтовый индекс", max_length=16, blank=True)
    house = models.CharField(u"Дом", max_length=16, blank=True)
    block = models.CharField(u"Корпус", max_length=16, blank=True)
    building = models.CharField(u"Строение", max_length=16, blank=True)
    f_number = models.CharField(u"Номер телефона", max_length=15, blank=True)


class ImpBur(models.Model):
    """
    Таблица для импорта данных захоронений.
    """    
    deadman_pk = models.CharField(u"deadmanuuid", max_length=36, primary_key=True)
    bur_pk = models.CharField(u"buruuid", max_length=36)
    last_name = models.CharField(u"Фамилия", max_length=128)
    first_name = models.CharField(u"Имя", max_length=30, blank=True)
    patronymic = models.CharField(u"Отчество", max_length=30, blank=True)
    birth_date = models.DateField(u"Дата рождения", blank=True, null=True)
    death_date = models.DateField(u"Дата смерти", blank=True, null=True)
    burial_date = models.DateField(u"Дата захоронения", blank=True, null=True)
    cemetery = models.ForeignKey(ImpCem)
    area = models.CharField(u"Участок", max_length=9)
    row = models.CharField(u"Ряд", max_length=9)
    seat = models.CharField(u"Место", max_length=9)
    gps_x = models.FloatField(u"Координата X", blank=True, null=True)
    gps_y = models.FloatField(u"Координата Y", blank=True, null=True)
    gps_z = models.FloatField(u"Координата Z", blank=True, null=True)
    

class Media(models.Model):
    """
    Таблица media. Пока не знаю, для чего она.
    """
    uuid = UUIDField(primary_key=True)
    soul = models.ForeignKey(Soul)
    url = models.URLField(blank=True, verify_exists=False)
    comment = models.TextField(blank=True)
    timestamp = models.DateTimeField(blank=True, null=True)

class OrderProduct(models.Model):
    """
    Продукт в заказе.
    """
    uuid = UUIDField(primary_key=True)
    name = models.CharField(u"Название продукта", max_length=255)
    default = models.BooleanField(u"Вкл. по умолчанию", default=False, blank=True)
    measure = models.CharField(u"Единицы измерения", max_length=50, blank=True)
    price = models.DecimalField(u"Цена", decimal_places=2, max_digits=10)

    def __unicode__(self):
        return self.name

    class Meta:
        verbose_name = (u'тип продукта для счет-заказа')
        verbose_name_plural = (u'типы продуктов для счет-заказа')

class OrderPosition(models.Model):
    """
    Позиция в заказе.
    """
    uuid = UUIDField(primary_key=True)
    order = models.ForeignKey(Order)
    order_product = models.ForeignKey(OrderProduct)
    count = models.DecimalField(u"Кол-во", decimal_places=2, max_digits=10)
    price = models.DecimalField(u"Цена", decimal_places=2, max_digits=10)

    @property
    def sum(self):
        return self.count * self.price

    def __unicode__(self):
        return self.name

    class Meta:
        verbose_name = (u'позиция счет-заказа')
        verbose_name_plural = (u'позиция счет-заказа')

