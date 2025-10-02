from django.db import models
import datetime
from django.contrib.auth.models import AbstractUser
from django.core.validators import RegexValidator


class User(AbstractUser):
    # override username field
    username = models.CharField(
        max_length=150,
        unique=True,
        # Regex that accepts almost everything except whitespace:
        validators=[
            RegexValidator(
                regex=r'^[^\s]+$',
                message='Username cannot contain spaces.'
            )
        ]
    )


    def __str__(self):
        return f"{self.username}"

def get_year_choices():
    current_year = datetime.datetime.now().year
    # Generate a list of years from current year to current year + 10
    return [(str(year), str(year)) for year in range(current_year, current_year + 11)]

class Department(models.Model):
   name = models.CharField(max_length=100, unique=True)
   
   class Meta:
       verbose_name = 'Program'
       verbose_name_plural = 'Programs'

   def __str__(self):
        return self.name

class Semester(models.Model):
   FIRST = 'FIRST'
   SECOND = 'SECOND'
   SEMESTER_CHOICES = (
        (FIRST, 'First'),
        (SECOND, 'Second'),
   )
   name = models.CharField(max_length=20, choices=SEMESTER_CHOICES, unique=True, default=FIRST)

   def __str__(self):
        return self.get_name_display()

class Course(models.Model):
   course_name = models.CharField(max_length=50)
   course_code = models.CharField(max_length=20, blank=True, null=True)
   question_number = models.PositiveIntegerField()
   total_marks = models.PositiveIntegerField()
   department = models.ForeignKey(Department, on_delete=models.PROTECT, null=True, blank=True)
   semester = models.ForeignKey(Semester, on_delete=models.PROTECT, null=True, blank=True)
   active = models.BooleanField(default=True)
   year = models.CharField(
       max_length=4,
       choices=get_year_choices(),
       default=str(datetime.datetime.now().year)
   )

   def __str__(self):
        return self.course_name + " " + self.year 

class Question(models.Model):
    course=models.ForeignKey(Course,on_delete=models.CASCADE)
    marks=models.PositiveIntegerField()
    question=models.CharField(max_length=600)
    option1=models.CharField(max_length=200)
    option2=models.CharField(max_length=200)
    option3=models.CharField(max_length=200)
    option4=models.CharField(max_length=200)
    cat=(('Option1','Option1'),('Option2','Option2'),('Option3','Option3'),('Option4','Option4'))
    answer=models.CharField(max_length=200,choices=cat)
    
    def __str__(self):
        return self.question
    
    
class Result(models.Model):
    student = models.ForeignKey('student.Student',on_delete=models.CASCADE)
    exam = models.ForeignKey(Course,on_delete=models.CASCADE)
    marks = models.PositiveIntegerField()
    date = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.student} - {self.exam} - {self.marks}"
