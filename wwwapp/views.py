import datetime
import os
import sys
import mimetypes
from dateutil.relativedelta import relativedelta
from wsgiref.util import FileWrapper
from typing import Dict

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError, SuspiciousOperation
from django.db import OperationalError, ProgrammingError
from django.db.models import Q
from django.http import JsonResponse, HttpResponse, HttpRequest, HttpResponseForbidden
from django.shortcuts import render, redirect, get_object_or_404, \
    render_to_response
from django.urls import reverse

from .forms import ArticleForm, UserProfileForm, UserForm, WorkshopForm, \
    UserProfilePageForm, WorkshopPageForm, UserCoverLetterForm, UserInfoPageForm
from .models import Article, UserProfile, Workshop, WorkshopParticipant, \
    WorkshopUserProfile, ResourceYearPermission
from .templatetags.wwwtags import qualified_mark


def get_context(request):
    context = {}

    context['has_workshops'] = False

    if request.user.is_authenticated:
        if Workshop.objects.filter(lecturer__user=request.user).exists():
            context['has_workshops'] = True

        visible_resources = ResourceYearPermission.objects.exclude(access_url__exact="")
        if request.user.has_perm('wwwapp.access_all_resources'):
            context['resources'] = visible_resources
        else:
            try:
                user_profile = UserProfile.objects.get(user=request.user)
                context['resources'] = visible_resources.filter(year__in=user_profile.all_participation_years())
            except UserProfile.DoesNotExist:
                context['resources'] = []

    context['google_analytics_key'] = settings.GOOGLE_ANALYTICS_KEY
    context['articles_on_menubar'] = Article.objects.filter(on_menubar=True).all()
    context['current_year'] = settings.CURRENT_YEAR

    return context


def program_view(request, year):
    context = get_context(request)
    context['title'] = 'Program WWW%d' % (int(year) % 100 - 4)  # :)

    if request.user.is_authenticated:
        user_participation = set(Workshop.objects.filter(participants__user=request.user).all())
    else:
        user_participation = set()

    workshops = Workshop.objects.filter(Q(status='Z') | Q(status='X'), type__year=year).order_by('title').prefetch_related('lecturer', 'lecturer__user', 'category')
    context['workshops'] = [(workshop, (workshop in user_participation)) for workshop
                            in workshops]

    if request.user.is_authenticated:
        qualifications = WorkshopParticipant.objects.filter(participant__user=request.user, workshop__type__year=year).prefetch_related('workshop')
        if not any(qualification.qualification_result is not None for qualification in qualifications):
            qualifications = None
        context['your_qualifications'] = qualifications

    return render(request, 'program.html', context)


def profile_view(request, user_id):
    """
    This function allows to view other people's profile by id.
    However, to view them easily some kind of resolver might be needed as we don't have usernames.
    """
    context = get_context(request)
    user_id = int(user_id)
    user = get_object_or_404(User, pk=user_id)

    profile = UserProfile.objects.get(user=user)
    profile_page = profile.profile_page

    is_my_profile = (request.user == user)
    can_see_all_users = request.user.has_perm('wwwapp.see_all_users')
    can_see_all_workshops = request.user.has_perm('wwwapp.see_all_workshops')

    context['title'] = "{0.first_name} {0.last_name}".format(user)
    context['profile_page'] = profile_page
    context['is_my_profile'] = is_my_profile
    context['gender'] = profile.gender

    if can_see_all_users or is_my_profile:
        context['profile'] = profile
        context['participation_data'] = profile.all_participation_data()
        if not can_see_all_workshops and not is_my_profile:
            # If the current user can't see non-public workshops, remove them from the list
            for participation in context['participation_data']:
                participation['workshops'] = [w for w in participation['workshops'] if w.is_publicly_visible()]

    if can_see_all_workshops or is_my_profile:
        context['lecturer_workshops'] = profile.lecturer_workshops.all().order_by('type__year')
    else:
        context['lecturer_workshops'] = profile.lecturer_workshops.filter(Q(status='Z') | Q(status='X')).order_by('type__year')
    context['can_see_all_workshops'] = can_see_all_workshops

    can_qualify = request.user.has_perm('wwwapp.change_workshop_user_profile')
    context['can_qualify'] = can_qualify
    context['has_workshop_profile'] = WorkshopUserProfile.objects.filter(
        user_profile=user.userprofile, year=settings.CURRENT_YEAR).exists()

    if request.method == 'POST':
        if not can_qualify:
            return HttpResponseForbidden()
        (edition_profile, _) = WorkshopUserProfile.objects.get_or_create(
            user_profile=user.userprofile, year=settings.CURRENT_YEAR)
        context['has_workshop_profile'] = True
        if request.POST['qualify'] == 'accept':
            edition_profile.status = WorkshopUserProfile.STATUS_ACCEPTED
            edition_profile.save()
        elif request.POST['qualify'] == 'reject':
            edition_profile.status = WorkshopUserProfile.STATUS_REJECTED
            edition_profile.save()
        elif request.POST['qualify'] == 'delete':
            edition_profile.delete()
            context['has_workshop_profile'] = False
        else:
            raise SuspiciousOperation("Invalid argument")

    return render(request, 'profile.html', context)


@login_required()
def my_profile_view(request):
    context = get_context(request)
    user_profile = UserProfile.objects.get(user=request.user)

    user_form = UserForm(instance=request.user)
    user_profile_form = UserProfileForm(instance=user_profile)
    user_profile_page_form = UserProfilePageForm(instance=user_profile)
    user_cover_letter_form = UserCoverLetterForm(instance=user_profile)
    user_info_page_form = UserInfoPageForm(instance=user_profile.user_info)

    if request.method == "POST":
        page = request.POST['page']
        if page == 'data':
            user_form = UserForm(request.POST, instance=request.user)
            user_profile_form = UserProfileForm(request.POST, instance=user_profile)
            if user_form.is_valid() and user_profile_form.is_valid():
                user_form.save()
                user_profile_form.save()
                messages.info(request, 'Zapisano.')
        elif page == 'profile_page':
            user_profile_page_form = UserProfilePageForm(request.POST, instance=user_profile)
            if user_profile_page_form.is_valid():
                user_profile_page_form.save()
                messages.info(request, 'Zapisano.')
        elif page == 'cover_letter':
            user_cover_letter_form = UserCoverLetterForm(request.POST, instance=user_profile)
            if user_cover_letter_form.is_valid():
                user_cover_letter_form.save()
                messages.info(request, 'Zapisano.')
        elif page == 'user_info':
            user_info_page_form = UserInfoPageForm(request.POST, instance=user_profile.user_info)
            if user_info_page_form.is_valid():
                user_info_page_form.save()
                messages.info(request, 'Zapisano.')
        else:
            raise SuspiciousOperation('Invalid page')

    user_form.helper.form_tag = False
    user_profile_form.helper.form_tag = False
    context['user_form'] = user_form
    context['user_profile_form'] = user_profile_form
    context['user_profile_page_form'] = user_profile_page_form
    context['user_cover_letter_form'] = user_cover_letter_form
    context['user_info_page_form'] = user_info_page_form
    context['is_editing_profile'] = True
    context['title'] = 'Mój profil'

    return render(request, 'profile.html', context)


def workshop_view(request, name=None):
    new = (name is None)
    if new:
        workshop = None
        title = 'Nowe warsztaty'
        if not request.user.is_authenticated:
            return redirect('login')
        else:
            has_perm_to_edit = True
    else:
        workshop = Workshop.objects.get(name=name)
        title = workshop.title
        if request.user.is_authenticated:
            has_perm_to_edit = Workshop.objects.filter(name=name, lecturer__user=request.user).exists()
        else:
            has_perm_to_edit = False

    # Workshop proposals are only visible to admins
    has_perm_to_see_all = request.user.has_perm('wwwapp.see_all_workshops')
    if not has_perm_to_edit and not has_perm_to_see_all:
        return redirect('login')

    if has_perm_to_edit:
        if request.method == 'POST':
            form = WorkshopForm(request.POST, instance=workshop)
            if form.is_valid():
                workshop = form.save(commit=False)
                workshop.save()
                form.save_m2m()
                user_profile = UserProfile.objects.get(user=request.user)
                workshop.lecturer.add(user_profile)
                workshop.save()
                messages.info(request, 'Zapisano.')
                return redirect('workshop', form.instance.name)
        else:
            form = WorkshopForm(instance=workshop)
    else:
        form = None

    context = get_context(request)
    context['title'] = title
    context['workshop'] = workshop
    context['has_perm_to_edit'] = has_perm_to_edit
    context['has_perm_to_view_details'] = has_perm_to_edit or has_perm_to_see_all

    context['form'] = form

    return render(request, 'workshop.html', context)


def can_edit_workshop(workshop, user):
    if user.is_authenticated:
        return Workshop.objects.filter(id=workshop.id, lecturer__user=user).exists()
    else:
        return False


def workshop_page_view(request, name):
    workshop = get_object_or_404(Workshop, name=name)
    has_perm_to_edit = can_edit_workshop(workshop, request.user)

    if not workshop.is_publicly_visible():  # Accepted or cancelled
        return HttpResponseForbidden("Warsztaty nie zostały zaakceptowane")

    context = get_context(request)
    context['workshop'] = workshop
    context['has_perm_to_edit'] = has_perm_to_edit
    context['has_perm_to_view_details'] = \
        has_perm_to_edit or request.user.has_perm('wwwapp.see_all_workshops')

    return render(request, 'workshoppage.html', context)


def workshop_page_edit_view(request, name):
    workshop = get_object_or_404(Workshop, name=name)

    if not workshop.is_publicly_visible():  # Accepted or cancelled
        return HttpResponseForbidden("Warsztaty nie zostały zaakceptowane")
    if not can_edit_workshop(workshop, request.user):
        return HttpResponseForbidden()

    if request.method == 'POST':
        form = WorkshopPageForm(request.POST, request.FILES,
                                instance=workshop)
        if form.is_valid():
            workshop = form.save(commit=False)
            workshop.save()
            form.save_m2m()
            user_profile = UserProfile.objects.get(user=request.user)
            workshop.lecturer.add(user_profile)
            workshop.save()
            messages.info(request, 'Zapisano.')
            return redirect('workshop_page_edit', form.instance.name)
    else:
        if not workshop.page_content:
            workshop_template = Article.objects.get(
                name="template_for_workshop_page").content
            workshop.page_content = workshop_template
            workshop.save()
        form = WorkshopPageForm(instance=workshop)

    context = get_context(request)
    context['workshop'] = workshop
    context['has_perm_to_edit'] = True
    context['has_perm_to_view_details'] = True

    context['form'] = form

    return render(request, 'workshoppage.html', context)


@login_required()
def workshop_participants_view(request, name):
    workshop = get_object_or_404(Workshop, name=name)
    has_perm_to_edit = can_edit_workshop(workshop, request.user)

    if not workshop.is_publicly_visible():  # Accepted or cancelled
        return HttpResponseForbidden("Warsztaty nie zostały zaakceptowane")

    if not (has_perm_to_edit or request.user.has_perm('wwwapp.see_all_workshops')):
        return HttpResponseForbidden()

    context = get_context(request)
    context['workshop'] = workshop
    context['has_perm_to_edit'] = has_perm_to_edit
    context['has_perm_to_view_details'] = True

    context['workshop_participants'] = WorkshopParticipant.objects.filter(workshop=workshop).prefetch_related(
            'workshop', 'participant', 'participant__user')
    
    return render(request, 'workshopparticipants.html', context)


def save_points_view(request):
    workshop_participant = WorkshopParticipant.objects.get(id=request.POST['id'])

    can_edit = can_edit_workshop(workshop_participant.workshop, request.user)
    if not can_edit:
        return JsonResponse({'error': 'Brak uprawnień.'})

    try:
        result_points = (request.POST['points'].strip() if 'points' in request.POST else None)
        result_comment = (request.POST['comment'].strip() if 'comment' in request.POST else None)
        if result_points is not None:
            if result_points == "":
                workshop_participant.qualification_result = None
            else:
                workshop_participant.qualification_result = result_points
        if result_comment is not None:
            workshop_participant.comment = result_comment
        workshop_participant.save()
    except (ValidationError, ValueError) as e:
        print(e)
        return JsonResponse({'error': 'Niepoprawny format liczby'})
    except Exception as e:
        print(e)
        raise e
    workshop_participant = WorkshopParticipant.objects.get(id=workshop_participant.id)

    return JsonResponse({'points': str(workshop_participant.qualification_result),
                         'comment': workshop_participant.comment,
                         'mark': qualified_mark(workshop_participant.is_qualified())})


@login_required()
@permission_required('wwwapp.see_all_workshops', raise_exception=True)
def participants_view(request, year):
    year = int(year)

    participants = WorkshopParticipant.objects.all().filter(workshop__type__year=year)\
                                                    .prefetch_related('workshop', 'participant', 'participant__user')
    workshops = Workshop.objects.filter(type__year=year).prefetch_related('lecturer', 'lecturer__user')
    lecturers_ids = set()
    for workshop in workshops:
        for l in workshop.lecturer.all():
            lecturers_ids.add(l.user.id)

    people = {}

    for participant in participants:
        p_id = participant.participant.id
        if p_id not in people:
            cover_letter = participant.participant.cover_letter
            if participant.participant.user.id in lecturers_ids:
                continue

            birth = participant.participant.user_info.get_birth_date()
            is_adult = None
            if birth is not None:
                is_adult = settings.WORKSHOPS_START_DATE >= birth + relativedelta(years=18)

            people[p_id] = {
                'user': participant.participant.user,
                'birth': birth,
                'is_adult': is_adult,
                'pesel': participant.participant.user_info.pesel,
                'address': participant.participant.user_info.address,
                'phone': participant.participant.user_info.phone,
                'tshirt_size': participant.participant.user_info.tshirt_size,
                'matura_exam_year': participant.participant.matura_exam_year,
                'accepted_workshop_count': 0,
                'workshop_count': 0,
                'has_letter': bool(cover_letter and len(cover_letter) > 50),
                'status': participant.participant.status_for(year),
                'school': participant.participant.school,
                'points': 0.0,
                'infos': [],
                'comments': participant.participant.user_info.comments,
                'start_date': participant.participant.user_info.start_date,
                'end_date': participant.participant.user_info.end_date,
            }

        if participant.qualification_result:
            people[p_id]['points'] += float(participant.result_in_percent())
        people[p_id]['infos'].append("{title} : {result:.1f}% : {comment}".format(
            title=participant.workshop.title,
            result=participant.result_in_percent() if participant.qualification_result else 0,
            comment=participant.comment if participant.comment else ""
        ))
        people[p_id]['workshop_count'] += 1
        if participant.is_qualified():
            people[p_id]['accepted_workshop_count'] += 1

    people = list(people.values())

    context = get_context(request)
    context['title'] = 'Uczestnicy'
    context['people'] = people

    return render(request, 'participants.html', context)


@login_required()
@permission_required('wwwapp.see_all_workshops', raise_exception=True)
def lecturers_view(request: HttpRequest, year: int) -> HttpResponse:
    year = int(year)

    workshops = Workshop.objects.filter(type__year=year, status=Workshop.STATUS_ACCEPTED).prefetch_related('lecturer', 'lecturer__user')

    people: Dict[int, Dict[str, any]] = {}
    for workshop in workshops:
        for lecturer in workshop.lecturer.all():
            if lecturer.id in people:
                people[lecturer.id]['workshops'].append(workshop.info_for_client_link())
                continue

            birth = lecturer.user_info.get_birth_date()
            is_adult = None
            if birth is not None:
                is_adult = settings.WORKSHOPS_START_DATE >= birth + relativedelta(years=18)

            people[lecturer.id] = {
                'user': lecturer.user,
                'birth': birth,
                'is_adult': is_adult,
                'pesel': lecturer.user_info.pesel,
                'address': lecturer.user_info.address,
                'phone': lecturer.user_info.phone,
                'tshirt_size': lecturer.user_info.tshirt_size,
                'comments': lecturer.user_info.comments,
                'start_date': lecturer.user_info.start_date,
                'end_date': lecturer.user_info.end_date,
                'workshops': [workshop.info_for_client_link()],
            }

    people_list = list(people.values())

    context = get_context(request)
    context['title'] = 'Prowadzący'
    context['people'] = people_list

    return render(request, 'lecturers.html', context)


def register_to_workshop_view(request):
    workshop_name = request.POST['workshop_name']

    if not request.user.is_authenticated:
        return JsonResponse({'redirect': reverse('login'), 'error': u'Jesteś niezalogowany'})

    workshop = get_object_or_404(Workshop, name=workshop_name)

    if workshop.type.year != settings.CURRENT_YEAR:
        return JsonResponse({'error': 'Kwalifikacja na te warsztaty została dawno zakończona.'})

    if datetime.datetime.now().date() >= settings.WORKSHOPS_START_DATE:
        return JsonResponse({'error': u'Kwalifikacja na te warsztaty została zakończona.'})

    WorkshopParticipant(participant=UserProfile.objects.get(user=request.user), workshop=workshop).save()

    context = get_context(request)
    context['workshop'] = workshop
    context['registered'] = True
    return JsonResponse({'content': render_to_response('_programworkshop.html', context).content.decode()})


def unregister_from_workshop_view(request):
    workshop_name = request.POST['workshop_name']
    data = {}
    if not request.user.is_authenticated:
        return JsonResponse({'redirect': reverse('login'), 'error': u'Jesteś niezalogowany'})

    workshop = get_object_or_404(Workshop, name=workshop_name)
    profile = UserProfile.objects.get(user=request.user)
    workshop_participant = WorkshopParticipant.objects.get(workshop=workshop, participant=profile)

    if workshop.type.year != settings.CURRENT_YEAR:
        return JsonResponse({'error': 'Kwalifikacja na te warsztaty została dawno zakończona.'})

    if datetime.datetime.now().date() >= settings.WORKSHOPS_START_DATE:
        return JsonResponse({'error': u'Kwalifikacja na te warsztaty została zakończona.'})

    if workshop_participant.qualification_result is not None or workshop_participant.comment:
        return JsonResponse({'error': u'Masz już wyniki z tej kwalifikacji - nie możesz się wycofać.'})

    workshop_participant.delete()

    context = get_context(request)
    context['workshop'] = workshop
    context['registered'] = False
    data['content'] = render_to_response('_programworkshop.html', context).content.decode()
    return JsonResponse(data)


@permission_required('wwwapp.export_workshop_registration')
def data_for_plan_view(request):
    data = {}

    participant_profiles_raw = UserProfile.objects.filter(workshop_profile__year=settings.CURRENT_YEAR, workshop_profile__status='Z')

    lecturer_profiles_raw = set()
    workshop_ids = set()
    workshops = []
    for workshop in Workshop.objects.filter(status='Z', type__year=settings.CURRENT_YEAR):
        workshop_data = {'wid': workshop.id,
                         'name': workshop.title,
                         'lecturers': [lect.id for lect in
                                       workshop.lecturer.all()]}
        for lecturer in workshop.lecturer.all():
            if lecturer not in participant_profiles_raw:
                lecturer_profiles_raw.add(lecturer)
        workshop_ids.add(workshop.id)
        workshops.append(workshop_data)
    data['workshops'] = workshops

    users = []
    user_ids = set()

    for user_type, profiles in [('Lecturer', lecturer_profiles_raw),
                                ('Participant', participant_profiles_raw)]:
        for up in profiles:
            users.append({
                'uid': up.id,
                'name': up.user.get_full_name(),
                'type': user_type,
                'start': up.user_info.start_date if up.user_info.start_date != 'no_idea' else 1,
                'end': up.user_info.end_date if up.user_info.end_date != 'no_idea' else 30
            })
            user_ids.add(up.id)

    data['users'] = users

    participation = []
    for wp in WorkshopParticipant.objects.all():
        if wp.workshop.id in workshop_ids and wp.participant.id in user_ids:
            participation.append({
                'wid': wp.workshop.id,
                'uid': wp.participant.id,
            })
    data['participation'] = participation

    return JsonResponse(data, json_dumps_params={'indent': 4})


def qualification_problems_view(request, workshop_name):
    workshop = get_object_or_404(Workshop, name=workshop_name)
    filename = workshop.qualification_problems.path

    wrapper = FileWrapper(open(filename, "rb"))
    response = HttpResponse(wrapper, content_type=mimetypes.guess_type(filename)[0])
    response['Content-Length'] = os.path.getsize(filename)
    return response


def article_view(request, name=None):
    context = get_context(request)
    new = (name is None)
    if new:
        art = None
        title = 'Nowy artykuł'
        has_perm = request.user.has_perm('wwwapp.add_article')
    else:
        art = Article.objects.get(name=name)
        title = art.title
        has_perm = request.user.has_perm('wwwapp.change_article')

    if has_perm:
        if request.method == 'POST':
            form = ArticleForm(request.user, request.POST, instance=art)
            if form.is_valid():
                article = form.save(commit=False)
                article.modified_by = request.user
                article.save()
                form.save_m2m()
                messages.info(request, 'Zapisano.')
                return redirect('article', form.instance.name)
        else:
            form = ArticleForm(request.user, instance=art)
    else:
        form = None

    context['addArticle'] = new
    context['title'] = title
    context['article'] = art
    context['form'] = form

    return render(request, 'article.html', context)


def article_name_list_view(request):
    names = Article.objects.values_list('name', flat=True)
    return JsonResponse(list(names), safe=False)


@login_required()
def your_workshops_view(request):
    workshops = Workshop.objects.filter(lecturer__user=request.user)
    return render_workshops(request, 'Twoje warsztaty', True, workshops)


@login_required()
@permission_required('wwwapp.see_all_workshops', raise_exception=True)
def all_workshops_view(request):
    workshops = Workshop.objects.all()
    return render_workshops(request, 'Wszystkie warsztaty', False, workshops)


def render_workshops(request, title, link_to_edit, workshops):
    context = get_context(request)

    years = set(workshop.type.year for workshop in workshops)
    years = list(reversed(sorted(years)))
    context['workshops'] = [
        {'year': year,
         'workshops': [workshop for workshop in workshops if workshop.type.year == year]}
        for year in years]
    context['title'] = title
    context['link_to_edit'] = link_to_edit

    return render(request, 'workshoplist.html', context)


@login_required()
@permission_required('wwwapp.see_all_workshops', raise_exception=True)  # Think about seperate permission
def emails_view(request):
    workshops = Workshop.objects.all()

    result = []
    for workshop in workshops:
        lecturer = workshop.lecturer.all()[0]
        email = lecturer.user.email
        name = lecturer.user.first_name + " " + lecturer.user.last_name

        to_append = {'workshopname': workshop.title, 'email': email, 'name': name}
        result.append(to_append)

    return JsonResponse(result, safe=False)


def as_article(name):
    # We want to make sure that article with this name exists.
    # try-except is needed because of some migration/initialization problems.
    try:
        Article.objects.get_or_create(name=name)
    except OperationalError:
        print("WARNING: Couldn't create article named", name,
              "; This should happen only during migration.", file=sys.stderr)
    except ProgrammingError:
        print("WARNING: Couldn't create article named", name,
              "; This should happen only during migration.", file=sys.stderr)

    def page(request):
        return article_view(request, name)
    return page


index_view = as_article("index")
template_for_workshop_page_view = as_article("template_for_workshop_page")


def resource_auth_view(request):
    """
    View checking permission for resource (header X-Original-URI). Returns 200
    when currently logged in user should be granted access to resource and 403
    when access should be denied.

    See https://docs.nginx.com/nginx/admin-guide/security-controls/configuring-subrequest-authentication/
    for intended usage.
    """
    if not request.user.is_authenticated:
        return HttpResponseForbidden("You need to login.")
    if request.user.has_perm('wwwapp.access_all_resources'):
        return HttpResponse("Glory to WWW and the ELITARNY MIMUW!!!")

    user_profile = UserProfile.objects.get(user=request.user)

    uri = request.META.get('HTTP_X_ORIGINAL_URI', '')

    for resource in ResourceYearPermission.resources_for_uri(uri):
        if user_profile.is_participating_in(resource.year):
            return HttpResponse("Welcome!")
    return HttpResponseForbidden("What about NO!")
