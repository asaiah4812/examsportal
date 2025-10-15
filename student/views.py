# student/views.py
from django.shortcuts import render, redirect, reverse
from . import forms, models
from django.db.models import Sum
from django.contrib.auth.models import Group
from django.http import HttpResponseRedirect
from django.contrib.auth.decorators import login_required, user_passes_test
from django.conf import settings
from datetime import date, timedelta
from exam import models as QMODEL
from teacher import models as TMODEL
from django.contrib import messages
import json
import random

# For showing signup/login button for student
def studentclick_view(request):
    if request.user.is_authenticated:
        return HttpResponseRedirect('afterlogin')
    return render(request, 'student/studentclick.html')

def student_signup_view(request):
    userForm = forms.StudentUserForm()
    studentForm = forms.StudentForm()
    mydict = {'userForm': userForm, 'studentForm': studentForm}
    
    if request.method == 'POST':
        userForm = forms.StudentUserForm(request.POST)
        studentForm = forms.StudentForm(request.POST, request.FILES)
        
        if userForm.is_valid() and studentForm.is_valid():
            # Save user with commit=False to get the user instance without saving to DB
            user = userForm.save(commit=False)
            user.username = user.username.lower()
            
            # Set password properly using raw password from form
            raw_password = userForm.cleaned_data.get('password')
            user.set_password(raw_password)
            user.save()
            
            # Create student profile
            student = studentForm.save(commit=False)
            student.user = user
            student.save()
            
            # Add to STUDENT group
            my_student_group, created = Group.objects.get_or_create(name='STUDENT')
            my_student_group.user_set.add(user)
            
            # Add success message and redirect
            messages.success(request, "Student account created successfully!")
            return HttpResponseRedirect('studentlogin')
        else:
            # Show form errors
            mydict['userForm'] = userForm
            mydict['studentForm'] = studentForm
            messages.error(request, "Please correct the errors below.")
    
    return render(request, 'student/studentsignup.html', context=mydict)

def is_student(user):
    return user.groups.filter(name='STUDENT').exists()

@login_required(login_url='studentlogin')
@user_passes_test(is_student)
def student_dashboard_view(request):
    # Get student object with related data
    student = models.Student.objects.select_related('department').get(user_id=request.user.id)
    
    # Only count courses and questions for student's department and active courses
    courses_qs = QMODEL.Course.objects.filter(active=True)
    if student.department_id:
        courses_qs = courses_qs.filter(department_id=student.department_id)
    
    total_course = courses_qs.count()
    total_question = QMODEL.Question.objects.filter(course__in=courses_qs).count()
    
    # Get upcoming exams - format them for the template
    upcoming_exams = []
    for course in courses_qs:
        upcoming_exams.append({
            'id': course.id,
            'title': course.course_name,
            'course': course.course_code if course.course_code else course.course_name,
            'date': course.year,  # Using year as date since no specific date field
            'duration': 60,  # Default duration, you can modify this
            'questions': course.question_number
        })
    
    # Get recent results and format them
    recent_results_db = QMODEL.Result.objects.filter(student=student).select_related('exam').order_by('-date')[:5]
    recent_results = []
    for result in recent_results_db:
        # Calculate percentage
        percentage = (result.marks / result.exam.total_marks) * 100
        
        # Determine grade
        if percentage >= 70:
            grade = "A - Excellent"
        elif percentage >= 60:
            grade = "B - Very Good"
        elif percentage >= 50:
            grade = "C - Good"
        elif percentage >= 45:
            grade = "D - Pass"
        else:
            grade = "F - Fail"
            
        recent_results.append({
            'title': result.exam.course_name,
            'course': result.exam.course_code if result.exam.course_code else result.exam.course_name,
            'score': round(percentage, 1),
            'grade': grade
        })
    
    context = {
        'student': student,
        'total_course': total_course,
        'total_question': total_question,
        'upcoming_exams': upcoming_exams,
        'recent_results': recent_results,
    }
    return render(request, 'student/student_dashboard.html', context=context)

@login_required(login_url='studentlogin')
@user_passes_test(is_student)
def student_exam_view(request):
    # Only show active courses for student's department
    student = models.Student.objects.get(user_id=request.user.id)
    courses = QMODEL.Course.objects.filter(active=True)
    if student.department_id:
        courses = courses.filter(department_id=student.department_id)
    return render(request, 'student/student_exam.html', {'courses': courses})

@login_required(login_url='studentlogin')
@user_passes_test(is_student)
def take_exam_view(request, pk):
    student = models.Student.objects.get(user_id=request.user.id)
    try:
        # Only allow access to active course in student's department
        course = QMODEL.Course.objects.get(id=pk, active=True, department_id=student.department_id)
    except QMODEL.Course.DoesNotExist:
        messages.error(request, "You are not allowed to view this course or it does not exist.")
        return HttpResponseRedirect(reverse('student-exam'))
    questions = QMODEL.Question.objects.filter(course=course)
    total_questions = questions.count()
    total_marks = sum(q.marks for q in questions)
    return render(request, 'student/take_exam.html', {'course': course, 'total_questions': total_questions, 'total_marks': total_marks})

@login_required(login_url='studentlogin')
@user_passes_test(is_student)
def start_exam_view(request, pk):
    try:
        student = models.Student.objects.get(user_id=request.user.id)
        # Only allow access to active course in student's department
        course = QMODEL.Course.objects.get(id=pk, active=True, department_id=student.department_id)
        
        # Get questions and shuffle them randomly
        questions = list(QMODEL.Question.objects.filter(course=course))
        
        # Use Python's random.shuffle for true randomization
        random.shuffle(questions)
        
        # Also shuffle options for each question
        for question in questions:
            options = [
                ('Option1', question.option1),
                ('Option2', question.option2),
                ('Option3', question.option3),
                ('Option4', question.option4)
            ]
            random.shuffle(options)
            
            # Store shuffled options in the question object
            question.shuffled_options = options
            # Find the new position of the correct answer
            for idx, (option_key, _) in enumerate(options):
                if option_key == question.answer:
                    question.correct_answer_index = idx
                    break
        
        if not questions:
            messages.error(request, 'No questions available for this course!')
            return HttpResponseRedirect(reverse('student-exam'))
        
        total_marks = sum(q.marks for q in questions)
        
        # Check if student has already taken this exam
        existing_result = QMODEL.Result.objects.filter(student=student, exam=course).first()
        if existing_result:
            messages.warning(request, 'You have already taken this exam!')
            return HttpResponseRedirect(reverse('view-result'))
        
        # Store shuffled question mapping in session for grading
        request.session['shuffled_questions'] = {
            'course_id': course.id,
            'questions': [
                {
                    'id': q.id,
                    'correct_index': q.correct_answer_index
                } for q in questions
            ]
        }
        
        context = {
            'course': course,
            'questions': questions,
            'total_marks': total_marks
        }
        response = render(request, 'student/start_exam.html', context)
        response.set_cookie('course_id', course.id)
        return response
        
    except QMODEL.Course.DoesNotExist:
        messages.error(request, 'Course not found or not available for your department!')
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
            student = models.Student.objects.get(user_id=request.user.id)
            # Only allow calculation for active course in student's department
            course = QMODEL.Course.objects.get(id=course_id, active=True, department_id=student.department_id)
            
            # Get the shuffled question mapping from session
            shuffled_data = request.session.get('shuffled_questions', {})
            if not shuffled_data or shuffled_data.get('course_id') != int(course_id):
                messages.error(request, 'Exam session expired or invalid!')
                return HttpResponseRedirect(reverse('student-exam'))
            
            questions = QMODEL.Question.objects.filter(course=course)
            total_marks = 0
            correct_answers = 0
            total_questions = questions.count()
            
            # Calculate marks based on shuffled options
            for question_data in shuffled_data['questions']:
                question_id = question_data['id']
                correct_index = question_data['correct_index']
                
                selected_index = request.POST.get(f'question{question_id}')
                if selected_index and selected_index.isdigit():
                    selected_index = int(selected_index)
                    
                    if selected_index == correct_index:
                        question = questions.get(id=question_id)
                        total_marks += question.marks
                        correct_answers += 1
            
            # Save the result
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
            
            # Clear session data and cookies
            if 'shuffled_questions' in request.session:
                del request.session['shuffled_questions']
            
            response = HttpResponseRedirect(reverse('view-result'))
            response.delete_cookie('course_id')
            
            messages.success(request, f'Exam submitted successfully! You scored {total_marks} marks.')
            return response
            
        except QMODEL.Course.DoesNotExist:
            messages.error(request, 'Course not found or not available for your department!')
            return HttpResponseRedirect(reverse('student-exam'))
        except Exception as e:
            messages.error(request, f'An error occurred while processing your exam: {str(e)}')
            return HttpResponseRedirect(reverse('student-exam'))
    else:
        messages.error(request, 'Invalid request method!')
        return HttpResponseRedirect(reverse('student-exam'))

@login_required(login_url='studentlogin')
@user_passes_test(is_student)
def view_result_view(request):
    student = models.Student.objects.get(user_id=request.user.id)
    # Only show results for active courses in student's department
    courses_qs = QMODEL.Course.objects.filter(active=True)
    if student.department_id:
        courses_qs = courses_qs.filter(department_id=student.department_id)
    results = QMODEL.Result.objects.filter(student=student, exam__in=courses_qs).order_by('-date')
    latest_result = request.session.pop('exam_result', None)
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
    return render(request, 'student/view_result.html', context)

@login_required(login_url='studentlogin')
@user_passes_test(is_student)
def check_marks_view(request, pk):
    student = models.Student.objects.get(user_id=request.user.id)
    try:
        # Only allow access to active course in student's department
        course = QMODEL.Course.objects.get(id=pk, active=True, department_id=student.department_id)
    except QMODEL.Course.DoesNotExist:
        messages.error(request, "You are not allowed to view this course or it does not exist.")
        return HttpResponseRedirect(reverse('student-exam'))
    results = QMODEL.Result.objects.filter(exam=course, student=student)
    for result in results:
        print(f"Result: {result}, Marks: {result.marks}, Exam: {result.exam}")
    return render(request, 'student/check_marks.html', {'results': results})

@login_required(login_url='studentlogin')
@user_passes_test(is_student)
def student_marks_view(request):
    # Get current student
    student = models.Student.objects.get(user_id=request.user.id)
    # Only consider results for active courses in student's department
    courses_qs = QMODEL.Course.objects.filter(active=True)
    if student.department_id:
        courses_qs = courses_qs.filter(department_id=student.department_id)
    results_qs = QMODEL.Result.objects.filter(student=student, exam__in=courses_qs).order_by('-date')
    # Courses the student has taken (distinct via result records)
    course_ids = results_qs.values_list('exam_id', flat=True)
    courses = QMODEL.Course.objects.filter(id__in=course_ids, active=True)
    if student.department_id:
        courses = courses.filter(department_id=student.department_id)
    # Total available courses in the system for this department and active
    total_courses = QMODEL.Course.objects.filter(active=True, department_id=student.department_id).count()
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
    return render(request, 'student/student_marks.html', context)