import os

files_to_patch = [
    r'c:\Users\denisdev\Documents\tournament_platform\core\templates\admin_section.html',
]

for file_path in files_to_patch:
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Form tag update
    old_form = '<form method="post" action="{% url \'create_tournament\' %}" id="inline-tournament-form">'
    new_form = '<form method="post" action="{% url \'create_tournament\' %}" id="inline-tournament-form" enctype="multipart/form-data">'
    
    if old_form in content:
        content = content.replace(old_form, new_form)
        print(f"Form tag updated in {os.path.basename(file_path)}")
    else:
        print(f"Form tag NOT found in {os.path.basename(file_path)}")

    # Field update
    old_field = '<div class="span2"><label>Опис форми реєстрації команди</label>{{ tournament_form.registration_form_description }}{% if tournament_form.registration_form_description.errors %}<div class="err">{{ tournament_form.registration_form_description.errors }}</div>{% endif %}</div>'
    new_field = old_field + '\n                        <div class="span2"><label>Банер турніру</label>{{ tournament_form.banner_image }}{% if tournament_form.banner_image.errors %}<div class="err">{{ tournament_form.banner_image.errors }}</div>{% endif %}</div>'

    if old_field in content:
        content = content.replace(old_field, new_field)
        print(f"Field updated in {os.path.basename(file_path)}")
    else:
        # Try with different whitespace?
        print(f"Field NOT found in {os.path.basename(file_path)}")

    with open(file_path, 'w', encoding='utf-8', newline='') as f:
        f.write(content)
