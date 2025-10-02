from django.contrib import admin
from .models import Result, Question, Course, Department, Semester
# Register your models here.

admin.site.register([Result, Question, Course, Department, Semester])
