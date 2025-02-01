import os
from django.shortcuts import get_object_or_404, redirect, render
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from ..models import Project, LeaderEvaluation, UserPreferences
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
            response['Content-Disposition'] = f'attachment; filename="konzultacni_list_{pk}.docx"'
            doc.save(response)
            return response
    else:
        form = DateInputForm()
        context = {
        'form': form,
        'project': project,
        'is_teacher': request.user.groups.filter(name='Teacher').exists(),
        'is_student': request.user.groups.filter(name='Student').exists(),
    }
        
    return render(request, 'projects/export_form.html',context)


@login_required
def export_project_assignment(request, pk):
    project = get_object_or_404(Project, pk=pk)

    template = "templates/docx/assignment_IT.docx" if project.student.userprofile.study_branch == "IT" else "templates/docx/assignment_E.docx"
    
    context = {
        'student_name': f"{project.student.first_name} {project.student.last_name}",
        'class_name': project.student.userprofile.class_name,
        'school_year': project.scheme.year if project.scheme else "N/A",
        'project_title': project.title,
        'assignment': project.assignment,
    }

    doc = DocxTemplate(template)
    doc.render(context)

    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document')
    response['Content-Disposition'] = f'attachment; filename="zadani_prace_{pk}.docx"'
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
    projects = Project.objects.all()

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

    doc.render(context)
    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document')
    response['Content-Disposition'] = f'attachment; filename="posudek_vedouciho_{pk}.docx"'
    doc.save(response)
    return response


@login_required
def export_opponent_eval(request, pk):
    project = get_object_or_404(Project, pk=pk)
    # opponent_eval = get_object_or_404(OpponentEvaluation, project=project)

    doc = DocxTemplate("templates/docx/opponent_eval.docx")
    opponent_eval = getattr(project, 'opponent_eval', None)

    # Načtení dat z modelu
    context = {
        'student_name': f"{project.student.first_name} {project.student.last_name}",
        'class_name': project.student.userprofile.class_name,
        'school_year': project.scheme.year if project.scheme else "N/A",
        'opponent_name': f"{project.opponent.userprofile.title} {project.opponent.first_name} {project.opponent.last_name}",
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

    # Cesta k šabloně
    # template_path = os.path.join('static', 'templates', 'opponent_eval_template.docx')
    # doc = DocxTemplate(template_path)

    user_prefs = UserPreferences.objects.filter(user=request.user).first()

    # Vložení podpisu, pokud existuje
    if user_prefs and user_prefs.signature and os.path.exists(user_prefs.signature.path):
        signature_img = InlineImage(doc, user_prefs.signature.path, width=Cm(2.5))  
        context["signature"] = signature_img  # Odkazujeme se na ALT text v šabloně
    else:
        context["signature"] = ""  # Pokud není podpis, zůstane prázdný

    doc.render(context)
    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document')
    response['Content-Disposition'] = f'attachment; filename="posudek_oponenta_{pk}.docx"'
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
        # ...
    }

    # Vyrenderovat HTML šablonu do řetězce
    html_string = render_to_string("pdf/final_report.html", context)

    # Convert HTML to PDF (WeasyPrint)
    pdf_file = HTML(string=html_string).write_pdf()

    # Odpověď do prohlížeče
    response = HttpResponse(pdf_file, content_type='application/pdf')
    filename = f"zaverecny_posudek_{project.pk}.pdf"
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response
