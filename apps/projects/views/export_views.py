import os
from django.shortcuts import get_object_or_404, redirect, render
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.urls import reverse
from ..models import Project, LeaderEvaluation, UserPreferences, Milestone, ScoringScheme
from ..forms import (
    DateInputForm
)
import csv
from django.http import HttpResponse
from docxtpl import DocxTemplate, InlineImage
from django.http import HttpResponse
import openpyxl
from django.template.loader import render_to_string
from weasyprint import HTML
from docx.shared import Cm
from datetime import datetime

@login_required
def export_project_docx(request, pk):
    project = get_object_or_404(Project, pk=pk)

    # Pouze vedoucí nebo superuser (nebo kdokoli, pokud je to volně přístupné)
    if not (request.user == project.leader or request.user.is_superuser):
        messages.error(request, "Nemáte oprávnění exportovat.")
        return redirect('projects:detail', pk=pk)

    # Zjištění oboru studenta
    student_profile = getattr(project.student, 'userprofile', None)
    branch = student_profile.study_branch if student_profile else 'E'  # pokud by student neměl profil, fallback = 'E'

    # Podle oboru vybereme šablonu
    if branch == 'IT':
        doc = DocxTemplate("templates/docx/zadani_projektu_IT.docx")
    else:
        doc = DocxTemplate("templates/docx/zadani_projektu_E.docx")

    # Připrav data pro šablonu
    class_name = student_profile.class_name if student_profile else ""

    # Získání kontrol
    controls_data = []
    for c in project.controls.all():
        controls_data.append({
            'date': c.date.strftime("%d.%m.%Y"),  # formátování
            'content': c.content,
            'evaluation': c.evaluation,
        })

    leader_eval = project.leader_eval if hasattr(project, 'leader_eval') else None
    opponent_eval = project.opponent_eval if hasattr(project, 'opponent_eval') else None

    context = {
        'student_name': f"{project.student.first_name} {project.student.last_name}",
        'class_name': class_name,
        'leader_name': project.leader.userprofile.title + " " + project.leader.get_full_name() if project.leader else "",
        'opponent_name': project.opponent.userprofile.title + " " + project.opponent.get_full_name() if project.opponent else "",
        'project_title': project.title,
        'project_description': project.description,

        'controls': controls_data,

        'leader_eval': {
            'area1_text': leader_eval.area1_text if leader_eval else "",
            'area1_points': leader_eval.area1_points if leader_eval else 0,
            # area2, area3 ...
        } if leader_eval else {},
        'opponent_eval': {
            'area1_text': opponent_eval.area1_text if opponent_eval else "",
            'area1_points': opponent_eval.area1_points if opponent_eval else 0,
            # area2 ...
        } if opponent_eval else {},
    }

    doc.render(context)

    # Vygenerujeme soubor
    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document')
    response['Content-Disposition'] = f'attachment; filename=\"projekt_{pk}.docx\"'
    doc.save(response)
    return response


@staff_member_required
def export_projects_xlsx(request):
    """
    Exportuje seznam projektů do XLSX.
    Sloupce: Student, Třída, Název, Vedoucí, Oponent, Stav.
    Případně můžeme přidat filtry.
    """
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Projekty"

    # Hlavička
    ws.append(["Student", "Třída", "Název projektu", "Vedoucí", "Oponent", "Stav"])

    projects = Project.objects.all()  # nebo filtr, to je na tobě

    for proj in projects:
        year = proj.scheme.year if proj.scheme else "N/A"
        student_name = f"{proj.student.first_name} {proj.student.last_name}" if proj.student else ""
        student_class = ""
        if proj.student and hasattr(proj.student, 'userprofile'):
            student_class = proj.student.userprofile.class_name or ""
        
        leader_name = proj.leader.username if proj.leader else ""
        opponent_name = proj.opponent.username if proj.opponent else ""
        row = [
            student_name,
            student_class,
            proj.title,
            leader_name,
            opponent_name,
            proj.get_status_display(),
        ]
        ws.append(row)

    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = 'attachment; filename="projekty.xlsx"'

    wb.save(response)
    return response



@login_required
def export_consultation_list(request, pk):
    project = get_object_or_404(Project, pk=pk)
    
    if request.method == 'POST':
        form = DateInputForm(request.POST)
        if form.is_valid():
            handover_date = form.cleaned_data['handover_date']

            student = project.student.username

            doc = DocxTemplate("templates/docx/consultation_list.docx")
            controls = project.controls.all().order_by('date')[:3]  # První 3 kontroly

            context = {
                'student_name': f"{project.student.first_name} {project.student.last_name}",
                'class_name': project.student.userprofile.class_name,
                'school_year': project.scheme.year if project.scheme else "N/A",
                'project_title': project.title,
                'control_1_date': controls[0].date.strftime('%d.%m.%Y') if len(controls) > 0 else "N/A",
                'control_1_eval': controls[0].evaluation if len(controls) > 0 else "N/A",
                'control_1_desc': controls[0].content if len(controls) > 0 else "N/A",
                'control_2_date': controls[1].date.strftime('%d.%m.%Y') if len(controls) > 1 else "N/A",
                'control_2_eval': controls[1].evaluation if len(controls) > 1 else "N/A",
                'control_2_desc': controls[1].content if len(controls) > 1 else "N/A",
                'control_3_date': controls[2].date.strftime('%d.%m.%Y') if len(controls) > 2 else "N/A",
                'control_3_eval': controls[2].evaluation if len(controls) > 2 else "N/A",
                'control_3_desc': controls[2].content if len(controls) > 2 else "N/A",
                'handover_date': handover_date.strftime('%d.%m.%Y')
            }

            user_prefs = UserPreferences.objects.filter(user=request.user).first()

            # Vložení podpisu, pokud existuje
            if user_prefs and user_prefs.signature and os.path.exists(user_prefs.signature.path):
                signature_img = InlineImage(doc, user_prefs.signature.path, width=Cm(2.5))  
                context["signature"] = signature_img  # Odkazujeme se na ALT text v šabloně
            else:
                context["signature"] = ""  # Pokud není podpis, zůstane prázdný

            doc.render(context)
            response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document')
            response['Content-Disposition'] = f'attachment; filename="konzultacni_list_{student}.docx"'
            doc.save(response)
            return response
    else:
        # Kontrola, zda existuje datum odevzdání projektu
        if project.delivery_work_date:
            form = DateInputForm(initial={'handover_date': project.delivery_work_date})
            # Automaticky vyexportovat dokument
            handover_date = project.delivery_work_date
            student = project.student.username

            doc = DocxTemplate("templates/docx/consultation_list.docx")
            controls = project.controls.all().order_by('date')[:3]  # První 3 kontroly

            context = {
                'student_name': f"{project.student.first_name} {project.student.last_name}",
                'class_name': project.student.userprofile.class_name,
                'school_year': project.scheme.year if project.scheme else "N/A",
                'project_title': project.title,
                'control_1_date': controls[0].date.strftime('%d.%m.%Y') if len(controls) > 0 else "N/A",
                'control_1_eval': controls[0].evaluation if len(controls) > 0 else "N/A",
                'control_1_desc': controls[0].content if len(controls) > 0 else "N/A",
                'control_2_date': controls[1].date.strftime('%d.%m.%Y') if len(controls) > 1 else "N/A",
                'control_2_eval': controls[1].evaluation if len(controls) > 1 else "N/A",
                'control_2_desc': controls[1].content if len(controls) > 1 else "N/A",
                'control_3_date': controls[2].date.strftime('%d.%m.%Y') if len(controls) > 2 else "N/A",
                'control_3_eval': controls[2].evaluation if len(controls) > 2 else "N/A",
                'control_3_desc': controls[2].content if len(controls) > 2 else "N/A",
                'handover_date': handover_date.strftime('%d.%m.%Y')
            }

            user_prefs = UserPreferences.objects.filter(user=request.user).first()

            # Vložení podpisu, pokud existuje
            if user_prefs and user_prefs.signature and os.path.exists(user_prefs.signature.path):
                signature_img = InlineImage(doc, user_prefs.signature.path, width=Cm(2.5))  
                context["signature"] = signature_img
            else:
                context["signature"] = ""

            doc.render(context)
            response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document')
            response['Content-Disposition'] = f'attachment; filename="konzultacni_list_{student}.docx"'
            doc.save(response)
            return response
        else:
            user = request.user
            # context['is_teacher'] = user.groups.filter(name='Teacher').exists()
            # context['is_student'] = user.groups.filter(name='Student').exists()
            # Pokud není datum odevzdání, vracíme stránku s JavaScriptem pro zobrazení popup
            return render(request, 'projects/export_error.html', {
                'project': project,
                'is_teacher': user.groups.filter(name='Teacher').exists(),
                'error_message': 'Není vyplněno datum odevzdání projektu',
                'redirect_url': reverse('projects:detail', kwargs={'pk': pk})
            })


@login_required
def export_project_assignment(request, pk):
    project = get_object_or_404(Project, pk=pk)

    leader = f'{project.leader.userprofile.title} {project.leader.first_name} {project.leader.last_name}' if project.leader else ""
    student = project.student.username

    template = "templates/docx/assignment_IT.docx" if project.student.userprofile.study_branch == "IT" else "templates/docx/assignment_E.docx"
    
    context = {
        'student_name': f"{project.student.first_name} {project.student.last_name}",
        'class_name': project.student.userprofile.class_name,
        'school_year': project.scheme.year if project.scheme else "N/A",
        'project_title': project.title,
        'assignment': project.assignment,
        'leader': leader,
    }

    doc = DocxTemplate(template)
    doc.render(context)

    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document')
    response['Content-Disposition'] = f'attachment; filename="zadani_prace_{student}.docx"'
    doc.save(response)
    return response



@login_required
def export_project_detail_pdf(request, pk):
    project = get_object_or_404(Project, pk=pk)
    context = {
        'student_name': f"{project.student.first_name} {project.student.last_name}",
        'class_name': project.student.userprofile.class_name,
        'project_title': project.title,
        'assignment': project.assignment,
        'milestones': project.milestones.all()
    }
    html_string = render_to_string('projects/pdf_project_detail.html', context)
    pdf_file = HTML(string=html_string).write_pdf()

    response = HttpResponse(pdf_file, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="projekt_{pk}.pdf"'
    return response


@login_required
def export_control_check_pdf(request):
    user = request.user
    # Zkus získat default_year z předvoleb, pokud existuje
    default_year = None
    if hasattr(user, 'preferences'):
        default_year = user.preferences.default_year

    # Pokud není předán GET parametr "year", použijeme default_year
    selected_year = request.GET.get('year', default_year)
    
    # Filtrujeme projekty podle ScoreBoardu (ScoringScheme.year) nebo případně podle studijního roku studenta
    if selected_year:
        # projects = Project.objects.filter(scheme__year=selected_year)
        # projects = Project.objects.filter(leader=request.user).order_by('student__last_name')
        projects = Project.objects.filter(scheme__year=selected_year, leader=request.user).order_by('student__last_name')
        #projects = Project.objects.filter(Q(scheme__year=selected_year) & Q(leader=request.user)).order_by('student__last_name')
    else:
        # projects = Project.objects.all()
        projects = Project.objects.filter(leader=request.user).order_by('student__last_name')
    # projects = Project.objects.all()
    # Filtrace: vybereme pouze projekty, kde je leader == přihlášený uživatel
    # projects = Project.objects.filter(leader=request.user).order_by('student__last_name')

    # Pro každý projekt předpřipravíme seřazené kontroly podle data
    # (Předpokládáme, že kontrolní záznamy mají pole "date")
    for project in projects:
        project.sorted_checks = project.controls.order_by('date')
    
    context = {
        'projects': projects,
    }

    html_string = render_to_string('projects/pdf_control_check.html', context)
    pdf_file = HTML(string=html_string).write_pdf()

    response = HttpResponse(pdf_file, content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="prehled_kontrol.pdf"'
    return response



@login_required
def export_leader_eval(request, pk):
    project = get_object_or_404(Project, pk=pk)
    leader_eval = get_object_or_404(LeaderEvaluation, project=project)

    if not leader_eval:
        messages.error(request, "Posudek vedoucího neexistuje.")
        return redirect('projects:detail', pk=pk)

    submission_status = leader_eval.submission_status

    # Inicializace hodnot
    submitted_on_time = ''
    submitted_late = ''
    not_submitted = ''

    # Přidání "X" do správného pole dle submission_status
    if submission_status == 'on_time':
        submitted_on_time = 'X'
    elif submission_status == 'late':
        submitted_late = 'X'
    elif submission_status == 'not_submitted':
        not_submitted = 'X'

    doc = DocxTemplate("templates/docx/leader_eval.docx")
    # leader_eval = getattr(project, 'leader_eval', None)

    # Načtení dat z modelu
    context = {
        'student_name': f"{project.student.first_name} {project.student.last_name}",
        'class_name': project.student.userprofile.class_name,
        'school_year': project.scheme.year if project.scheme else "N/A",
        'leader_name': f"{project.leader.userprofile.title} {project.leader.first_name} {project.leader.last_name}",
        'project_title': project.title,
        'area1_text': leader_eval.area1_text,
        'area1_points': leader_eval.area1_points,
        'area2_text': leader_eval.area2_text,
        'area2_points': leader_eval.area2_points,
        'area3_text': leader_eval.area3_text,
        'area3_points': leader_eval.area3_points,
        'total_points': leader_eval.area1_points + leader_eval.area2_points + leader_eval.area3_points,
        'max_points': (
            project.scheme.leader_area1_max +
            project.scheme.leader_area2_max +
            project.scheme.leader_area3_max
        ) if project.scheme else "N/A",
        'review_date': leader_eval.export_date.strftime('%d.%m.%Y') if leader_eval.export_date else '',
        # Zaškrtnutí příslušného pole
        'submitted_on_time': submitted_on_time,
        'submitted_late': submitted_late,
        'not_submitted': not_submitted,
    }

    # Přidání podpisu
    # user_prefs = getattr(request.user, 'userpreferences', None)
    user_prefs = UserPreferences.objects.filter(user=request.user).first()

    # Vložení podpisu, pokud existuje
    if user_prefs and user_prefs.signature and os.path.exists(user_prefs.signature.path):
        signature_img = InlineImage(doc, user_prefs.signature.path, width=Cm(2.5))  
        context["signature"] = signature_img  # Odkazujeme se na ALT text v šabloně
    else:
        context["signature"] = ""  # Pokud není podpis, zůstane prázdný

    # Determine which leader name to use
    if project.external_leader:
        leader_name = project.external_leader
        # Don't include signature for external leader
        context["signature"] = ""
    else:
        leader_name = f"{project.leader.userprofile.title} {project.leader.first_name} {project.leader.last_name}"
        # Add signature only for internal leader
        user_prefs = UserPreferences.objects.filter(user=request.user).first()
        if user_prefs and user_prefs.signature and os.path.exists(user_prefs.signature.path):
            context["signature"] = InlineImage(doc, user_prefs.signature.path, width=Cm(2.5))
        else:
            context["signature"] = ""

    context['leader_name'] = leader_name

    doc.render(context)
    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document')
    # response['Content-Disposition'] = f'attachment; filename="posudek_vedouciho_{pk}.docx"'
    response['Content-Disposition'] = f'attachment; filename="posudek_vedouciho_{project.student.username}.docx"'
    doc.save(response)
    return response


@login_required
def export_opponent_eval(request, pk):
    project = get_object_or_404(Project, pk=pk)
    # opponent_eval = getattr(project, 'opponent_eval', None)

    # Allow export for project leader if there's an external opponent
    if not (request.user == project.opponent or 
            (project.external_opponent and request.user == project.leader) or 
            request.user.is_superuser):
        messages.error(request, "Nemáte oprávnění exportovat posudek oponenta.")
        return redirect('projects:detail', pk=pk)

    doc = DocxTemplate("templates/docx/opponent_eval.docx")
    opponent_eval = getattr(project, 'opponent_eval', None)

    # Determine which opponent name to use
    if project.external_opponent:
        opponent_name = project.external_opponent
        # Don't use signature for external opponent
        signature = ""
    else:
        opponent_name = f"{project.opponent.userprofile.title} {project.opponent.first_name} {project.opponent.last_name}"
        # Add signature only for internal opponent
        user_prefs = UserPreferences.objects.filter(user=request.user).first()
        # user_prefs = UserPreferences.objects.filter(user=project.opponent).first()
        if user_prefs and user_prefs.signature and os.path.exists(user_prefs.signature.path):
            signature = InlineImage(doc, user_prefs.signature.path, width=Cm(2.5))
        else:
            signature = ""

        # Načtení dat z modelu
    context = {
        'student_name': f"{project.student.first_name} {project.student.last_name}",
        'class_name': project.student.userprofile.class_name,
        'school_year': project.scheme.year if project.scheme else "N/A",
        'opponent_name': opponent_name,
        'signature': signature,
        'project_title': project.title,
        'area1_text': opponent_eval.area1_text,
        'area1_points': opponent_eval.area1_points,
        'area2_text': opponent_eval.area2_text,
        'area2_points': opponent_eval.area2_points,
        'total_points': opponent_eval.area1_points + opponent_eval.area2_points,
        'max_points': (
            project.scheme.opponent_area1_max +
            project.scheme.opponent_area2_max
        ) if project.scheme else "N/A",
        'review_date': opponent_eval.export_date.strftime('%d.%m.%Y') if opponent_eval.export_date else '',
    }

    doc.render(context)
    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document')
    # response['Content-Disposition'] = f'attachment; filename="posudek_oponenta_{pk}.docx"'
    response['Content-Disposition'] = f'attachment; filename="posudek_oponenta_{project.student.username}.docx"'
    doc.save(response)
    return response


@login_required
def export_final_report_pdf(request, pk):
    """
    Vygeneruje jedno stránkový PDF report obsahující:
    - Studenta (jméno, třída)
    - Název, zadání
    - Vedoucí a oponent
    - Posudky vedoucího i oponenta (body)
    - Celkový počet bodů a max
    - Tabulka bodů vs známky
    """
    project = get_object_or_404(Project, pk=pk)

    # Student
    student_name = ""
    class_name = ""
    if project.student:
        student_name = f"{project.student.first_name} {project.student.last_name}"
        # Pokud je třída v userprofile:
        if hasattr(project.student, 'userprofile'):
            class_name = project.student.userprofile.class_name or ""

    # Vedoucí
    leader_name = ""
    if project.leader:
        leader_name = f"{project.leader.userprofile.title} {project.leader.first_name} {project.leader.last_name}"

    # Oponent
    opponent_name = ""
    if project.opponent:
        opponent_name = f"{project.opponent.userprofile.title} {project.opponent.first_name} {project.opponent.last_name}"

    # Posudky - vedoucí
    # Můžeš mít LeaderEvaluation s 3 oblastmi (text a body)
    leader_eval = getattr(project, 'leader_eval', None)  # nebo LeaderEvaluation.objects.filter(project=project).first()
    if leader_eval:
        leader_area1_points = leader_eval.area1_points
        leader_area2_points = leader_eval.area2_points
        leader_area3_points = leader_eval.area3_points
        leader_area1_text = leader_eval.area1_text
        leader_area2_text = leader_eval.area2_text
        leader_area3_text = leader_eval.area3_text
    else:
        leader_area1_points = 0
        leader_area2_points = 0
        leader_area3_points = 0
        leader_area1_text = ""
        leader_area2_text = ""
        leader_area3_text = ""

    # Oponent
    opponent_eval = getattr(project, 'opponent_eval', None)  
    if opponent_eval:
        opponent_area1_points = opponent_eval.area1_points
        opponent_area2_points = opponent_eval.area2_points
        opponent_area1_text = opponent_eval.area1_text
        opponent_area2_text = opponent_eval.area2_text
    else:
        opponent_area1_points = 0
        opponent_area2_points = 0
        opponent_area1_text = ""
        opponent_area2_text = ""

    # Sečíst total
    total_points = (leader_area1_points + leader_area2_points + leader_area3_points
                    + opponent_area1_points + opponent_area2_points)
    # max_points = ... buď napevno, nebo z scoreboardu
    max_leader_area1 = project.scheme.leader_area1_max
    max_leader_area2 = project.scheme.leader_area2_max
    max_leader_area3 = project.scheme.leader_area3_max
    max_opponent_area1 = project.scheme.opponent_area1_max
    max_opponent_area2 = project.scheme.opponent_area2_max
    max_points = (max_leader_area1 + max_leader_area2 + max_leader_area3 
                  + max_opponent_area1 + max_opponent_area2)

    # assignment = project.assignment (zadání práce)
    # Tabulka body vs známky -> staticky v šabloně, nebo definuj python list
    grade_table = [
        {"max":100, "min":85, "grade": "výborně"},
        {"max":84, "min":70, "grade": "chvalitebně"},
        {"max":69, "min":50, "grade": "dobře"},
        {"max":49, "min":35, "grade": "dostatečně"},
        {"max":34, "min":0, "grade": "nedostatečně"},
        # atd
    ]

    context = {
        "project": project,
        "student_name": student_name,
        "class_name": class_name,
        "leader_name": leader_name,
        "opponent_name": opponent_name,
        "delivery_date": project.delivery_work_date.strftime('%d.%m.%Y') if project.delivery_work_date else "",
        "documentation_date": project.delivery_documentation_date.strftime('%d.%m.%Y') if project.delivery_documentation_date else "",
        "leader_area1_text": leader_area1_text,
        "leader_area2_text": leader_area2_text,
        "leader_area3_text": leader_area3_text,
        "leader_area1_points": leader_area1_points,
        "leader_area2_points": leader_area2_points,
        "leader_area3_points": leader_area3_points,
        "opponent_area1_text": opponent_area1_text,
        "opponent_area2_text": opponent_area2_text,
        "opponent_area1_points": opponent_area1_points,
        "opponent_area2_points": opponent_area2_points,
        "total_points": total_points,
        "max_points": max_points,
        "grade_table": grade_table,
        "leader_max_1": max_leader_area1,
        "leader_max_2": max_leader_area2,
        "leader_max_3": max_leader_area3,
        "opponent_max_1": max_opponent_area1,
        "opponent_max_2": max_opponent_area2,
        "defence_points": 100 - max_points,
        "leader_questions": leader_eval.defense_questions if leader_eval else "",
        "opponent_questions": opponent_eval.defense_questions if opponent_eval else "",
        # ...
    }

    # Vyrenderovat HTML šablonu do řetězce
    html_string = render_to_string("pdf/final_report.html", context)

    # Convert HTML to PDF (WeasyPrint)
    pdf_file = HTML(string=html_string).write_pdf()

    # Odpověď do prohlížeče
    response = HttpResponse(pdf_file, content_type='application/pdf')
    # filename = f"zaverecny_posudek_{project.pk}.pdf"
    filename = f"zaverecny_posudek_{project.student.username}.pdf"
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


@login_required
def export_milestones_pdf(request):
    """
    Exportuje všechny milníky pro projekty, kde je přihlášený uživatel vedoucím.
    Milníky jsou seskupeny podle projektů a seřazeny podle data.
    """

    user = request.user
    # Zkus získat default_year z předvoleb, pokud existuje
    default_year = None
    if hasattr(user, 'preferences'):
        default_year = user.preferences.default_year

    # Pokud není předán GET parametr "year", použijeme default_year
    selected_year = request.GET.get('year', default_year)
    
    # Filtrujeme projekty podle ScoreBoardu (ScoringScheme.year) nebo případně podle studijního roku studenta
    if selected_year:
        projects = Project.objects.filter(scheme__year=selected_year, leader=request.user).order_by('student__last_name')
    else:
        # projects = Project.objects.all()
        projects = Project.objects.filter(leader=request.user).order_by('student__last_name')

    context = {
        'projects': projects,
    }

    # Získání všech projektů, kde je přihlášený uživatel vedoucím
    # projects = Project.objects.filter(leader=request.user).order_by('student__last_name')

    # Příprava dat pro šablonu
    projects_data = []
    for project in projects:
        milestones = Milestone.objects.filter(project=project).order_by('deadline')
        milestones_data = []
        for milestone in milestones:
            status = milestone.get_status_display()
            if status == 'Dokončeno':
                row_color = 'green'
            elif status == 'Rozpracováno':
                if milestone.deadline and milestone.deadline < datetime.now().date():  # if milestone.deadline
                    row_color = 'red'
                elif milestone.deadline:
                    row_color = 'yellow'
                else:
                    row_color = 'white'
            else:
                if milestone.deadline and milestone.deadline < datetime.now().date():  # if milestone.deadline
                    row_color = 'red'
                else:
                    row_color = 'white'
            milestones_data.append({
                'title': milestone.title,
                'deadline': milestone.deadline.strftime('%d.%m.%Y') if milestone.deadline else "N/A",
                'status': milestone.get_status_display(),
                'note': milestone.note,
                'row_color': row_color,
                # 'is_overdue': milestone.deadline < datetime.now().date() if milestone.deadline else False
            })
        
        projects_data.append({
            'project_title': project.title,
            'milestones': milestones_data,
            'student_name': f"{project.student.first_name} {project.student.last_name}",
        })

    # Kontext pro šablonu
    context = {
        'projects': projects_data,
        'current_date': datetime.now()
    }

    # Vyrenderování HTML šablony do řetězce
    html_string = render_to_string('projects/pdf_milestones.html', context)

    # Převod HTML na PDF pomocí WeasyPrint
    pdf_file = HTML(string=html_string).write_pdf()

    # Odpověď do prohlížeče
    response = HttpResponse(pdf_file, content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="milestones_report.pdf"'
    return response

@login_required
def project_details_overview(request):
    """
    Displays an overview of all projects where the current user is the leader or opponent.
    Shows student details, project title, control checks, submission status, and evaluations.
    """
    user = request.user
    
    # Get default year from user preferences if available
    default_year = None
    if hasattr(user, 'preferences'):
        default_year = user.preferences.default_year

    # Get all available school years from ScoringScheme for the dropdown
    available_years = ScoringScheme.objects.values_list('year', flat=True).distinct().order_by('-year')
    
    # Use year from GET parameter or default from preferences
    selected_year = request.GET.get('year', default_year)
    
    # Get source project ID from URL parameters
    source_project_id = request.GET.get('from_project', None)
    
    # Determine if we want to see leader's projects or opponent's projects
    view_type = request.GET.get('view_type', 'leader')
    
    # Filter projects by year and leader/opponent role
    if view_type == 'opponent':
        if selected_year:
            projects = Project.objects.filter(scheme__year=selected_year, opponent=user).select_related(
                'student', 'student__userprofile').order_by('student__userprofile__class_name', 'student__last_name')
        else:
            projects = Project.objects.filter(opponent=user).select_related(
                'student', 'student__userprofile').order_by('student__userprofile__class_name', 'student__last_name')
    else:  # default to leader view
        if selected_year:
            projects = Project.objects.filter(scheme__year=selected_year, leader=user).select_related(
                'student', 'student__userprofile').order_by('student__userprofile__class_name', 'student__last_name')
        else:
            projects = Project.objects.filter(leader=user).select_related(
                'student', 'student__userprofile').order_by('student__userprofile__class_name', 'student__last_name')
    
    projects_data = []
    for project in projects:
        # Get control checks for this project
        controls = project.controls.all().order_by('date')
        
        # Check controls and format display values appropriately
        control_1 = 'Ne'
        control_2 = 'Ne'
        control_3 = 'Ne'
        
        if len(controls) >= 1:
            if controls[0].evaluation:
                control_1 = controls[0].evaluation
            else:
                control_1 = controls[0].date.strftime('%d.%m.%Y') if controls[0].date else 'Ano'
                
        if len(controls) >= 2:
            if controls[1].evaluation:
                control_2 = controls[1].evaluation
            else:
                control_2 = controls[1].date.strftime('%d.%m.%Y') if controls[1].date else 'Ano'
                
        if len(controls) >= 3:
            if controls[2].evaluation:
                control_3 = controls[2].evaluation
            else:
                control_3 = controls[2].date.strftime('%d.%m.%Y') if controls[2].date else 'Ano'
        
        # Check if work and documentation were delivered - show dates if available
        work_delivered = project.delivery_work_date.strftime('%d.%m.%Y') if project.delivery_work_date else 'Ne'
        docs_delivered = project.delivery_documentation_date.strftime('%d.%m.%Y') if project.delivery_documentation_date else 'Ne'
        
        # Check if delay was granted - show date if available
        delay_granted = project.delayed_submission_date.strftime('%d.%m.%Y') if project.delayed_submission_date else 'Ne'
        
        # Get leader evaluation points if available
        leader_eval = getattr(project, 'leader_eval', None)
        if leader_eval:
            leader_points = leader_eval.area1_points + leader_eval.area2_points + leader_eval.area3_points
        else:
            leader_points = '-'
            
        # Get opponent evaluation points if available
        opponent_eval = getattr(project, 'opponent_eval', None)
        if opponent_eval:
            opponent_points = opponent_eval.area1_points + opponent_eval.area2_points
        else:
            opponent_points = '-'
            
        # Get student details
        student_name = f"{project.student.first_name} {project.student.last_name}" if project.student else "N/A"
        class_name = project.student.userprofile.class_name if project.student and hasattr(project.student, 'userprofile') else "N/A"
        
        projects_data.append({
            'id': project.id,
            'student_name': student_name,
            'class_name': class_name,
            'title': project.title,
            'control_1': control_1,
            'control_2': control_2,
            'control_3': control_3,
            'work_delivered': work_delivered,
            'docs_delivered': docs_delivered,
            'delay_granted': delay_granted,
            'leader_points': leader_points,
            'opponent_points': opponent_points,
        })
    
    context = {
        'projects': projects_data,
        'selected_year': selected_year,
        'available_years': available_years,
        'source_project_id': source_project_id,
        'is_teacher': user.groups.filter(name='Teacher').exists(),
        'view_type': view_type,  # Add view type to context
        'username': f"{user.userprofile.title} {user.first_name} {user.last_name}",
    }
    
    return render(request, 'projects/project_details_overview.html', context)

@login_required
def export_project_details_pdf(request):
    """
    Generates a PDF with project details and repeating table headers on each page.
    """
    user = request.user
    
    # Get default year from user preferences if available
    default_year = None
    if hasattr(user, 'preferences'):
        default_year = user.preferences.default_year

    # Use year from GET parameter or default from preferences
    selected_year = request.GET.get('year', default_year)
    
    # Determine if we want to see leader's projects or opponent's projects
    view_type = request.GET.get('view_type', 'leader')
    
    # Filter projects by year and leader/opponent role
    if view_type == 'opponent':
        if selected_year:
            projects = Project.objects.filter(scheme__year=selected_year, opponent=user).select_related(
                'student', 'student__userprofile').order_by('student__userprofile__class_name', 'student__last_name')
        else:
            projects = Project.objects.filter(opponent=user).select_related(
                'student', 'student__userprofile').order_by('student__userprofile__class_name', 'student__last_name')
    else:  # default to leader view
        if selected_year:
            projects = Project.objects.filter(scheme__year=selected_year, leader=user).select_related(
                'student', 'student__userprofile').order_by('student__userprofile__class_name', 'student__last_name')
        else:
            projects = Project.objects.filter(leader=user).select_related(
                'student', 'student__userprofile').order_by('student__userprofile__class_name', 'student__last_name')
    
    projects_data = []
    for project in projects:
        # Get control checks for this project
        controls = project.controls.all().order_by('date')
        
        # Check controls and format display values appropriately
        control_1 = 'Ne'
        control_2 = 'Ne'
        control_3 = 'Ne'
        
        if len(controls) >= 1:
            if controls[0].evaluation:
                control_1 = controls[0].evaluation
            else:
                control_1 = controls[0].date.strftime('%d.%m.%Y') if controls[0].date else 'Ano'
                
        if len(controls) >= 2:
            if controls[1].evaluation:
                control_2 = controls[1].evaluation
            else:
                control_2 = controls[1].date.strftime('%d.%m.%Y') if controls[1].date else 'Ano'
                
        if len(controls) >= 3:
            if controls[2].evaluation:
                control_3 = controls[2].evaluation
            else:
                control_3 = controls[2].date.strftime('%d.%m.%Y') if controls[2].date else 'Ano'
        
        # Check if work and documentation were delivered - show dates if available
        work_delivered = project.delivery_work_date.strftime('%d.%m.%Y') if project.delivery_work_date else 'Ne'
        docs_delivered = project.delivery_documentation_date.strftime('%d.%m.%Y') if project.delivery_documentation_date else 'Ne'
        
        # Check if delay was granted - show date if available
        delay_granted = project.delayed_submission_date.strftime('%d.%m.%Y') if project.delayed_submission_date else 'Ne'
        
        # Get leader evaluation points if available
        leader_eval = getattr(project, 'leader_eval', None)
        if leader_eval:
            leader_points = leader_eval.area1_points + leader_eval.area2_points + leader_eval.area3_points
        else:
            leader_points = '-'
            
        # Get opponent evaluation points if available
        opponent_eval = getattr(project, 'opponent_eval', None)
        if opponent_eval:
            opponent_points = opponent_eval.area1_points + opponent_eval.area2_points
        else:
            opponent_points = '-'
            
        # Get student details
        student_name = f"{project.student.first_name} {project.student.last_name}" if project.student else "N/A"
        class_name = project.student.userprofile.class_name if project.student and hasattr(project.student, 'userprofile') else "N/A"
        
        projects_data.append({
            'id': project.id,
            'student_name': student_name,
            'class_name': class_name,
            'title': project.title,
            'control_1': control_1,
            'control_2': control_2,
            'control_3': control_3,
            'work_delivered': work_delivered,
            'docs_delivered': docs_delivered,
            'delay_granted': delay_granted,
            'leader_points': leader_points,
            'opponent_points': opponent_points,
        })
    
    context = {
        'projects': projects_data,
        'selected_year': selected_year,
        'current_date': datetime.now(),
        'username': f"{user.userprofile.title} {user.first_name} {user.last_name}",
        'view_type': view_type,  # Add view type to context
        'role': "Oponent" if view_type == 'opponent' else "Vedoucí"  # Add role title
    }
    
    # Add specific HTML/CSS for WeasyPrint to properly handle page breaks and repeating headers
    html_string = render_to_string('projects/pdf_project_details.html', context)
    
    # Generate PDF with WeasyPrint
    pdf_file = HTML(string=html_string).write_pdf()
    
    # Prepare response
    response = HttpResponse(pdf_file, content_type='application/pdf')
    role_text = "oponent" if view_type == 'opponent' else "vedouci"
    filename = f"projekty_prehled_{role_text}_{datetime.now().strftime('%Y-%m-%d')}.pdf"
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    
    return response

# 'is_teacher': user.groups.filter(name='Teacher').exists(),