import os
import re

input_folder = "input"
output_folder = "output"

# Output folder create pannurom
if not os.path.exists(output_folder):
    os.makedirs(output_folder)

def process_xml_content(xml_content):
    # ==========================================
    # STEP 1: Title kulla irukura bold tags-a remove panradhu
    # ==========================================
    def replace_bold(match):
        title_content = match.group(0)
        title_content = title_content.replace("<bold>", "").replace("</bold>", "").replace("<bold/>", "")
        return title_content

    pattern_title = r'<title.*?>.*?</title>'
    xml_content = re.sub(pattern_title, replace_bold, xml_content, flags=re.DOTALL | re.IGNORECASE)

    # ==========================================
    # STEP 2: </sec><sec...> next line-ku maathradhu
    # ==========================================
    pattern_sec = r'</sec>\s*(<sec\b[^>]*>)'
    xml_content = re.sub(pattern_sec, r'</sec>\n\1', xml_content, flags=re.IGNORECASE)

    # ==========================================
    # STEP 3: Dynamic Page Track & <fig><img/></fig> -> <graphic/> Tag Conversion
    # ==========================================
    fx_counter = [1]
    current_page = ["001"] # Default fallback page number

    combined_pattern = r'(<\?pageStart\b[^>]*\bpagination=["\'](\d+)["\'][^>]*\?>|<pageStart\b[^>]*\bpagination=["\'](\d+)["\'][^>]*/>)|(<p>\s*<fig>\s*<img\s*/>\s*</fig>\s*</p>)|(<fig>\s*<img\s*/>\s*</fig>)'

    def replacer(match):
        if match.group(1):
            page_num_val = match.group(2) if match.group(2) else match.group(3)
            current_page[0] = f"{int(page_num_val):03d}"
            return match.group(0)
        elif match.group(4):
            fx_str = f"fx_{fx_counter[0]:03d}"
            fx_counter[0] += 1
            pg_str = f"pg_{current_page[0]}"
            return f'<graphic xmlns:xlink="http://www.w3.org/1999/xlink" xlink:href="img/000000000000_{pg_str}_{fx_str}.jpg"/>'
        elif match.group(5):
            fx_str = f"fx_{fx_counter[0]:03d}"
            fx_counter[0] += 1
            pg_str = f"pg_{current_page[0]}"
            return f'<p><graphic xmlns:xlink="http://www.w3.org/1999/xlink" xlink:href="img/000000000000_{pg_str}_{fx_str}.jpg"/></p>'

        return match.group(0)

    xml_content = re.sub(combined_pattern, replacer, xml_content, flags=re.IGNORECASE)

    # ==========================================
    # STEP 4: Remove nested duplicate <p><p>...</p></p> tags
    # ==========================================
    pattern_nested_p = r'<p\b[^>]*>\s*<p\b[^>]*>(.*?)</p>\s*</p>'
    while re.search(pattern_nested_p, xml_content, flags=re.DOTALL | re.IGNORECASE):
        xml_content = re.sub(pattern_nested_p, r'<p>\1</p>', xml_content, flags=re.DOTALL | re.IGNORECASE)

    # ==========================================
    # STEP 5: Add <xref> links for "Seiten" numbers
    # ==========================================
    def format_seiten_links(match):
        full_text = match.group(0)
        pattern_pages = r'(Seiten\s+(\d+))|((?:und|,)\s+(\d+))'
        
        def link_replacer(m):
            if m.group(1):
                p_num = m.group(2)
                return f'<xref ref-type="link-tosolution" rid="pg{p_num}">Seiten {p_num}</xref>'
            elif m.group(3):
                join_word = m.group(3).split()[0]
                p_num = m.group(4)
                return f'{join_word} <xref ref-type="link-tosolution" rid="pg{p_num}">{p_num}</xref>'
            return m.group(0)
            
        return re.sub(pattern_pages, link_replacer, full_text, flags=re.IGNORECASE)

    pattern_seiten_block = r'Seiten\s+\d+(?:\s*(?:und|,)\s*\d+)*'
    xml_content = re.sub(pattern_seiten_block, format_seiten_links, xml_content, flags=re.IGNORECASE)

    # ==========================================
    # STEP 6: Remove EMPTY <p></p> tags
    # ==========================================
    pattern_empty_p = r'<p\b[^>]*>\s*</p>|<p\b[^>]*/>'
    xml_content = re.sub(pattern_empty_p, '', xml_content, flags=re.IGNORECASE)

    # ==========================================
    # STEP 7: STRICT Punctuation check for <statement> tag
    # ==========================================
    def wrap_subtask_statement(match):
        sec_start = match.group(1)
        label_part = match.group(2)
        p_content = match.group(3)
        sec_end = match.group(4)

        # Remove <p> and </p> tags
        inner_text = re.sub(r'^<p\b[^>]*>', '', p_content, flags=re.IGNORECASE)
        inner_text = re.sub(r'</p>$', '', inner_text, flags=re.IGNORECASE).strip()

        # ONLY check if the content ends with punctuation (., ;, ?, :) BEFORE </p>
        if re.search(r'[.;?:!]\s*$', inner_text):
            wrapped_p = f"<statement>\n{p_content}\n</statement>"
            return f"{sec_start}\n{label_part}\n{wrapped_p}\n{sec_end}"
        else:
            return f"{sec_start}\n{label_part}\n{p_content}\n{sec_end}"

    pattern_subtask = r'(<sec\b[^>]*sec-type=["\']subtask["\'][^>]*>)\s*(<label>.*?</label>)\s*(<p>.*?</p>)\s*(</sec>)'
    xml_content = re.sub(pattern_subtask, wrap_subtask_statement, xml_content, flags=re.DOTALL | re.IGNORECASE)

    # ==========================================
    # STEP 8: ACCURATE Subtask ID Replacement for ALL Children (a, b, c, d...)
    # ==========================================
    def fix_subtask_ids_across_file(content):
        # Sec task ah base panni split panrom
        parts = re.split(r'(<sec\b[^>]*sec-type=["\']task["\'][^>]*>)', content, flags=re.IGNORECASE)
        
        new_content = [parts[0]]
        
        for i in range(1, len(parts), 2):
            task_header = parts[i]
            task_body = parts[i+1] if (i+1) < len(parts) else ""
            
            # Label number-a search panrom (e.g. 62 -> 062)
            label_match = re.search(r'<label>\s*(\d+)\s*</label>', task_body, flags=re.IGNORECASE)
            if label_match:
                task_num_raw = label_match.group(1)
                formatted_task_num = f"{int(task_num_raw):03d}"
                
                # Ulla irukura ELLA subtask IDs-ayum update panrom
                def subtask_id_replacer(m):
                    prefix = m.group(1)       # id="pg239_task
                    sub_letter = m.group(2)   # a, b, c...
                    quote = m.group(3)        # "
                    return f'{prefix}{formatted_task_num}{sub_letter}{quote}'

                task_body = re.sub(
                    r'(id=["\'][^"\']*_task)\d+([a-z]+)(["\'])',
                    subtask_id_replacer,
                    task_body,
                    flags=re.IGNORECASE
                )
            
            new_content.append(task_header + task_body)
            
        return "".join(new_content)

    xml_content = fix_subtask_ids_across_file(xml_content)

    # ==========================================
    # STEP 9: Remove orphan </fig> inside <p>...</p> (ONLY if <fig> opening tag is missing)
    # ==========================================
    def remove_orphan_fig_close(match):
        p_block = match.group(0)
        if not re.search(r'<fig\b', p_block, flags=re.IGNORECASE):
            return re.sub(r'</fig>', '', p_block, flags=re.IGNORECASE)
        return p_block

    pattern_p_block = r'<p\b[^>]*>.*?</p>'
    xml_content = re.sub(pattern_p_block, remove_orphan_fig_close, xml_content, flags=re.DOTALL | re.IGNORECASE)

    return xml_content

def process_xml_files():
    if not os.path.exists(input_folder):
        print(f"Error: '{input_folder}' folder illa! First 'input' folder create pannungga.")
        return

    files = [f for f in os.listdir(input_folder) if f.endswith('.xml')]
    
    if not files:
        print(f"'{input_folder}' folder-la XML files edhum illa!")
        return

    for file_name in files:
        input_path = os.path.join(input_folder, file_name)
        output_path = os.path.join(output_folder, file_name)

        with open(input_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # Update process
        updated_content = process_xml_content(content)

        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(updated_content)

        print(f"Processed: {file_name} -> Saved to '{output_folder}/'")

if __name__ == "__main__":
    process_xml_files()