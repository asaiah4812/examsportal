from django import forms
from django.contrib.auth import get_user_model
from . import models
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth import authenticate
from exam import models as QMODEL

User = get_user_model()

class StudentUserForm(forms.ModelForm):
    class Meta:
        model=User
        fields=['first_name','last_name','username','password']
        widgets = {
        'password': forms.PasswordInput()
        }

class StudentForm(forms.ModelForm):
    class Meta:
        model=models.Student
        fields=['address','mobile','department','profile_pic']


class StudentAuthenticationForm(AuthenticationForm):
    """Allow login with either username or student matric number."""
    def clean(self):
        cleaned_data = super().clean()
        identifier = self.cleaned_data.get('username')
        password = self.cleaned_data.get('password')

        if identifier and password:
            # Try normal username first
            user = authenticate(self.request, username=identifier.lower(), password=password)
            if user is None:
                # Try resolve by matric number -> username
                try:
                    student = models.Student.objects.select_related('user').get(username=identifier)
                    user = authenticate(self.request, username=student.user.username.lower(), password=password)
                    if user is not None:
                        # Replace the username field so downstream uses actual username
                        self.cleaned_data['username'] = student.user.username
                        return self.cleaned_data
                except models.Student.DoesNotExist:
                    # Fall through to default error raised by parent
                    pass

        return cleaned_data

