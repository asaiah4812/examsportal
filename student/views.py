from django.shortcuts import render,redirect,reverse
from . import forms,models
from django.db.models import Sum
from django.contrib.auth.models import Group
from django.http import HttpResponseRedirect
from django.contrib.auth.decorators import login_required,user_passes_test
from django.conf import settings
from datetime import date, timedelta
from exam import models as QMODEL
from teacher import models as TMODEL
from django.contrib import messages
import json


#for showing signup/login button for student
def studentclick_view(request):
    if request.user.is_authenticated:
        return HttpResponseRedirect('afterlogin')
    return render(request,'student/studentclick.html')

def student_signup_view(request):
    userForm=forms.StudentUserForm()
    studentForm=forms.StudentForm()
    mydict={'userForm':userForm,'studentForm':studentForm}
    if request.method=='POST':
        userForm=forms.StudentUserForm(request.POST)
        studentForm=forms.StudentForm(request.POST,request.FILES)
        if userForm.is_valid() and studentForm.is_valid():
            user=userForm.save()
            user.set_password(user.password)
            user.save()
            student=studentForm.save(commit=False)
            student.user=user
            student.save()
            my_student_group = Group.objects.get_or_create(name='STUDENT')
            my_student_group[0].user_set.add(user)
        return HttpResponseRedirect('studentlogin')
    return render(request,'student/studentsignup.html',context=mydict)

def is_student(user):
    return user.groups.filter(name='STUDENT').exists()

@login_required(login_url='studentlogin')
@user_passes_test(is_student)
def student_dashboard_view(request):
    dict={
    
    'total_course':QMODEL.Course.objects.all().count(),
    'total_question':QMODEL.Question.objects.all().count(),
    }
    return render(request,'student/student_dashboard.html',context=dict)

@login_required(login_url='studentlogin')
@user_passes_test(is_student)
def student_exam_view(request):
    courses=QMODEL.Course.objects.all()
    return render(request,'student/student_exam.html',{'courses':courses})

@login_required(login_url='studentlogin')
@user_passes_test(is_student)
def take_exam_view(request,pk):
    course=QMODEL.Course.objects.get(id=pk)
    total_questions=QMODEL.Question.objects.all().filter(course=course).count()
    questions=QMODEL.Question.objects.all().filter(course=course)
    total_marks=0
    for q in questions:
        total_marks=total_marks + q.marks
    
    return render(request,'student/take_exam.html',{'course':course,'total_questions':total_questions,'total_marks':total_marks})

@login_required(login_url='studentlogin')
@user_passes_test(is_student)
def start_exam_view(request,pk):
    try:
        course = QMODEL.Course.objects.get(id=pk)
        questions = QMODEL.Question.objects.filter(course=course).order_by('?')  # Randomize questions
        
        if not questions.exists():
            messages.error(request, 'No questions available for this course!')
            return HttpResponseRedirect(reverse('student-exam'))
        
        total_marks = sum(q.marks for q in questions)
        
        # Check if student has already taken this exam
        student = models.Student.objects.get(user_id=request.user.id)
        existing_result = QMODEL.Result.objects.filter(student=student, exam=course).first()
        if existing_result:
            messages.warning(request, 'You have already taken this exam!')
            return HttpResponseRedirect(reverse('view-result'))
        
        context = {
            'course': course, 
            'questions': questions,
            'total_marks': total_marks
        }
        
        # Debug: Print questions data
        print(f"Course: {course.course_name}")
        print(f"Number of questions: {questions.count()}")
        for i, q in enumerate(questions[:3]):  # Print first 3 questions for debugging
            print(f"Question {i+1}: {q.question[:50]}...")
        
        response = render(request,'student/start_exam.html', context)
        response.set_cookie('course_id', course.id)
        return response
        
    except QMODEL.Course.DoesNotExist:
        messages.error(request, 'Course not found!')
        return HttpResponseRedirect(reverse('student-exam'))
    except models.Student.DoesNotExist:
        messages.error(request, 'Student profile not found!')
        return HttpResponseRedirect(reverse('student-exam'))
    except Exception as e:
        messages.error(request, f'An error occurred: {str(e)}')
        return HttpResponseRedirect(reverse('student-exam'))

@login_required(login_url='studentlogin')
@user_passes_test(is_student)
def calculate_marks_view(request):
    if request.method == 'POST':
        course_id = request.POST.get('course_id')
        if not course_id:
            messages.error(request, 'Invalid exam submission!')
            return HttpResponseRedirect(reverse('student-exam'))
        
        try:
            course = QMODEL.Course.objects.get(id=course_id)
            questions = QMODEL.Question.objects.filter(course=course)
            
            total_marks = 0
            correct_answers = 0
            total_questions = questions.count()
            
            for question in questions:
                # Get the selected answer from POST data
                selected_ans = request.POST.get(f'question{question.id}')
                actual_answer = question.answer
                
                if selected_ans and selected_ans == actual_answer:
                    total_marks += question.marks
                    correct_answers += 1
            
            # Save the result
            student = models.Student.objects.get(user_id=request.user.id)
            
            # Check if result already exists (prevent duplicate submissions)
            existing_result = QMODEL.Result.objects.filter(student=student, exam=course).first()
            if existing_result:
                messages.warning(request, 'You have already taken this exam!')
                return HttpResponseRedirect(reverse('view-result'))
            
            result = QMODEL.Result()
            result.marks = total_marks
            result.exam = course
            result.student = student
            result.save()
            
            # Store result details in session for display
            request.session['exam_result'] = {
                'course_name': course.course_name,
                'total_marks': total_marks,
                'correct_answers': correct_answers,
                'total_questions': total_questions,
                'percentage': round((total_marks / course.total_marks) * 100, 2) if course.total_marks > 0 else 0
            }
            
            # Clear cookies
            response = HttpResponseRedirect(reverse('view-result'))
            response.delete_cookie('course_id')
            
            # Clear any question cookies that might exist
            for question in questions:
                response.delete_cookie(f'question{course.id}_{question.id}')
            
            messages.success(request, f'Exam submitted successfully! You scored {total_marks} marks.')
            return response
            
        except QMODEL.Course.DoesNotExist:
            messages.error(request, 'Course not found!')
            return HttpResponseRedirect(reverse('student-exam'))
        except Exception as e:
            messages.error(request, 'An error occurred while processing your exam!')
            return HttpResponseRedirect(reverse('student-exam'))
    else:
        messages.error(request, 'Invalid request method!')
        return HttpResponseRedirect(reverse('student-exam'))

@login_required(login_url='studentlogin')
@user_passes_test(is_student)
def view_result_view(request):
    student = models.Student.objects.get(user_id=request.user.id)
    results = QMODEL.Result.objects.filter(student=student).order_by('-date')
    
    # Get the latest exam result from session if available
    latest_result = request.session.pop('exam_result', None)
    
    # Calculate performance statistics
    performance_stats = None
    if results:
        total_percentage = 0
        best_percentage = 0
        
        for result in results:
            if result.exam.total_marks > 0:
                percentage = (result.marks / result.exam.total_marks) * 100
                total_percentage += percentage
                if percentage > best_percentage:
                    best_percentage = percentage
        
        average_percentage = total_percentage / len(results) if results else 0
        
        performance_stats = {
            'average_percentage': round(average_percentage, 2),
            'best_percentage': round(best_percentage, 2),
            'total_exams': len(results)
        }
    
    context = {
        'results': results,
        'latest_result': latest_result,
        'performance_stats': performance_stats
    }
    return render(request,'student/view_result.html', context)

    

@login_required(login_url='studentlogin')
@user_passes_test(is_student)
def check_marks_view(request, pk):
    course = QMODEL.Course.objects.get(id=pk)
    student = models.Student.objects.get(user_id=request.user.id)
    results = QMODEL.Result.objects.all().filter(exam=course).filter(student=student)
    
    # # Debugging: Print what we found
    # print(f"Course: {course.course_name}")
    # print(f"Student: {student.get_name}")
    # print(f"Results count: {results.count()}")
    for result in results:
        print(f"Result: {result}, Marks: {result.marks}, Exam: {result.exam}")
    
    return render(request, 'student/check_marks.html', {'results': results})

@login_required(login_url='studentlogin')
@user_passes_test(is_student)
def student_marks_view(request):
    # Get current student
    student = models.Student.objects.get(user_id=request.user.id)

    # All results for this student
    results_qs = QMODEL.Result.objects.filter(student=student).order_by('-date')

    # Courses the student has taken (distinct via result records)
    course_ids = results_qs.values_list('exam_id', flat=True)
    courses = QMODEL.Course.objects.filter(id__in=course_ids)

    # Total available courses in the system
    total_courses = QMODEL.Course.objects.count()

    # Latest score percentage if any result exists
    latest_score = None
    if results_qs.exists():
        latest = results_qs.first()
        if latest.exam.total_marks > 0:
            latest_score = round((latest.marks / latest.exam.total_marks) * 100)

    context = {
        'courses': courses,
        'total_courses': total_courses,
        'latest_score': latest_score,
    }
    return render(request,'student/student_marks.html', context)
  