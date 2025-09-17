from django.shortcuts import render,redirect,reverse
from . import forms,models
from django.db.models import Sum
from django.contrib.auth.models import Group
from django.http import HttpResponseRedirect
from django.contrib.auth.decorators import login_required,user_passes_test
from django.conf import settings
from datetime import date, timedelta
from exam import models as QMODEL
from student import models as SMODEL
from exam import forms as QFORM
from django.http import HttpResponse
import openpyxl
import io
from django.db.models import Sum


#for showing signup/login button for teacher
def teacherclick_view(request):
    if request.user.is_authenticated:
        return HttpResponseRedirect('afterlogin')
    return render(request,'teacher/teacherclick.html')

def teacher_signup_view(request):
    userForm=forms.TeacherUserForm()
    teacherForm=forms.TeacherForm()
    mydict={'userForm':userForm,'teacherForm':teacherForm}
    if request.method=='POST':
        userForm=forms.TeacherUserForm(request.POST)
        teacherForm=forms.TeacherForm(request.POST,request.FILES)
        if userForm.is_valid() and teacherForm.is_valid():
            user=userForm.save()
            user.set_password(user.password)
            user.save()
            teacher=teacherForm.save(commit=False)
            teacher.user=user
            teacher.save()
            my_teacher_group = Group.objects.get_or_create(name='TEACHER')
            my_teacher_group[0].user_set.add(user)
        return HttpResponseRedirect('teacherlogin')
    return render(request,'teacher/teachersignup.html',context=mydict)



def is_teacher(user):
    return user.groups.filter(name='TEACHER').exists()

@login_required(login_url='teacherlogin')
@user_passes_test(is_teacher)
def teacher_dashboard_view(request):
    dict={
    
    'total_course':QMODEL.Course.objects.all().count(),
    'total_question':QMODEL.Question.objects.all().count(),
    'total_student':SMODEL.Student.objects.all().count()
    }
    return render(request,'teacher/teacher_dashboard.html',context=dict)

@login_required(login_url='teacherlogin')
@user_passes_test(is_teacher)
def teacher_exam_view(request):
    return render(request,'teacher/teacher_exam.html')


@login_required(login_url='teacherlogin')
@user_passes_test(is_teacher)
def teacher_add_exam_view(request):
    courseForm=QFORM.CourseForm()
    if request.method=='POST':
        courseForm=QFORM.CourseForm(request.POST)
        if courseForm.is_valid():        
            courseForm.save()
        else:
            print("form is invalid")
        return HttpResponseRedirect('/teacher/teacher-view-exam')
    return render(request,'teacher/teacher_add_exam.html',{'courseForm':courseForm})

@login_required(login_url='teacherlogin')
@user_passes_test(is_teacher)
def teacher_view_exam_view(request):
    courses = QMODEL.Course.objects.all()
    return render(request,'teacher/teacher_view_exam.html',{'courses':courses})

@login_required(login_url='teacherlogin')
@user_passes_test(is_teacher)
def delete_exam_view(request,pk):
    course=QMODEL.Course.objects.get(id=pk)
    course.delete()
    return HttpResponseRedirect('/teacher/teacher-view-exam')

@login_required(login_url='adminlogin')
def teacher_question_view(request):
    return render(request,'teacher/teacher_question.html')

@login_required(login_url='teacherlogin')
@user_passes_test(is_teacher)
def teacher_add_question_view(request):
    questionForm=QFORM.QuestionForm()
    if request.method=='POST':
        questionForm=QFORM.QuestionForm(request.POST)
        if questionForm.is_valid():
            question=questionForm.save(commit=False)
            course=QMODEL.Course.objects.get(id=request.POST.get('courseID'))
            question.course=course
            question.save()       
        else:
            print("form is invalid")
        return HttpResponseRedirect('/teacher/teacher-view-question')
    return render(request,'teacher/teacher_add_question.html',{'questionForm':questionForm})

@login_required(login_url='teacherlogin')
@user_passes_test(is_teacher)
def teacher_view_question_view(request):
    courses= QMODEL.Course.objects.all()
    return render(request,'teacher/teacher_view_question.html',{'courses':courses})

@login_required(login_url='teacherlogin')
@user_passes_test(is_teacher)
def see_question_view(request,pk):
    questions=QMODEL.Question.objects.all().filter(course_id=pk)
    return render(request,'teacher/see_question.html',{'questions':questions})

@login_required(login_url='teacherlogin')
@user_passes_test(is_teacher)
def remove_question_view(request,pk):
    question=QMODEL.Question.objects.get(id=pk)
    question.delete()
    return HttpResponseRedirect('/teacher/teacher-view-question')


def logout(request):
    from django.contrib.auth import logout
    from django.contrib import messages
    logout(request)
    messages.info(request, 'logout successfully')
    return redirect('/')


@login_required(login_url='teacherlogin')
@user_passes_test(is_teacher)
def teacher_bulk_upload_questions_view(request):
    if request.method == 'POST' and request.FILES.get('file'):
        file = request.FILES['file']
        course_id = request.POST.get('course_id')
        try:
            course = QMODEL.Course.objects.get(id=course_id)
        except QMODEL.Course.DoesNotExist:
            return render(request, 'teacher/bulk_upload.html', {
                'courses': QMODEL.Course.objects.all(),
                'error': 'Selected course not found.'
            })

        try:
            wb = openpyxl.load_workbook(file)
            ws = wb.active
            created = 0
            for idx, row in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
                question_text, option1, option2, option3, option4, answer, marks = row or (None,)*7
                if not question_text:
                    continue
                if answer not in ['Option1', 'Option2', 'Option3', 'Option4']:
                    continue
                try:
                    marks_int = int(marks) if marks is not None else 1
                except Exception:
                    marks_int = 1
                QMODEL.Question.objects.create(
                    course=course,
                    question=str(question_text)[:600],
                    option1=str(option1 or '')[:200],
                    option2=str(option2 or '')[:200],
                    option3=str(option3 or '')[:200],
                    option4=str(option4 or '')[:200],
                    answer=answer,
                    marks=marks_int
                )
                created += 1

            course.question_number = QMODEL.Question.objects.filter(course=course).count()
            course.total_marks = QMODEL.Question.objects.filter(course=course).aggregate(Sum('marks'))['marks__sum'] or 0
            course.save()

            return render(request, 'teacher/bulk_upload.html', {
                'courses': QMODEL.Course.objects.all(),
                'success': f'Successfully imported {created} questions into {course.course_name}.'
            })
        except Exception:
            return render(request, 'teacher/bulk_upload.html', {
                'courses': QMODEL.Course.objects.all(),
                'error': 'Failed to process file. Ensure it follows the sample format.'
            })

    return render(request, 'teacher/bulk_upload.html', {
        'courses': QMODEL.Course.objects.all()
    })


@login_required(login_url='teacherlogin')
@user_passes_test(is_teacher)
def teacher_download_sample_questions_excel(request):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = 'Questions'
    ws.append(['question', 'option1', 'option2', 'option3', 'option4', 'answer', 'marks'])
    ws.append(['What is 2 + 2?', '1', '2', '3', '4', 'Option4', 2])
    ws.append(['Capital of France?', 'Berlin', 'Madrid', 'Paris', 'Lisbon', 'Option3', 5])
    stream = io.BytesIO()
    wb.save(stream)
    stream.seek(0)
    response = HttpResponse(stream.read(), content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = 'attachment; filename="sample_questions.xlsx"'
    return response