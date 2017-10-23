from django.http import HttpResponse
from django.contrib.auth.models import User
from django.contrib.auth import authenticate, login, logout
from django.core.mail import send_mail
from django.db import IntegrityError

from grades import models
from djstripe.utils import subscriber_has_active_subscription
from email_confirm_la.models import EmailConfirmation

import datetime
from collections import namedtuple

def _register(request):
    name = request.POST["name"]
    email = request.POST["email"]
    password = request.POST["password"]
    password2 = request.POST['cpassword']
    grading_system = request.POST['gsys']
    #account_type = request.POST['account']

    if password == password2 and len(password) >= 8:
        try:
            user = User.objects.create_user(email, email, password)
        except IntegrityError:
            return None
        EmailConfirmation.objects.verify_email_for_object(email, user)
        user.is_active = False
        user.first_name = name
        user.save()
        now = datetime.datetime.now()
        valid = models.AccountValid.objects.get(id=1)
        grading_sys = models.GradingSystem.objects.get(id=grading_system)
        account_type = models.AccountType.objects.get(id=1)
        account = models.Accounts(user=user, create_date=now, valid=valid,
                grading_sys=grading_sys, account_type=account_type)
        account.save()

        return user

def confirm_email(email):
    user = User.objects.get(email=email)
    user.is_active = True
    user.save()

def is_premium(user, account):
    if account.sponsored:
        return True
    else:
        return subscriber_has_active_subscription(user)

def get_user(user_id):
    user = User.objects.get(id=user_id)
    return user

def get_account(user_id):
    user = User.objects.get(id=user_id)
    account = models.Accounts.objects.get(user=user)
    return account

def get_stylesheets():
    stylesheets = models.Stylesheet.objects.all()
    return stylesheets

def get_grading_systems():
    grading_systems = models.GradingSystem.objects.all().order_by('name')
    return grading_systems

def get_countries():
    countries = models.Country.objects.all().order_by('name')
    return countries

def get_account_types():
    account_types = models.AccountType.objects.all()
    return account_types

def get_semesters(user_id):
    account = get_account(user_id)
    semesters = models.Semesters.objects.all().filter(account=account)
    return semesters

def get_subjects(user_id):
    account = get_account(user_id)
    subjects = models.Subject.objects.all().filter(account=account)
    return subjects

def get_grades(user_id):
    account = get_account(user_id)
    grades = models.Grades.objects.all().filter(subject__account=account)\
        .order_by('date')
    return grades

def get_grades_date_desc(user_id):
    account = get_account(user_id)
    grades = models.Grades.objects.all().filter(subject__account=account)\
        .order_by('-date')
    return grades

def get_representations(user_id):
    account = get_account(user_id)
    representations = models.Representative.objects.all()\
        .filter(g=account.grading_sys)
    return representations

def get_calculative(user_id):
    account = get_account(user_id)
    calculative = models.Calculative.objects.get(g=account.grading_sys)
    return calculative

def get_semester_now(user_id):
    account = get_account(user_id)
    now = datetime.datetime.now()
    semester = models.Semesters.objects.filter(semester_start__lte=now,
                                               semester_end__gte=now,
                                               account=account)
    return semester

def get_subjects_for_semester(user_id, semester):
    account = get_account(user_id)
    subjects = get_subjects(user_id)
    subjects_list = []

    for subject in subjects:
        grades = models.Grades.objects.filter(
            date__gte=semester.semester_start, date__lte=semester.semester_end,
            subject=subject)
        if len(grades) > 0:
            average = 0;
            top_grade = 0;
            counter = 0;
            for grade in grades:
                average += (grade.score * grade.weight)
                counter += grade.weight
                if grade.score > top_grade:
                    top_grade = grade.score
            average = int(average / counter) if average != 0 else 0

            if account.grading_sys.type == 'c':
                grading_system = models.CalculativeDescrip.objects.all()\
                    .filter(c__g=account.grading_sys)
                representation = get_calculative_descrip(grading_system,
                                                         average)
                grade = resolve_grade_c(user_id, average)
                top_grade = resolve_grade_c(user_id, top_grade)
                output = {"representation": grade,
                          "legend": representation.legend}
                output2 = {"representation": top_grade}
            elif account.grading_sys.type == 'r':
                grading_system = models.Representative.objects.all()\
                    .filter(g=account.grading_sys)
                output = resolve_grade_r(grading_system, average)
                output2 = resolve_grade_r(grading_system, top_grade)
            subject.average = output
            subject.top_grade = output2
            subject.score = average
            subject.nr_grades = len(grades)
            subjects_list.append(subject)
    return subjects_list

def get_subjects_average(user_id, subjects):
    account = get_account(user_id)
    total_average = 0
    counter = 0
    for subject in subjects:
        total_average += (subject.score * subject.weight)
        counter += subject.weight
    try:
        total_average = int(total_average/counter)
    except ZeroDivisionError:
        total_average = 0
    if account.grading_sys.type == 'c':
        grading_system = models.CalculativeDescrip.objects.all().\
            filter(c__g=account.grading_sys)
        representation = get_calculative_descrip(grading_system, total_average)
        grade = resolve_grade_c(user_id, total_average)
        total_avg = {"representation": grade, "legend": representation.legend}
    elif account.grading_sys.type == 'r':
        grading_system = models.Representative.objects.all()\
            .filter(g=account.grading_sys)
        total_avg = resolve_grade_r(grading_system, total_average)
    return total_avg


def dashboard_logic(user_id):
    semester = get_semester_now(user_id)
    try:
        semester = semester[0]
        subjects = get_subjects_for_semester(user_id, semester)
        if len(subjects) == 0:
            output = {"no_data":True}
            return output

        now = datetime.datetime.now().date()
        # Get total average across all subjects
        total_avg = get_subjects_average(user_id, subjects)
        
        # semester progress in % * 100
        progress = int((semester.semester_start - now) / 
                       (semester.semester_start - semester.semester_end)*100)
        output = {"semester": semester, "progress": progress,
                  "subjects": subjects, "total_avg":total_avg}
    except IndexError:
        # If theres no data for user show different content in html (jinja)
        output = {"no_data":True}
    return output

def insights_logic(user_id):
    semesters = get_semesters(user_id)
    output = []
    for semester in semesters:
        subjects = get_subjects_for_semester(user_id, semester)
        total_avg = get_subjects_average(user_id, subjects)
        output.append({"semester": semester, "subjects": subjects,
                       "total_avg":total_avg})
    return output

def new_semester(request):
    start_date = request.POST["start"]
    end_date = request.POST["end"]
    name = request.POST["name"]
    start_date = datetime.datetime.strptime(start_date, '%m/%d/%Y').date()
    end_date = datetime.datetime.strptime(end_date, '%m/%d/%Y').date()
    user_id = request.session['member_id']
    account = get_account(user_id)
    semester_valid = check_semester(user_id, start_date, end_date, 0)
    if semester_valid:
        semester = models.Semesters(name=name, semester_start=start_date,
                                    semester_end=end_date, account=account)
        semester.save()
        return True
    else:
        return False

def edit_semester(request):
    id = request.POST["id"]
    name = request.POST["name"]
    start = request.POST["start"]
    end = request.POST["end"]
    start_date = datetime.datetime.strptime(start, '%m/%d/%Y').date()
    end_date = datetime.datetime.strptime(end, '%m/%d/%Y').date()
    user_id = request.session['member_id']
    semester_valid = check_semester(user_id, start_date, end_date, id)
    semester_owned = check_semester_ownership(user_id, id)
    if semester_valid and semester_owned:
        semester = models.Semesters.objects.get(id=id)
        semester.name = name
        semester.semester_start = datetime.datetime.strptime(start, '%m/%d/%Y')
        semester.semester_end = datetime.datetime.strptime(end , '%m/%d/%Y')
        semester.save()
        return True
    else:
        return False

def del_semester(request):
    semester_id = request.POST["id"]
    semester_owned = check_semester_ownership(request.session['member_id'],
                                              semester_id)
    if semester_owned:
        semester = models.Semesters.objects.get(id=semester_id)
        semester.delete()
        return True
    else:
        return False

def new_subject(request, user_id):
    name = request.POST["name"]
    weight = request.POST["weight"]
    account = get_account(request.session['member_id'])
    all_subjects = models.Subject.objects.all().filter(account=account)
    user = get_user(user_id)
    premium = is_premium(user, account)
    if len(all_subjects)>= 10 and premium == False:
        return "subjectlimit"
    else:
        subject = models.Subject(name=name, weight=weight, account=account)
        subject.save()
        return subject
    return None

def edit_subject(request):
    id = request.POST["id"]
    name = request.POST["name"]
    weight = request.POST["weight"]
    subject_owned = check_subject_ownership(request.session['member_id'], id)
    if subject_owned:
        subject = models.Subject.objects.get(id=id)
        subject.name = name
        subject.weight = weight
        subject.save()
        return True
    else:
        return False

def del_subject(request):
    subject_id = request.POST["id"]
    subject_owned = check_subject_ownership(request.session['member_id'],
                                            subject_id)
    if subject_owned:
        subject = models.Subject.objects.get(id=subject_id)
        subject.delete()
        return True
    else:
        return False

def new_grade(request):
    account = get_account(request.session['member_id'])
    grade = request.POST["grade"]
    total_points = request.POST["total_pts"]
    earned_points = request.POST["pts"]
    grade_percent = request.POST["percent"]
    subject_id = request.POST["subject"]
    weight = request.POST["weight"]
    subject = models.Subject.objects.get(id=subject_id)
    date = request.POST["date"]
    date = datetime.datetime.strptime(date, '%m/%d/%Y')
    note = request.POST["note"]
    subject_owned = check_subject_ownership(request.session['member_id'],
                                            subject_id)
    try:
        if subject_owned:
            if account.grading_sys.type == "c":
                #calculational
                grading_system = models.Calculative.objects\
                    .get(g=account.grading_sys)
                score = resolve_grade_percent_c(grading_system, grade,
                                                total_points, earned_points,
                                                grade_percent)
            elif account.grading_sys.type == "r":
                #representative
                grading_system = models.Representative.objects.all()\
                    .filter(g=account.grading_sys)
                score = resolve_grade_percent_r(grading_system, grade,
                                                total_points, earned_points,
                                                grade_percent)
            else:
                return None
            grade = models.Grades(subject=subject, note=note, date=date,
                                  weight=weight, score=score)
            grade.save()
            return grade
        else:
            return None
    except UnboundLocalError:
        return None

def edit_grade(request):
    account = get_account(request.session['member_id'])
    id = request.POST["id"]
    score = request.POST["grade"]
    subject_id = request.POST["subject"]
    date = request.POST["date"]
    weight = request.POST["weight"]
    date = datetime.datetime.strptime(date, '%m/%d/%Y')
    note = request.POST["note"]
    subject = models.Subject.objects.get(id=subject_id)
    grade_owned = check_grade_ownership(request.session['member_id'], id)
    subject_owned = check_subject_ownership(request.session['member_id'],
                                            subject_id)

    if grade_owned and subject_owned:
        if account.grading_sys.type == "c":
            #calculational
            grading_system = models.Calculative.objects\
                .get(g=account.grading_sys)
            score = resolve_grade_percent_c(grading_system, score, '', '', '')
        elif account.grading_sys.type == "r":
            #representative
            grading_system = models.Representative.objects.all()\
                .filter(g=account.grading_sys)
            score = resolve_grade_percent_r(grading_system, score, '', '', '')
        else:
            return False

        grade = models.Grades.objects.get(id=id)
        grade.score = score
        grade.subject = subject
        grade.date = date
        grade.weight = weight
        grade.note = note
        grade.save()
        return True
    else:
        return False

def del_grade(request):
    grade_id = request.POST["id"]
    grade_owned = check_grade_ownership(request.session['member_id'], grade_id)
    if grade_owned:
        grade = models.Grades.objects.get(id=grade_id)
        grade.delete()
        return True
    else:
        return False

def update_user_data(user_id, request):
    user = get_user(user_id)
    name = request.POST["name"]
    email = request.POST["email"]
    if len(name) > 0 and len(email) > 0:
        user.first_name = name
        user.username = email
        user.save()
        return True
    else:
        return False

def change_password(user_id, request):
    user = get_user(user_id)
    password = request.POST["password"]
    cpassword = request.POST["cpassword"]
    old_password = request.POST["old_password"]
    # Verify user
    _user = authenticate(username=user.username, password=old_password)
    if _user is not None and password == cpassword and len(password) >= 8:
        user.set_password(password)
        user.save()
        # Login user again as user is automatically logged out after 
        # password change
        user = authenticate(username=user.username, password=password)
        login(request, user)
        request.session['member_id'] = user.id
        return True
    else:
        return False

def update_properties(user_id, request):
    success = False
    stylesheet = request.POST["stylesheet"]
    grading_system = request.POST["grading_system"]
    account = get_account(user_id)
    stylesheet = models.Stylesheet.objects.get(id=stylesheet)
    grading_system = models.GradingSystem.objects.get(id=grading_system)
    if stylesheet is not None:
        account.css_style = stylesheet
        account.save()
        success = True
    if grading_system is not None:
        account.grading_sys = grading_system
        account.save()
        success = True
    return success

def resolve_grade_percent_c(grading_system, grade, total_points, earned_points,
                            grade_percent):
    grade_range = grading_system.top - grading_system.bottom
    percentage_range = (100 - grading_system.bottom_per)/100

    if grade != '':
        percent = (((float(grade) - grading_system.bottom) / grade_range)\
                   * percentage_range) + (grading_system.bottom_per/100)
        score = int(round((percent * 100), 1))
    elif total_points != '' and earned_points != '':
        if float(total_points) >= float(earned_points):
            pass
        else:
            # Switch total and earned points if entered incorrectly
            temp_tot = total_points
            total_points = earned_points
            earned_points = temp_tot
        percent = ((float(earned_points) / float(total_points))\
                   * percentage_range) + (grading_system.bottom_per/100)
        score = int(round((percent * 100), 1))
    elif grade_percent != '':
        percent = (float(grade_percent) * percentage_range)\
            + (grading_system.bottom_per/100)
        score = int(round((percent * 100), 1))
    else:
        print("skjfhkasjdhfljkssh")
        # all fields are empty - throw error
    return score

def resolve_grade_percent_r(grading_system, grade, total_points, earned_points,
                            grade_percent):
    if grade != '':
        representative = models.Representative.objects.get(id=grade)
        score = int((representative.top - representative.bottom)/2)\
            + representative.bottom
    elif total_points != '' and earned_points != '':
        if float(total_points) >= float(earned_points):
            pass
        else:
            # Switch total and earned points if entered incorrectly
            temp_tot = total_points
            total_points = earned_points
            earned_points = temp_tot
        score = int((int(float(earned_points))/int(float(total_points)))*100)
    elif grade_percent != '':
        score = int(float(grade_percent))
    else:
        print("skdjaflkasj")
        # Throw error - no grade given in html form
    return score

def resolve_grade_c(user_id, grade_per):
    account = get_account(user_id)
    grading_system = models.Calculative.objects.get(g=account.grading_sys)
    grade_range = grading_system.top - grading_system.bottom
    if grade_per == 0:
        return grading_system.bottom
    elif grade_per > grading_system.bottom_per:
        # calculate difference between 100% and the bottom % and find out how
        # much of the grade that difference is and add grade bottom
        upper_diff = 100 - grading_system.bottom_per
        grade_diff = grade_per - grading_system.bottom_per
        grade = ((grade_diff / upper_diff) * grade_range)\
            + grading_system.bottom
        return round(grade, 2)
    else:
        grade = (grade_per / grading_system.bottom_per) * grading_system.bottom
        return round(grade, 2)

def get_calculative_descrip(calculative, grade_per):
    lowest_descrip = None;
    for descrip in calculative:
        if descrip.top > grade_per >= descrip.bottom:
            return descrip
        elif lowest_descrip == None:
            lowest_descrip = descrip
        elif lowest_descrip.top > descrip.top:
            lowest_descrip = descrip
    #If no descriptions were found (happens when they don't got to 0%) then
    # return the lowest description
    return lowest_descrip

def resolve_grade_r(grading_system, grade_per):
    for sys in grading_system:
        if sys.top > grade_per >= sys.bottom:
            return sys

def add_representation_to_grades(grading_sys, grades):
    grading_system = models.Representative.objects.all().filter(g=grading_sys)
    for grade in grades:
        r = resolve_grade_r(grading_system, grade.score)
        grade.calc = r.representation
        grade.calc_id = r.id
    return grades

def check_semester(user_id, start, end, id):
    semesters = get_semesters(user_id)
    Range = namedtuple('Range', ['start', 'end'])
    r1 = Range(start=start, end=end)
    for semester in semesters:
        if semester.id == int(id):
            # skip checking a semester against itself
            # (used when editing a semester)
            continue
        r2 = Range(start=semester.semester_start, end=semester.semester_end)
        latest_start = max(r1.start, r2.start)
        earliest_end = min(r1.end, r2.end)
        overlap = (earliest_end - latest_start).days + 1
        if overlap > 0:
            return False
    return True

def check_semester_ownership(user_id, semester_id):
    account = get_account(user_id)
    semesters = models.Semesters.objects.all().filter(account=account)
    for semester in semesters:
        if semester.id == int(semester_id):
            return True
    return False

def check_subject_ownership(user_id, subject_id):
    account = get_account(user_id)
    subjects = models.Subject.objects.all().filter(account=account)
    for subject in subjects:
        if subject.id == int(subject_id):
            return True
    return False

def check_grade_ownership(user_id, grade_id):
    account = get_account(user_id)
    grades = models.Grades.objects.all().filter(subject__account=account)
    for grade in grades:
        if grade.id == int(grade_id):
            return True
    return False
