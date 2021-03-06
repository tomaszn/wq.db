from . import router
from django.utils.http import urlquote
from django.urls import reverse


def version(request):
    return {'version': router.version}


def get_base_url():
    return reverse('wq:config-list').replace('/config/', '')


def get_wq_path(request):
    base_url = get_base_url()
    if base_url and not request.path.startswith(base_url):
        return None
    path = request.path.replace(base_url + "/", "")
    return path


def router_info(request):
    base_url = get_base_url()
    full_path = request.path
    path = get_wq_path(request)
    if not path:
        return {}
    if request.GET:
        path += "?" + request.GET.urlencode()

    info = {
        'base_url': base_url,
        'path': path,
        'path_enc': urlquote(path),
        'params': request.GET,
        'full_path': full_path,
        'full_path_enc': urlquote(full_path),
        'prev_path': '',  # Referer?
    }

    return {
        'rt': base_url,
        'svc': base_url,
        'router_info': info,
        'pages_info': info,  # FIXME: Remove in 2.0
    }


# FIXME: Remove in 2.0
def pages_info(request):
    return router_info(request)


def wq_config(request):
    path = get_wq_path(request)
    if not path:
        return {}
    parts = path.split('/')
    user = request.user if request.user.is_authenticated else None
    wq_conf = router.get_config(user=user)
    page_conf = None
    root_conf = None

    for name, conf in wq_conf['pages'].items():
        if parts[0] == conf['url']:
            page_conf = conf
        elif conf['url'] == "":
            root_conf = conf

    if not page_conf and root_conf and len(parts) == 1:
        page_conf = root_conf

    return {
        'wq_config': wq_conf,
        'page_config': page_conf,
    }
