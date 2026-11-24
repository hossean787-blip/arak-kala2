"""Guest favorites migrate on customer login and remain scoped to that account."""
from django.db import transaction
from django.contrib.auth.signals import user_logged_in
from django.dispatch import receiver
from .models import Customer, Favorite, Product

MAX_FAVORITES = 100

def guest_ids(request):
    raw = request.session.get("favorites", [])
    return list(dict.fromkeys(i for i in raw if type(i) is int and 0 < i < 2**63))[:MAX_FAVORITES] if isinstance(raw, list) else []

def customer_for(request):
    return Customer.objects.filter(account=request.user).first() if request.user.is_authenticated else None

def favorite_ids(request):
    customer = customer_for(request)
    if customer is None:
        return guest_ids(request)
    return list(Favorite.objects.filter(customer=customer, product__active=True).values_list("product_id",flat=True)[:MAX_FAVORITES])

@receiver(user_logged_in, dispatch_uid="arak_merge_guest_favorites")
def merge_guest_favorites(sender, request, user, **kwargs):
    if request is None:
        return
    ids = guest_ids(request)
    customer = Customer.objects.filter(account=user).first()
    if not ids or customer is None:
        return
    with transaction.atomic():
        Customer.objects.select_for_update().get(pk=customer.pk)
        existing = set(Favorite.objects.filter(customer=customer).values_list("product_id",flat=True))
        valid = set(Product.objects.filter(active=True,pk__in=ids).values_list("pk",flat=True))
        new = [i for i in ids if i in valid and i not in existing][:max(0,MAX_FAVORITES-len(existing))]
        Favorite.objects.bulk_create([Favorite(customer=customer,product_id=i) for i in new],ignore_conflicts=True)
    request.session.pop("favorites",None)

def set_favorite(request, product, desired=None):
    customer=customer_for(request)
    if customer is None:
        ids=guest_ids(request)
        add = product.pk not in ids if desired is None else desired
        if add and product.pk not in ids:
            if len(ids)>=MAX_FAVORITES:
                return False
            ids.append(product.pk)
        if not add and product.pk in ids:
            ids.remove(product.pk)
        request.session["favorites"]=ids
        return True
    with transaction.atomic():
        Customer.objects.select_for_update().get(pk=customer.pk)
        records=Favorite.objects.filter(customer=customer)
        present=records.filter(product=product).exists()
        add = not present if desired is None else desired
        if add and not present:
            if records.count()>=MAX_FAVORITES:
                return False
            Favorite.objects.get_or_create(customer=customer,product=product)
        elif not add and present:
            records.filter(product=product).delete()
    return True
