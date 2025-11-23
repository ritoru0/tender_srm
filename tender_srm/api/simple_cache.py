from django.core.cache import cache
from django.conf import settings
from functools import wraps

def cache_page(timeout=None):
    """ 
    декоратор для кеширования страниц
    используется для данных, которые редко меняются
    """
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):

            if request.method != 'GET':
                return view_func(request, *args, **kwargs)
            
            cache_key = f"{request.path}_{request.user.id}"
            
            response = cache.get(cache_key)
            if response is not None:
                return response
            
            response = view_func(request, *args, **kwargs)
            
            if response.status_code == 200:
                cache.set(cache_key, response, timeout or settings.CACHE_TTL)
            
            return response
        return _wrapped_view
    return decorator

def clear_cache_for_user(user_id, pattern=None):
    """Очистка кеша для конкретного пользователя"""
    pass

def clear_all_cache():
    """Очистка всего кеша"""
    cache.clear()