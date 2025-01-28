import os
from docxtpl import DocxTemplate, InlineImage
from docx.shared import Cm

# Cesta k šabloně
template_path = "/Users/joe/Python/django/evidence_mp/templates/docx/leader_eval.docx"  # Upravte cestu k vaší šabloně

# Cesta k podpisu
signature_path = "/Users/joe/Python/django/evidence_mp/media/signatures/signature_1920x1280_ah07GYD.png"  # Upravte na skutečnou cestu

# Ověření, zda soubory existují
if not os.path.exists(template_path):
    print(f"❌ Šablona nenalezena: {template_path}")
    exit()

if not os.path.exists(signature_path):
    print(f"❌ Obrázek nenalezen: {signature_path}")
    exit()

print("✅ Šablona a obrázek existují!")

# Načtení šablony
doc = DocxTemplate(template_path)

# Vytvoření obrázku
signature = InlineImage(doc, signature_path, width=Cm(3))

# Kontext pro renderování
context = {
    "student_name": "Pepa Zdepa",
    "class_name": "IT4",
    "project_title": "Testovací projekt",
    "signature": signature,  # Toto odpovídá ALT textu v šabloně
}

print("🔄 Spouštím renderování...")
doc.render(context)

# Uložení nového dokumentu
output_path = "output_test.docx"
doc.save(output_path)

print(f"✅ Dokument uložen jako: {output_path}")
