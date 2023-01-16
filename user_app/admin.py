import operator
from functools import reduce

from django.contrib.admin import site, AdminSite, ModelAdmin, TabularInline, StackedInline, SimpleListFilter
from django.contrib.auth.models import User, Group
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from django.contrib.admin.models import LogEntry
from django.utils.translation import gettext_lazy as _
from django.contrib.auth.hashers import make_password
from user_app.models import MyUser, ProductModel, CategoryProduct, UniqCodeModel, OneCCodeModel, PeriodicTimeModel, \
    CategoryProductExclude, UserActivityTrack, AlboProductModel, OneCCodeAlboModel
from django.contrib.humanize.templatetags.humanize import intcomma

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


class ManagerAdminPanel(CustomAdminBase):
    permissions = 'is_admin_manager'


class CustomerAdminPanel(CustomAdminBase):
    permissions = 'is_admin_customer'


class SupportAdminPanel(CustomAdminBase):
    permissions = 'is_admin_support'


support_admin = SupportAdminPanel(name='support-admin')
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
        obj.is_superuser = False
        obj.manager_user = request.user
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

    # def get_queryset(self, request):
    #     queryset = super().get_queryset(request)
    #     return


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
    model = AlboProductModel
    extra = 1
    fields = 'uniq_code', 'describe', 'price_sample', 'full_url', 'url_describe', 'url_image_albo', 'image_tag', 'size_field', 'quantity'
    readonly_fields = 'full_url', 'image_tag', 'quantity'

    def get_queryset(self, request):
        my_query = super().get_queryset(request)
        if request.user.categoryproductexclude_set.exists():
            list_exclude = request.user.categoryproductexclude_set.values_list('exclude_category__name_category')
            my_query = AlboProductModel.objects.exclude(category_product__name_category__in=list_exclude)
        return my_query.order_by('size_field')

    def price_uniq(self, obj):
        discount = getattr(self.my_user_form, 'discount', 0)
        sample_price = obj.price_sample
        if obj.pk:
            return intcomma(round(sample_price - (sample_price * (discount / 100)), 2))
        return 0

    def url_describe(self, obj):
        if getattr(obj, 'url_describe'):
            return format_html("<a href='%s'>Ссылка на товар %s на сайте </a>" %
                               (obj.url_describe, str(obj.describe)[:20]))

    def image_tag(self, obj):
        if obj.url_image_albo:
            return mark_safe('<img src="%s" style="width:180px;height:180px;" />' % (obj.url_image_albo))
        return ''  # mark_safe('<img src="" alt="%s" style="width:60px; height:60px;" />' % "noimagefound")

    def formfield_for_dbfield(self, db_field, request, **kwargs):
        setattr(self, 'my_user_form', request.user)
        return super().formfield_for_choice_field(db_field, request, **kwargs)

    def field_price_intcomma(self, obj):
        return intcomma(round(obj.price_sample, 2))

    field_price_intcomma.short_description = _("Цена без скидки")

    price_uniq.short_description = _("Цена со скидкой")
    image_tag.short_description = _("Ссылка на товар")


class CategoryProductAdmin(ModelAdmin):
    inlines = [ProductInline, ]

    def get_queryset(self, request):
        my_query = super().get_queryset(request)
        if request.user.categoryproductexclude_set.exists():
            list_exclude = request.user.categoryproductexclude_set.values_list('exclude_category__name_category')
            my_query = CategoryProduct.objects.exclude(name_category__in=list_exclude)
        return my_query


class MyCategoryListFilter(SimpleListFilter):
    def queryset(self, request, queryset):
        return queryset
        # list_exclude = request.user.categoryproductexclude_set.values_list('exclude_category__name_category')
        # return queryset.exclude(category_product__name_category__in=list_exclude)


class SimpleHistoryShowDeletedFilter(SimpleListFilter):
    title = "Entries"
    parameter_name = "entries"

    def lookups(self, request, model_admin):
        return (
            ("deleted_only", "Only Deleted"),
        )


class ProjectProductAdmin(ModelAdmin):
    model = ProductModel
    list_display = ("uniq_code", "describe", "price_sample", "price_uniq", "full_url", 'image_tag')
    list_filter = ('category_product__name_category', "uniq_code", "price_sample",)

    # list_filter = (SimpleHistoryShowDeletedFilter,)

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

    def name_category_fields(self, obj):
        return obj.category_product.name_category

    def price_uniq(self, obj):
        discount = getattr(self.my_user_form, 'discount', 0)
        return intcomma(round(obj.price_sample - (obj.price_sample * (discount / 100)), 2))

    def discount(self, obj):
        return obj.my_user_form.discount

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


class OneCCodeModelInlines(StackedInline):
    model = OneCCodeModel
    extra = 1


class OneCCodeAlboModelInlines(StackedInline):
    model = OneCCodeAlboModel
    extra = 1


class AlboProductAdmin(ModelAdmin):
    inlines = [OneCCodeAlboModelInlines, ]
    model = AlboProductModel
    list_display = ("uniq_code", "describe", "field_price_intcomma", "full_url", "image_tag", "quantity")
    list_filter = ('category_product__name_category', "size_field")

    # list_filter = (SimpleHistoryShowDeletedFilter,)

    def get_queryset(self, request):
        my_query = super().get_queryset(request)
        if request.user.categoryproductexclude_set.exists():
            list_exclude = request.user.categoryproductexclude_set.values_list('exclude_category__name_category')
            my_query = AlboProductModel.objects.exclude(category_product__name_category__in=list_exclude)

        list_category = my_query.filter(category_product__name_category__isnull=False).values_list(
            'category_product__name_category', flat=True).distinct()
        list_query = []
        for name_category in list_category:
            list_query.append(my_query.filter(category_product__name_category=name_category).order_by('size_field'))
        query_sort = reduce(operator.or_, list_query)
        return query_sort

    def changelist_view(self, request, extra_context=None):
        # add user in my model admin
        setattr(self, 'my_user_form', request.user)
        return super().changelist_view(request, extra_context)

    def name_category_fields(self, obj):
        return obj.category_product.name_category

    def price_uniq(self, obj):
        discount = getattr(self.my_user_form, 'discount', 0)
        return intcomma(round(obj.price_sample - (obj.price_sample * (discount / 100)), 2))

    def discount(self, obj):
        return obj.my_user_form.discount

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        # if db_field.name == "name":
        #     kwargs["queryset"] = Model.objects.order_by('name')
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def field_price_intcomma(self, obj):
        return intcomma(round(obj.price_sample, 2))

    price_uniq.short_description = _("Цена со скидкой")
    field_price_intcomma.short_description = _("Цена")


class UniqCodeModelAdmin(ModelAdmin):
    inlines = [OneCCodeModelInlines, ]
    list_display = ("uniq_code", 'field_set')

    def field_set(self, obj):
        data = obj.oneccodemodel_set.values_list('uniq_code_one_c', flat=True)
        return ','.join(data)


class CategoryProductExcludeAdmin(ModelAdmin):
    model = CategoryProductExclude
    list_display = ("exclude_category", 'exclude_user')
    filter_dict = {'resolution_value': 'is_admin_customer'}

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "exclude_user":
            kwargs["queryset"] = MyUser.objects.filter(**self.filter_dict)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


class CustomerForMangerModelAdmin(CustomerModelAdmin):

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        return queryset.filter(manager_user=request.user)


class CustomerModelForGeneralAdmin(CustomerModelAdmin):
    # inlines = [CustInline, ]
    filter_dict = {'resolution_value': 'is_admin_customer'}
    fields = ('email', 'password', 'first_name', 'last_name', 'phone', 'name_company', 'user_position', 'discount',
              "manager_user")
    list_display = ("email", "first_name", "name_company", "phone", "user_position", "discount", "manager_user")
    list_filter = ("name_company", "discount")


class AlboProductForCustomerAdmin(AlboProductAdmin):
    inlines = []
    fields = ("uniq_code", "describe", "field_price_intcomma", "price_uniq", "full_url", "image_tag", "quantity")
    readonly_fields = "price_uniq", "full_url", "image_tag", "field_price_intcomma"
    list_display = ("uniq_code", "describe", "field_price_intcomma", "price_uniq", "full_url", "image_tag", "quantity")

class ProductInlineForCustomer(ProductInline):
    fields = 'uniq_code', 'describe', 'field_price_intcomma', 'price_uniq', 'full_url', 'url_describe', 'url_image_albo', 'image_tag', 'size_field', 'quantity'
    readonly_fields = 'full_url', 'price_uniq', 'image_tag', 'quantity', 'field_price_intcomma'
class CategoryProductForCustomerAdmin(CategoryProductAdmin):
    inlines = [ProductInlineForCustomer, ]


support_admin.register(UsersGeneralManager, GeneralModelAdmin)
support_admin.register(MyUser)
support_admin.register(AlboProductModel, AlboProductAdmin)
support_admin.register(ProductModel, ProjectProductAdmin)
support_admin.register(CategoryProduct, CategoryProductAdmin)
support_admin.register(UsersManager, ManagerModelAdmin)
support_admin.register(UsersCustomer, CustomerModelAdmin)
support_admin.register(UniqCodeModel, UniqCodeModelAdmin)
support_admin.register(PeriodicTimeModel)
support_admin.register(CategoryProductExclude)

general_admin.register(PeriodicTimeModel)
general_admin.register(UsersGeneralManager, GeneralModelAdmin)
general_admin.register(ProductModel, ProjectProductAdmin)
general_admin.register(CategoryProduct, CategoryProductAdmin)
general_admin.register(UsersCustomer, CustomerModelForGeneralAdmin)
general_admin.register(UsersManager, ManagerModelAdmin)
general_admin.register(UniqCodeModel, UniqCodeModelAdmin)
general_admin.register(CategoryProductExclude, CategoryProductExcludeAdmin)
general_admin.register(AlboProductModel, AlboProductAdmin)

manager_admin.register(ProductModel, ProjectProductAdmin)
manager_admin.register(CategoryProduct, CategoryProductAdmin)
manager_admin.register(UsersCustomer, CustomerForMangerModelAdmin)
manager_admin.disable_action('delete_selected')
manager_admin.register(CategoryProductExclude, CategoryProductExcludeAdmin)
manager_admin.register(UniqCodeModel, UniqCodeModelAdmin)
manager_admin.register(AlboProductModel, AlboProductAdmin)

customer_admin.disable_action('delete_selected')
# customer_admin.register(ProductModel, ProjectProductAdmin)
customer_admin.register(CategoryProduct, CategoryProductForCustomerAdmin)
customer_admin.register(AlboProductModel, AlboProductForCustomerAdmin)


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


support_admin.site_header = 'Albo Panel'
manager_admin.site_header = 'Albo Panel'
general_admin.site_header = 'Albo Panel'
customer_admin.site_header = 'Albo Panel'

support_admin.site_title = "Albo Admin Portal"
general_admin.site_title = "Albo Admin Portal"
manager_admin.site_title = "Albo Admin Portal"
customer_admin.site_title = "Albo Admin Portal"

support_admin.index_title = "Welcome to Albo Portal"
general_admin.index_title = "Welcome to Albo Portal"
manager_admin.index_title = "Welcome to Albo Portal"
customer_admin.index_title = "Welcome to Albo Portal"

support_admin.register(LogEntry, LogEntryAdmin)
support_admin.register(Group)
general_admin.register(UserActivityTrack)
support_admin.register(UserActivityTrack)
