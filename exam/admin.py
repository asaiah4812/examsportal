from django.contrib import admin
from .models import Result, Question, Course
# Register your models here.

admin.site.register([Result, Question, Course])
