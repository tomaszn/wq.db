from wq.db import rest
from .models import (
    RootModel, UserManagedModel, Parent, Child, ItemType, Item, GeometryModel,
    SlugModel,
)
from .serializers import RootModelSerializer

rest.router.register_model(
    RootModel,
    url="",
    lookup="slug",
    serializer=RootModelSerializer,
)
rest.router.register_model(UserManagedModel)
rest.router.register_model(Parent)
rest.router.register_model(Child, per_page=100)
rest.router.register_model(ItemType)
rest.router.register_model(Item)
rest.router.register_model(GeometryModel)
rest.router.register_model(SlugModel, lookup="code")
rest.router.set_extra_config(debug=True)

rest.router.add_page("rest_context", {})
rest.router.add_page("auth_context", {})
