from django.contrib.admin import site, AdminSite, ModelAdmin, TabularInline, StackedInline
from django.contrib.auth.models import User, Group

from django.utils.translation import gettext_lazy as _
from django.contrib.auth.hashers import make_password
from user_app.models import MyUser, ProductModel, CategoryProduct, UniqCodeModel, OneCCodeModel, PeriodicTimeModel, \
    CategoryProductExclude, UserActivityTrack

default_admin = site


class CustomAdminBase(AdminSite):
    model_name = ''
    permissions = ''
    model_name_permission = 'resolution_value'

    def has_permission(self, request):
        return super().has_permission(request) and \
               hasattr(request.user, self.model_name_permission) and \
               getattr(request.user, self.model_name_permission) == self.permissions


class GeneralAdminPanel(CustomAdminBase):
    permissions = 'is_admin_general'
    model_name = 'GeneralModel'


class ManagerAdminPanel(CustomAdminBase):
    permissions = 'is_admin_manager'
    model_name = 'ManagerModel'


class CustomerAdminPanel(CustomAdminBase):
    permissions = 'is_admin_customer'
    model_name = 'CustomerModel'


general_admin = GeneralAdminPanel(name='general-admin')
manager_admin = ManagerAdminPanel(name='manager-admin')
customer_admin = CustomerAdminPanel(name='customer-admin')


class UsersGeneralManager(MyUser):
    class Meta:
        proxy = True
        verbose_name = _('Главный менеджер')
        verbose_name_plural = _("Главные менеджеры")


class UsersCustomer(MyUser):
    class Meta:
        proxy = True
        verbose_name = _('Покупатель')
        verbose_name_plural = _("Покупатели")


class UsersManager(MyUser):
    class Meta:
        proxy = True
        verbose_name = _('Менеджер')
        verbose_name_plural = _("Менеджеры")


class BaseCustomModelAdmin(ModelAdmin):
    filter_dict = {}
    fields = ('email', 'password', 'first_name', 'last_name', 'phone', 'name_company', 'user_position')

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        return queryset.filter(**self.filter_dict)

    def save_model(self, request, obj, form, change):
        keys, value = tuple(self.filter_dict.items())[0]
        setattr(obj, keys, value)
        name_group = value.split('_')[-1] + '_group'
        obj.is_active = True
        obj.is_staff = True
        my_group, _ = Group.objects.get_or_create(name=name_group)
        setattr(obj, 'password', make_password(obj.password))
        obj.save()
        my_group.user_set.add(obj)


class CustInline(TabularInline):
    model = CategoryProductExclude
    extra = 1


class ManagerModelAdmin(BaseCustomModelAdmin):
    filter_dict = {'resolution_value': 'is_admin_manager'}
    fields = ('email', 'password', 'first_name', 'last_name', 'phone', 'user_position')
    list_display = ("email", "first_name", "phone", "user_position")
    list_filter = ("user_position",)


class CustomerModelAdmin(BaseCustomModelAdmin):
    inlines = [CustInline, ]
    filter_dict = {'resolution_value': 'is_admin_customer'}
    fields = ('email', 'password', 'first_name', 'last_name', 'phone', 'name_company', 'user_position', 'discount')
    list_display = ("email", "first_name", "name_company", "phone", "user_position", "discount")
    list_filter = ("name_company", "discount")


class GeneralModelAdmin(BaseCustomModelAdmin):
    filter_dict = {'resolution_value': 'is_admin_general'}


class ProductModelAdmin(ModelAdmin):
    list_display = '__all__'


class ProductInline(TabularInline):
    model = ProductModel
    extra = 1


class CategoryProductAdmin(ModelAdmin):
    inlines = [ProductInline, ]

    def get_queryset(self, request):
        my_query = super().get_queryset(request)
        if request.user.categoryproductexclude_set.exists():
            list_exclude = request.user.categoryproductexclude_set.values_list('exclude_category__name_category')
            my_query = CategoryProduct.objects.exclude(name_category__in=list_exclude)
        return my_query


class ProjectProductAdmin(ModelAdmin):
    model = ProductModel
    list_display = ("uniq_code", "describe_fields", "price_sample", "price_uniq", "full_url", 'image_tag')
    list_filter = ("uniq_code", "price_sample")
    readonly_fields = ('describe_fields',)

    def get_queryset(self, request):
        my_query = super().get_queryset(request)
        if request.user.categoryproductexclude_set.exists():
            list_exclude = request.user.categoryproductexclude_set.values_list('exclude_category__name_category')
            my_query = ProductModel.objects.exclude(category_product__name_category__in=list_exclude)
        return my_query

    def changelist_view(self, request, extra_context=None):
        # add user in my model admin
        setattr(self, 'my_user_form', request.user)
        return super().changelist_view(request, extra_context)

    def describe_fields(self, obj):
        n = 15
        obj_describe = obj.describe
        return obj_describe[:n] + '...' if len(obj_describe) >= n else obj_describe

    def price_uniq(self, obj):
        discount = getattr(self.my_user_form, 'discount', 0)
        return round(obj.price_sample - (obj.price_sample * (discount / 100)), 2)

    def discount(self, obj):
        return obj.my_user_form.discount


class OneCCodeModelInlines(StackedInline):
    model = OneCCodeModel
    extra = 1


class UniqCodeModelAdmin(ModelAdmin):
    inlines = [OneCCodeModelInlines, ]
    list_display = ("uniq_code", 'field_set')

    def field_set(self, obj):
        data = obj.oneccodemodel_set.values_list('uniq_code_one_c', flat=True)
        return ','.join(data)


default_admin.register(UsersGeneralManager, GeneralModelAdmin)

general_admin.register(ProductModel, ProjectProductAdmin)
general_admin.register(CategoryProduct, CategoryProductAdmin)
general_admin.register(UsersCustomer, CustomerModelAdmin)
general_admin.register(UsersManager, ManagerModelAdmin)

default_admin.register(MyUser)
default_admin.register(ProductModel, ProjectProductAdmin)
default_admin.register(CategoryProduct, CategoryProductAdmin)
default_admin.register(UsersManager, ManagerModelAdmin)
default_admin.register(UsersCustomer, CustomerModelAdmin)
default_admin.register(UniqCodeModel, UniqCodeModelAdmin)
default_admin.register(PeriodicTimeModel)
default_admin.register(CategoryProductExclude)

manager_admin.register(ProductModel, ProjectProductAdmin)
manager_admin.register(CategoryProduct, CategoryProductAdmin)
manager_admin.register(UsersCustomer, CustomerModelAdmin)
manager_admin.disable_action('delete_selected')
manager_admin.register(CategoryProductExclude)

customer_admin.disable_action('delete_selected')
customer_admin.register(ProductModel, ProjectProductAdmin)
customer_admin.register(CategoryProduct, CategoryProductAdmin)

from django.contrib.admin.models import LogEntry


class LogEntryAdmin(ModelAdmin):
    date_hierarchy = 'action_time'

    list_filter = [
        'user',
        'content_type',
        'action_flag'
    ]

    search_fields = [
        'object_repr',
        'change_message'
    ]

    list_display = [
        'action_time',
        'user',
        'content_type',
        'action_flag',
    ]


default_admin.register(LogEntry, LogEntryAdmin)
general_admin.register(UserActivityTrack)
default_admin.register(UserActivityTrack)
