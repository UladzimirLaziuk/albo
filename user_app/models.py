import json

from django.contrib.auth.base_user import BaseUserManager
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver
from django.utils import timezone
from django_celery_beat.models import PeriodicTask, CrontabSchedule
from django.contrib import messages
from phonenumber_field.modelfields import PhoneNumberField
from django.utils.html import mark_safe
from django.utils.translation import gettext_lazy as _
from django.contrib.auth.signals import user_logged_in, user_logged_out
from django.utils.html import format_html
import albo.settings
from django.db.utils import IntegrityError
from django.contrib.admin.models import LogEntry, ADDITION, CHANGE


class UserManager(BaseUserManager):
    def create_user(self, email, full_name=None, profile_picture=None, password=None, is_admin=True, is_staff=True,
                    is_active=True, is_superuser=False):
        if not email:
            raise ValueError("User must have an email")
        if not password:
            raise ValueError("User must have a password")
        if not full_name:
            raise ValueError("User must have a full name")

        user = self.model(
            email=self.normalize_email(email)
        )
        user.full_name = full_name
        user.set_password(password)  # change password to hash
        user.profile_picture = profile_picture
        user.is_admin = is_admin
        user.is_superuser = is_superuser
        user.is_staff = is_staff
        user.is_active = is_active
        user.save(using=self._db)
        return user

    def create_superuser(self, email, full_name=None, profile_picture=None, password=None, resolution_value=None,
                         **extra_fields):
        if not email:
            raise ValueError("User must have an email")
        if not password:
            raise ValueError("User must have a password")

        user = self.model(
            email=self.normalize_email(email)
        )
        user.full_name = full_name
        user.set_password(password)
        user.profile_picture = profile_picture
        user.is_admin = True
        user.is_staff = True
        user.is_active = True
        user.is_superuser = True
        user.resolution_value = resolution_value
        user.save(using=self._db)
        return user


class MyUser(AbstractUser):
    email = models.EmailField(_('email address'), unique=True)

    phone = PhoneNumberField(blank=True)
    name_company = models.CharField(max_length=50, default='')
    user_position = models.CharField(max_length=50, default='')
    resolution_value = models.CharField(max_length=50, default='')
    discount = models.FloatField(verbose_name='Скидка клиента в %', default=0)
    manager_user = models.ForeignKey('MyUser', on_delete=models.CASCADE, blank=True, null=True)
    username = None
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['first_name', 'last_name', 'resolution_value']
    objects = UserManager()

    class Meta:
        verbose_name = "App User"
        verbose_name_plural = "App Users"

    def has_usable_password(self):
        if self.resolution_value == 'is_admin_customer':
            return False
        return super().has_usable_password()

    @property
    def get_full_name(self):
        if self.username:
            return '%s. %s' % (self.username[:1], self.last_name)
        return '%s. %s' % (self.first_name[:1], self.last_name)

    # def __str__(self):
    #     return '%s. %s' % (self.username[:1], self.last_name)


# MyUser.has_usable_password()

class CategoryProduct(models.Model):
    name_category = models.CharField(max_length=120, default='', verbose_name='Категории товара')

    class Meta:
        verbose_name = "Категория"
        verbose_name_plural = "Категории"

    def __str__(self):
        return '%s' % self.name_category


class CategoryProductExclude(models.Model):
    exclude_category = models.ForeignKey(CategoryProduct, on_delete=models.CASCADE, blank=True, null=True)
    exclude_user = models.ForeignKey(MyUser, on_delete=models.CASCADE, blank=True, null=True)


class AlboProductModel(models.Model):
    category_product = models.ForeignKey(CategoryProduct, on_delete=models.CASCADE, blank=True, null=True)
    uniq_code = models.CharField(max_length=255, default='', verbose_name='Код товара')
    describe = models.CharField(max_length=255, default='', verbose_name='Описание товара')
    url_describe = models.URLField(verbose_name="Ссылка на описание товара на сайте", max_length=255, blank=True,
                                   null=True)
    url_image_albo = models.URLField(verbose_name="Ссылка на фото товара на сайте", blank=True, null=True,
                                     max_length=255)
    price_sample = models.FloatField(verbose_name='Цена', default=0)
    quantity = models.IntegerField(null=True, default=0, verbose_name='Количество')
    size_field = models.FloatField(verbose_name='Размер', default=0)

    class Meta:
        verbose_name = "Продукт Albo"
        verbose_name_plural = "Продукты Albo"

    @property
    def image_tag(self):
        if self.url_image_albo:
            return mark_safe('<img src="%s" style="width:180px;height:180px;" />' % (self.url_image_albo))
        return mark_safe('<img src="" alt="%s" style="width:60px; height:60px;" />' % "noimagefound")

    @property
    def full_url(self):
        if self.url_describe:
            return format_html("<a href='%s' target='_blank' >Ссылка на товар</a>" % self.url_describe)
        return ''

    full_url.fget.short_description = _("Ссылка на товар")
    image_tag.fget.short_description = _("Фото товара")

    def __str__(self):
        return '%s' % self.describe


class OneCCodeAlboModel(models.Model):
    map_code = models.ForeignKey(AlboProductModel, on_delete=models.CASCADE)
    uniq_code_one_c = models.CharField(max_length=120, verbose_name='Code 1C')


class ProductModel(models.Model):
    category_product = models.ForeignKey(CategoryProduct, on_delete=models.CASCADE, blank=True, null=True)
    uniq_code = models.CharField(max_length=255, default='', verbose_name='Код товара')
    describe = models.CharField(max_length=255, default='', verbose_name='Описание товара')
    url_describe = models.URLField(verbose_name="Ссылка на описание товара на сайте", default='', max_length=100)
    url_image_albo = models.URLField(verbose_name="Ссылка на фото товара на сайте", default='', max_length=100)
    price_sample = models.FloatField(verbose_name='Цена обычная', default=0)

    class Meta:
        verbose_name = "Продукт"
        verbose_name_plural = "Продукты"

    def image_tag(self):
        if self.url_image_albo:
            return mark_safe('<img src="%s" style="width:180px;height:180px;" />' % (self.url_image_albo))
        return mark_safe('<img src="" alt="%s" style="width:60px; height:60px;" />' % "noimagefound")

    def full_url(self):
        if self.url_describe:
            return format_html("<a href='%s'>Ссылка на товар %s на сайте </a>" %
                               (self.url_describe, str(self.describe)[:20]))
        return ''

    def __str__(self):
        return '%s' % self.describe


class UniqCodeModel(models.Model):
    uniq_code = models.CharField(max_length=120, unique=True)

    def __str__(self):
        return '%s' % self.uniq_code  # + 'с кодами ' + ','.join(self.oneccodemodel_set.values_list('uniq_code_one_c', flat=True))


class OneCCodeModel(models.Model):
    map_code = models.ForeignKey(UniqCodeModel, on_delete=models.CASCADE)
    uniq_code_one_c = models.CharField(max_length=120, verbose_name='Code 1C')


class PeriodicTimeModel(models.Model):
    topic_for_post = [(index, data) for index, data in
                      enumerate(range(1, 61, 1), start=0)]
    periodic_minute = models.PositiveSmallIntegerField(choices=topic_for_post, default=1)
    last_time = models.DateTimeField(blank=True, null=True)

    @property
    def get_val_periodic_minute(self):
        return list(self.topic_for_post)[self.periodic_minute][1]

    def __str__(self):
        return f'{self.get_val_periodic_minute}'


class UserActivityTrack(models.Model):
    user = models.ForeignKey(MyUser, on_delete=models.CASCADE)
    session_key = models.CharField(max_length=40, db_index=True)
    login = models.DateTimeField(auto_now_add=True)
    logout = models.DateTimeField(null=True, default=None)
    ip = models.CharField(max_length=255)
    user_agent = models.CharField(max_length=255)

    def __str__(self):
        name = self.user.get_full_name or 'No Name'
        return f'{name}'


def function_create_beat(time_beat, task, name_task, **kwargs):
    schedule, _ = CrontabSchedule.objects.update_or_create(minute=f'*/{time_beat}', hour="8-18", day_of_week="*")
    periodic_task, created = PeriodicTask.objects.get_or_create(
        crontab=schedule,
        name=name_task,
        task=task,
        kwargs=json.dumps(kwargs),
    )


@receiver(post_save, sender=PeriodicTimeModel)
def create_track_signal(sender, instance, **kwargs):
    beat_time = str(instance.get_val_periodic_minute)
    IMPORT_FTP_ADDRESS = albo.settings.IMPORT_FTP_ADDRESS
    EXPORT_FTP_ADDRESS = albo.settings.EXPORT_FTP_ADDRESS
    FILE_NAME_FOR_EXPORT = albo.settings.FILE_NAME_FOR_EXPORT
    kwargs = {}
    kwargs.update({
        'import_ftp_address': IMPORT_FTP_ADDRESS,
        'export_ftp_address': EXPORT_FTP_ADDRESS,
        'filename_for_export': FILE_NAME_FOR_EXPORT,
    })
    function_create_beat(beat_time, task="albo.tasks.task_export", name_task='task_export', **kwargs)


@receiver(post_delete, sender=PeriodicTimeModel)
def delete_period_task(sender, instance, **kwargs):
    PeriodicTask.objects.all().delete()
    CrontabSchedule.objects.all().delete()


@receiver(user_logged_in)
def post_login(sender, user, request, **kwargs):
    messages.add_message(request, messages.INFO, user.get_full_name + ' Hello!')

    # locationInfo = get_location_data__from_ip(ip)
    try:
        UserActivityTrack.objects.create(
            user=user,
            session_key=request.session.session_key,
            ip=request.META.get('REMOTE_ADDR'),
            user_agent=request.META.get('HTTP_USER_AGENT'),
        )
    except IntegrityError:
        pass


@receiver(user_logged_out)
def post_logged_out(sender, user, request, **kwargs):
    UserActivityTrack.objects.filter(user=user, session_key=request.session.session_key).update(logout=timezone.now())
