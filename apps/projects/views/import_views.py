import csv
import io
from django.contrib.auth.models import User, Group
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from apps.profiles.models import UserProfile
from ..models import Project, Milestone
import csv
from datetime import datetime
from django.contrib.auth.models import User
import datetime
import string
import secrets


def admin_check(user):
    return user.is_superuser

def generate_password(length=10):
    """
    Vygeneruje náhodné heslo o dané délce (default 10),
    vynechává 'O', '0', 'I', 'l', aby se předešlo záměně.
    """
    # Základní sada znaků: ascii_letters, digits, plus pár speciálních
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*"

    # Odebereme homogenní (vizuálně podobné) znaky
    # Např. O (velké o), 0 (nula), I (velké i), l (malé L)
    for ch in ["O", "0", "I", "l"]:
        alphabet = alphabet.replace(ch, "")

    # Vygenerujeme heslo dané délky
    return ''.join(secrets.choice(alphabet) for _ in range(length))


@login_required
def import_milestones_csv(request, project_id):
    """
    Např. ve formuláři 'upload file' -> POST -> 
    python parse -> create Milestone pro kazdy radek
    """
    project = get_object_or_404(Project, pk=project_id)
    if not request.user.groups.filter(name='Teacher').exists():
        messages.error(request, "Jen učitel může importovat milníky.")
        return redirect('projects:detail', pk=project_id)
    
    if request.method == 'POST':
        csv_file = request.FILES.get('file')
        if csv_file is None:
            messages.error(request, "Nebylo vybráno žádné CSV.")
            return redirect('projects:detail', pk=project_id)

        decoded_file = csv_file.read().decode('utf-8').splitlines()
        reader = csv.reader(decoded_file, delimiter=';')  # nebo ',' atd.
        # Očekáváš např. sloupce: title;deadline;status;note

        for row in reader:
            if len(row) < 1:
                continue

            title = row[0]
            deadline_str = row[1] if len(row) > 1 else None
            status = row[2] if len(row) > 2 else 'not_started'
            note = row[3] if len(row) > 3 else ''

            # Ošetření parsování data
            deadline = None
            if deadline_str:
                try:
                    deadline = datetime.strptime(deadline_str, '%Y-%m-%d').date()
                except ValueError:
                    messages.error(request, f"Neplatný formát datumu: {deadline_str}. Řádek přeskočen.")
                    continue  # Přeskočí špatně formátované řádky

            Milestone.objects.create(
                project=project,
                title=title,
                deadline=deadline,
                status=status,
                note=note
            )

        messages.success(request, "Milníky naimportovány.")
        return redirect('projects:detail', pk=project_id)
    
    # GET: zobrazit formulář
    return render(request, 'projects/milestone_import.html', {'project': project})


@user_passes_test(admin_check)
def import_users_csv(request):
    """
    Očekává CSV (oddělené středníkem):
    username;first_name;last_name;email;role;class_name;branch;title
    Pokud branch chybí, nastaví se 'E'.
    Pokud role == teacher, sloupec 'title' se zapíše do userprofile.title.
    """
    if request.method == 'POST':
        csv_file = request.FILES.get('file')
        if not csv_file:
            messages.error(request, "Není vybrán žádný CSV soubor.")
            return redirect('import_users_csv')

        data = csv_file.read().decode('utf-8')
        reader = csv.reader(io.StringIO(data), delimiter=';', quotechar='"')

        student_group = Group.objects.get(name='Student')
        teacher_group = Group.objects.get(name='Teacher')

        count_created = 0
        row_counter = 0

        newly_created_passwords = []

        for row in reader:
            row_counter += 1
            
            # Minimální počet sloupců = 7 (plus 8. sloupec pro title)
            # username;fname;lname;email;role;class_name;branch;title
            if len(row) < 7:
                messages.warning(request, f"Řádek {row_counter}: Příliš málo sloupců (očekáváno aspoň 7).")
                continue

            username = row[0].strip()
            first_name = row[1].strip()
            last_name = row[2].strip()
            email = row[3].strip()
            role = row[4].strip().lower()  # "student" / "teacher"
            class_name = row[5].strip()

            # 7. sloupec: branch
            if len(row) > 6:
                branch = row[6].strip()
                if not branch:
                    branch = 'E'
            else:
                # Pokud chybí, default 'E'
                branch = 'E'

            # 8. sloupec: title (jen pro učitele)
            title = ""
            if len(row) > 7:
                title = row[7].strip()

            # Vytvoření/upravení user
            user, created = User.objects.get_or_create(
                username=username,
                defaults={
                    'first_name': first_name,
                    'last_name': last_name,
                    'email': email
                }
            )

            if not created:
                # user už existuje -> update jméno, email
                user.first_name = first_name
                user.last_name = last_name
                user.email = email
                user.save()

            if role == 'student':
                user.groups.set([student_group])
                if not hasattr(user, 'userprofile'):
                    profile = UserProfile.objects.create(user=user)
                else:
                    profile = user.userprofile

                # Student -> class_name, branch
                profile.class_name = class_name
                profile.study_branch = branch
                # Student obvykle nemá title -> ponecháme prázdné
                profile.save()

            elif role == 'teacher':
                user.groups.set([teacher_group])
                if not hasattr(user, 'userprofile'):
                    profile = UserProfile.objects.create(user=user)
                else:
                    profile = user.userprofile

                # Učitel -> class_name (pokud používá?), branch (pokud používá?), plus title
                # profile.class_name = class_name  # pokud to i pro učitele dává smysl
                # profile.study_branch = branch
                profile.title = title  # <--- klíčové pro nový sloupec
                profile.save()

            # Pokud user nově vznikl => generovat heslo
            if created:
                new_password = generate_password(10)  # funkce pro generování hesel
                user.set_password(new_password)
                user.save()

                newly_created_passwords.append({
                    'username': username,
                    'password': new_password
                })

            count_created += 1

        # Ulož seznam hesel do session pro stažení
        request.session['imported_passwords'] = newly_created_passwords
        request.session.modified = True

        messages.success(request, f"Import hotov, zpracováno {count_created} řádků.")
        return redirect('projects:import_result')

    return render(request, 'users/import_users.html')

@user_passes_test(admin_check)
def import_result(request):
    # Tady zobrazíme odkaz "stáhnout CSV s hesly"
    newly_created_passwords = request.session.get('imported_passwords', [])
    # print("DEBUG: newly_created_passwords =", newly_created_passwords)
    # Můžeš vypsat do tabulky?
    return render(request, 'projects/import_result.html', {
        'newly_created_passwords': newly_created_passwords,
    })



@user_passes_test(admin_check) # nebo login_required + check user.is_superuser
def import_projects(request):
    """
    CSV formát (quotechar='"', delimiter=';'), řádky:
    student_username;title;description;[leader_username];[opponent_username]
    V případě chyb se řádek přeskočí a zaloguje.
    """
    log_entries = []  # sem budeme ukládat záznamy o přeskočených řádcích

    if request.method == 'POST':
        csv_file = request.FILES.get('file')
        if not csv_file:
            messages.error(request, "Není vybrán žádný CSV soubor.")
            return redirect('projects:import_projects')

        # Čtení CSV s ohledem na uvozovky a středník
        data = csv_file.read().decode('utf-8', errors='replace')
        reader = csv.reader(io.StringIO(data), delimiter=';', quotechar='"')

        count_created = 0
        row_num = 0

        for row in reader:
            row_num += 1
            # Očekávaný minimální počet sloupců = 3 (student, title, description)
            if len(row) < 3:
                log_entries.append(f"Řádek {row_num}: Nedostatečný počet sloupců.")
                continue

            student_username = row[0].strip()
            title = row[1].strip()
            description = row[2].strip()

            leader_username = row[3].strip() if len(row) > 3 else ""
            opponent_username = row[4].strip() if len(row) > 4 else ""

            # Najít studenta
            try:
                student = User.objects.get(username=student_username)
            except User.DoesNotExist:
                log_entries.append(f"Řádek {row_num}: Student '{student_username}' neexistuje.")
                continue

            # Případně leader
            leader = None
            if leader_username:
                try:
                    leader = User.objects.get(username=leader_username)
                except User.DoesNotExist:
                    log_entries.append(f"Řádek {row_num}: Vedoucí '{leader_username}' neexistuje. Přeskakuji.")
                    continue

            # Případně opponent
            opponent = None
            if opponent_username:
                try:
                    opponent = User.objects.get(username=opponent_username)
                except User.DoesNotExist:
                    log_entries.append(f"Řádek {row_num}: Oponent '{opponent_username}' neexistuje. Přeskakuji.")
                    continue

            # Kontrola duplicity (stejný title + stejný student)
            existing = Project.objects.filter(title=title, student=student).exists()
            if existing:
                log_entries.append(f"Řádek {row_num}: Projekt '{title}' pro studenta '{student_username}' už existuje.")
                continue

            # Vytvořit nový Project
            Project.objects.create(
                student=student,
                title=title,
                description=description,
                leader=leader,
                opponent=opponent
            )
            count_created += 1

        messages.success(request, f"Import hotov. Vytvořeno {count_created} projektů.")
        # Můžeme log_entries uložit do session, abychom je zobrazili ve výsledné stránce nebo stáhli jako CSV
        request.session['import_logs'] = log_entries
        return redirect('projects:import_result')

    return render(request, 'projects/import_projects.html')


@user_passes_test(admin_check)
def import_result_view(request):
    """
    Zobrazí log_entries ze session, příp. nabídne stažení jako CSV.
    """
    log_entries = request.session.pop('import_logs', [])
    return render(request, 'projects/import_result.html', {'log_entries': log_entries})


@user_passes_test(admin_check)
def download_passwords_csv(request):
    newly_created_passwords = request.session.get('imported_passwords', [])
    if not newly_created_passwords:
        messages.warning(request, "Žádná nová hesla k dispozici.")
        return redirect('import_result')

    # vytvořit CSV v paměti
    output = io.StringIO()
    writer = csv.writer(output, delimiter=';', quotechar='"')
    writer.writerow(["username", "password"])  # hlavička
    for item in newly_created_passwords:
        writer.writerow([item['username'], item['password']])

    # Vrátit jako HttpResponse
    response = HttpResponse(output.getvalue(), content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="new_passwords.csv"'
    return response
