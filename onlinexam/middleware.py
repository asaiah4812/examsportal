# middleware.py
from django.http import HttpResponseNotFound
from django.template import loader
from django.conf import settings

class Custom404Middleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        
        # Only show custom 404 for actual 404 responses
        if response.status_code == 404 and settings.DEBUG:
            # Check if this is a valid URL that should exist
            # Don't interfere with static files or media
            if not request.path.startswith('/static/') and not request.path.startswith('/media/'):
                template = loader.get_template('404.html')
                return HttpResponseNotFound(template.render({
                    'request': request,
                    'user': request.user
                }))
        return response