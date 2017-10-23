from django.db import models
from django.contrib.auth.models import User  # User Account
from django.utils.functional import cached_property

from django.dispatch import receiver
from email_confirm_la.signals import post_email_confirmation_confirm

@receiver(post_email_confirmation_confirm)
def post_email_confirmation_confirm_callback(sender, confirmation, **kwargs):
    model_instace = confirmation.content_object
    email = confirmation.email
    # Activate account
    user = User.objects.get(email=email)
    user.is_active = True
    user.save()

class GradingSystem(models.Model):
    """ The type of grading system for a specific Area

    ** Contents **
    name - name of the grading system (ex. CH)
    type - representative or calculative or none (r, c, n) 
           none just uses percent as grading system
    """
    name = models.CharField(max_length=50, null=False)
    # Type of grading system. R=representative, C=calculative, N=none (%)
    type = models.CharField(max_length=50, null=False)

    def __str__(self):
        return self.name

class AccountType(models.Model):
    """ Defines if the model is free or premium

    ** Contents **
    name - name of account type (ex. Free)
    price - price of account (ex. 0 for free or 2 for premium)
    periodicity - how often the prive should be charged per year (ex. 12)
    restrict_lvl - to know if an account is allowed to access premium features
    """
    name = models.CharField(max_length=50)
    price = models.IntegerField(null=True)
    periodicity = models.IntegerField(null=True)
    restrict_lvl = models.IntegerField(null=False)

    def __str__(self):
        return self.name

class AccountValid(models.Model):
    """ Defines the validity levels for accounts

    ** Contents **
    isvalid - is the account active
    level - level of validity (ex. if account is late for payment, valid,
            disabled due suspicious activity etc.)
    message - message that correspondes the the level of validity
    """
    isvalid = models.BooleanField(default=True, null=False)
    level = models.IntegerField(null=False)
    message = models.CharField(max_length=500, null=True)

    def __str__(self):
        return self.message

class Stylesheet(models.Model):
    """ CSS style filename to be used for user

    ** Contents **
    name - filename of css Stylesheet
    """
    name = models.CharField(max_length=50, null=False)

    def __str__(self):
        return self.name

class Accounts(models.Model):
    """ Account data that expands on the default django user table

    ** Contents **
    user - ForeignKey of user
    create_date - Date if account creation
    valid - ForeignKey to level of account validity
    grading_sys - ForeignKey to gradingsystem to be used with this account
    account_type - ForeignKey on type (free, premium)
    """
    user = models.OneToOneField(User, unique=True, primary_key=True)
    create_date = models.DateField(null=False)
    valid = models.ForeignKey(AccountValid, on_delete=models.PROTECT,
                              null=False)
    grading_sys = models.ForeignKey(GradingSystem, on_delete=models.PROTECT,
                                    null=False)
    account_type = models.ForeignKey(AccountType, on_delete=models.PROTECT,
                                     null=False)
    css_style = models.ForeignKey(Stylesheet, null=True, default=1)
    sponsored = models.BooleanField(null=False, default=False)

    def __str__(self):
        return self.user.username

class DateDefinitions(models.Model):
    """ Define important dates on a yearly basis

    ** Contents **
    schoolyr_start - Date of the start of the schoolyear
    sem*_start - start of semester
    sem*_end - end of semester
    account - ForeignKey to corresponding account

    There is a maximum of four semesters per year
    """
    schoolyr_start = models.DateField(null=False)
    account = models.ForeignKey(Accounts, on_delete=models.CASCADE, null=False)

    def __str__(self):
        return self.account.user.username

class Semesters(models.Model):
    """Define Semesters

    ** Contents **
    name - semester name
    semester_end - semester end date
    semester_start - semester start date
    account - ForeignKey relation to Accounts
    """
    name = models.CharField(max_length=100, null=True)
    semester_end = models.DateField(null=False)
    semester_start = models.DateField(null=False)
    account = models.ForeignKey(Accounts, null=False)

    def __str__(self):
        return "{} , {} , {}".format(self.account.user.username,
                                     str(self.semester_start),
                                     str(self.semester_end))

class Subject(models.Model):
    """ Subjects

    ** Contents **
    name - name of Subject
    account - ForeignKey to user account
    """
    name = models.CharField(max_length=50, null=False)
    account = models.ForeignKey(Accounts, on_delete=models.CASCADE, null=False)
    weight = models.FloatField(null=False, default=1)

    def __str__(self):
        return "{} , {}".format(self.account.user.username, self.name)

class Grades(models.Model):
    """ Grades

    ** Contents **
    subject - ForeignKey on subject to which this grade belongs
    date - Date of grade
    score - grade received in percent
    """
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, null=False)
    note = models.CharField(max_length=1000)
    date = models.DateField(null=False)
    weight = models.FloatField(null=False, default=1)
    score = models.FloatField(null=False)

    def __str__(self):
        return "{} , {} , {}".format(self.subject.account.user.username,
                                     self.subject.name,  str(self.date))

############## Grading ###################
# representative & calculative grading systems

class Legend(models.Model):
    """ Defines pre-sets for grade levels consistent accross grading types
        Used to set a color for a grade (ex. red for bad, green for good)
        and a description

    ** Contents **
    description - description for this level (ex. Excellent, Bad, Good)
    lvl - level of description (ex. 1 for Excellent)
    """
    description = models.CharField(max_length=50, null=False)
    css_class = models.CharField(max_length=50, null=True)
    lvl = models.IntegerField(null=False)

    def __str__(self):
        return str(self.lvl) + " | " + self.description

class Country(models.Model):
    """ Countries

    ** Contents **
    name - name of country
    """
    name = models.CharField(max_length=50, null=False)

    def __str__(self):
        return self.name

class Area(models.Model):
    """ Areas in Country - Useful for different grading systems in different
        eg. states

    ** Contents **
    name - name of Area
    g = ForeignKey on GradingSystem for area
    c = ForeignKey on Country of area
    """
    name = models.CharField(max_length=50, null=False)
    g = models.ForeignKey(GradingSystem, null=False)
    c = models.ForeignKey(Country, null=False)

    def __str__(self):
        return self.name

class Representative(models.Model):
    """ Representations for Representative grading systems
    Representative grading systems are grading systems which are not
    calculated, but use a representation to define a grade.
    Ex. Grade "A" = score or 90% - 100%

    ** Contents **
    bottom - bottom border for grade representation in percent (ex. 90%)
    top - top border for grade representation in percent (ex. 100%)
    representation - representation for percentage range
    legend - ForeignKey on level of grade (ex. excellent)
    g - ForeignKey on grading system that uses this representation
    """
    bottom = models.IntegerField(null=False)
    top = models.IntegerField(null=False)
    representation = models.CharField(max_length=50, null=False)
    legend = models.ForeignKey(Legend, null=False)
    g = models.ForeignKey(GradingSystem, null=False)

    def __str__(self):
        return "{} | {} | {}".format(self.g.name, self.representation, 
                                     str(self.top))


class Calculative(models.Model):
    """ Calculation properties for a Calculative grading system
    Calculative grading systems are grading systems which are both calculative
    and (most of the time) also have representations

    ** Contents **
    bottom - lowest grade possible (Ex. 1 in grading system from 6 - 1 )
    top - highest grade possible (Ex. 6 in grading system from 6 - 1 )
    bottom_per - starting percentage at which grade should be calculated
                (some grading systems don't calculate at all if grade
                lower than ex. 20% )
    g - ForeignKey on grading system that uses these properties
    """
    bottom = models.IntegerField(null=False)
    top = models.IntegerField(null=False)
    bottom_per = models.IntegerField(null=False)
    g = models.ForeignKey(GradingSystem, null=False)

    def __str__(self):
        return self.g.name


class CalculativeDescrip(models.Model):
    """
    Decriptions for a calculative grading system - FK goes to calculative
    grading system properties

    ** Contents **
    bottom - bottom border for grade description in percent
    top - border for grade description in percent
    """
    bottom = models.IntegerField(null=False)
    top = models.IntegerField(null=False)
    legend = models.ForeignKey(Legend, null=False)
    c = models.ForeignKey(Calculative, null=False)

    def __str__(self):
        return "{} : {} , {} , {}".format(self.c.g.name, str(self.bottom),
                                          str(self.top),
                                          self.legend.description)
