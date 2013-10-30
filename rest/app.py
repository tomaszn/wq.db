from django.utils.importlib import import_module
from django.utils.module_loading import module_has_submodule
from django.conf.urls import patterns, include, url
from django.core.paginator import Paginator

from django.conf import settings
from rest_framework.routers import DefaultRouter, Route
from rest_framework.settings import api_settings
from rest_framework.response import Response

from .models import ContentType, get_ct
from .permissions import has_perm
from .views import SimpleViewSet, ModelViewSet


class Router(DefaultRouter):
    _models = set()
    _serializers = {}
    _querysets = {}
    _viewsets = {}
    _extra_pages = {}
    _custom_config = {}

    include_root_view = False
    include_config_view = True
    include_multi_view = True

    def __init__(self, trailing_slash=False):
        # Add trailing slash for list views
        self.routes.append(Route(
            url=r'^{prefix}/$',
            mapping={
                'get': 'list',
                'post': 'create'
            },
            name='{basename}-list',
            initkwargs={'suffix': 'List'}
        ))
        super(Router, self).__init__(trailing_slash=trailing_slash)

    def register_model(self, model, viewset=None, serializer=None,
                       queryset=None):
        self._models.add(model)
        if viewset:
            self.register_viewset(model, viewset)
        if serializer:
            self.register_serializer(model, serializer)
        if queryset:
            self.register_queryset(model, queryset)

        ct = get_ct(model)
        viewset = self.get_viewset_for_model(model)
        self.register(ct.urlbase, viewset, ct.identifier)

    def register_viewset(self, model, viewset):
        self._viewsets[model] = viewset

    def register_serializer(self, model, serializer):
        self._serializers[model] = serializer

    def register_queryset(self, model, queryset):
        self._querysets[model] = queryset

    def get_serializer_for_model(self, model_class, serializer_depth=None):
        if model_class in self._serializers:
            serializer = self._serializers[model_class]
        else:
            # Make sure we're not dealing with a proxy
            real_model = get_ct(model_class, True).model_class()
            if real_model in self._serializers:
                serializer = self._serializers[real_model]
            else:
                serializer = api_settings.DEFAULT_MODEL_SERIALIZER_CLASS

        class Serializer(serializer):
            class Meta(serializer.Meta):
                depth = serializer_depth
                model = model_class
        return Serializer

    def serialize(self, obj, many=False, depth=None):
        if many:
            # assume obj is a queryset
            model = obj.model
            if depth is None:
                depth = 0
        else:
            model = obj
            if depth is None:
                depth = 1
        serializer = self.get_serializer_for_model(model, depth)
        return serializer(obj, many=many, context={'router': self}).data

    def get_paginate_by_for_model(self, model_class):
        name = get_ct(model_class).identifier
        if name in self._custom_config:
            paginate_by = self._custom_config[name].get('per_page', None)
            if paginate_by:
                return paginate_by
        return api_settings.PAGINATE_BY

    def paginate(self, model, page_num, request=None):
        obj_serializer = self.get_serializer_for_model(model)
        paginate_by = self.get_paginate_by_for_model(model)
        paginator = Paginator(self.get_queryset_for_model(model), paginate_by)
        page = paginator.page(page_num)

        class Serializer(api_settings.DEFAULT_PAGINATION_SERIALIZER_CLASS):
            class Meta:
                object_serializer_class = obj_serializer
        return Serializer(
            instance=page,
            context={'router': self, 'request': request}
        ).data

    def get_queryset_for_model(self, model):
        if model in self._querysets:
            return self._querysets[model]
        return model.objects.all()

    def get_viewset_for_model(self, model_class):
        if model_class in self._viewsets:
            viewset = self._viewsets[model_class]
        else:
            # Make sure we're not dealing with a proxy
            real_model = get_ct(model_class, True).model_class()
            if real_model in self._viewsets:
                viewset = self._viewsets[real_model]
            else:
                viewset = ModelViewSet

        if get_ct(model_class).is_identified:
            lookup = 'primary_identifiers__slug'
        else:
            lookup = 'pk'

        class ViewSet(viewset):
            model = model_class
            router = self
            lookup_field = lookup

        return ViewSet

    def get_config(self, user):
        pages = {}
        for page in self._extra_pages:
            conf, view = self.get_page(page)
            pages[page] = conf
        for model in self._models:
            ct = get_ct(model)
            if not has_perm(user, ct, 'view'):
                continue
            info = {
                'name': ct.name,
                'url': ct.urlbase,
                'list': True,
                'parents': [],
                'children': []
            }
            for perm in ('add', 'change', 'delete'):
                if has_perm(user, ct, perm):
                    info['can_' + perm] = True

            for pct in ct.get_parents():
                if has_perm(user, pct, 'view'):
                    info['parents'].append(pct.identifier)

            for cct in ct.get_children():
                if has_perm(user, cct, 'view'):
                    info['children'].append(cct.identifier)

            for name in ('annotated', 'identified', 'located', 'related'):
                if getattr(ct, 'is_' + name):
                    info[name] = True

            if ct.is_located or ct.has_geo_fields:
                info['map'] = True

            for field in model._meta.fields:
                if field.choices:
                    info.setdefault('choices', {})
                    info['choices'][field.name] = [{
                        'value': val,
                        'label': unicode(label)
                    } for val, label in field.choices]

            for name in ('annotationtype', 'annotation'):
                if ct.identifier != name and getattr(ct, 'is_' + name):
                    pages[name] = {'alias': ct.identifier}

            if ct.identifier in self._custom_config:
                info.update(self._custom_config[ct.identifier])
            pages[ct.identifier] = info

        return {'pages': pages}

    def add_page(self, name, config, view=None):
        if view is None:
            class PageView(SimpleViewSet):
                template_name = name + '.html'

                def list(self, request, *args, **kwargs):
                    return Response(config)
            view = PageView
        url = config.get('url', name)
        self._extra_pages[name] = config, view
        self.register(url, view, name)

    def customize_page(self, name, config):
        self._custom_config[name] = config

    def get_page(self, page):
        return self._extra_pages[page]

    def get_page_config(self, name, user):
        config = self.get_config(user)
        return config['pages'].get(name, None)

    def get_config_view(self):
        class ConfigView(SimpleViewSet):
            def list(this, request, *args, **kwargs):
                return Response(self.get_config(request.user))
        return ConfigView

    def get_multi_view(self):
        class MultipleListView(SimpleViewSet):
            def list(this, request, *args, **kwargs):
                conf_by_url = {
                    conf['url']: (page, conf)
                    for page, conf
                    in self.get_config(request.user)['pages'].items()
                }
                urls = request.GET.get('lists', '').split(',')
                result = {}
                for url in urls:
                    if url not in conf_by_url:
                        continue
                    page, conf = conf_by_url[url]
                    ct = ContentType.objects.get(model=page)
                    cls = ct.model_class()
                    result[url] = self.paginate(cls, 1, request)
                return Response(result)
        return MultipleListView

    def get_urls(self):
        # Register a few extra views before returning urls

        if self.include_config_view:
            # /config.js
            self.register('config', self.get_config_view(), 'config')

        if self.include_multi_view:
            # /multi.json
            self.register('multi', self.get_multi_view(), 'multi')

        return super(Router, self).get_urls()

    def get_routes(self, viewset):
        routes = super(Router, self).get_routes(viewset)
        model = getattr(viewset, "model", None)
        if not model:
            return routes

        # Custom routes

        ct = get_ct(model)
        for pct in ct.get_all_parents():
            if pct.model_class() not in self._models:
                continue
            if pct.urlbase == '':
                purlbase = ''
            else:
                purlbase = pct.urlbase + '/'

            purl = (
                '^' + purlbase + r'(?P<' + pct.identifier
                + '>[^\/\?]+)/{prefix}{trailing_slash}$'
            )
            routes.append(Route(
                url=purl,
                mapping={'get': 'list'},
                name="{basename}-for-%s" % pct.identifier,
                initkwargs={'suffix': 'List'},
            ))

        for cct in ct.get_all_children():
            cbase = cct.urlbase
            routes.append(
                url='^%s-by-{prefix}' % cbase,
                mapping={'get': 'list'},
                name="%s-by-%s" % (cct.identifier, ct.identifier),
                initkwargs={'target': cbase, 'suffix': 'List'},
            )

        return routes

    @property
    def version(self):
        if not hasattr(self, '_version'):
            vtxt = getattr(settings, 'VERSION_TXT', None)
            if vtxt is None:
                self._version = None
            else:
                vfile = open(vtxt, 'r')
                self._version = vfile.read()
                vfile.close()
        return self._version

router = Router()


def autodiscover():
    for app_name in settings.INSTALLED_APPS:
        app = import_module(app_name)
        if module_has_submodule(app, 'serializers'):
            import_module(app_name + '.serializers')
    for app_name in settings.INSTALLED_APPS:
        app = import_module(app_name)
        if module_has_submodule(app, 'views'):
            import_module(app_name + '.views')
