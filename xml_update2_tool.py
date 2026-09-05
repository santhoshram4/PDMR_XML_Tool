import os
import re
from datetime import datetime

# ==========================================
# EXPIRY DATE CHECK (Expiry: Sep 30, 2026)
# ==========================================
EXPIRY_DATE = datetime(2026, 9, 30, 23, 59, 59)

def check_expiry():
    current_time = datetime.now()
    if current_time > EXPIRY_DATE:
        print("\n" + "=" * 55)
        print(" ERROR: Script Expired!")
        print(" This tool has expired on August 31, 2026. Please contact Tool Developer.")
        print("=" * 55 + "\n")
        return False
    return True

input_folder = "input"
output_folder = "output"

def read_file_safely(file_path):
    """Reads file content trying multiple encodings to avoid utf-8 decode errors."""
    encodings = ['utf-8', 'latin-1', 'iso-8859-1', 'cp1252']
    for enc in encodings:
        try:
            with open(file_path, 'r', encoding=enc) as f:
                return f.read()
        except UnicodeDecodeError:
            continue
    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
        return f.read()

def get_isbn_number():
    txt_path = os.path.join(input_folder, "Mention_ISBN_Num.txt")
    default_isbn = "000000000000"
    
    if os.path.exists(txt_path):
        try:
            content = read_file_safely(txt_path)
            match = re.search(r'ISBN\s*Number:\s*["\'](\d+)["\']', content, flags=re.IGNORECASE)
            if match:
                return match.group(1)
            else:
                fallback_match = re.search(r'(\d{10,13})', content)
                if fallback_match:
                    return fallback_match.group(1)
        except Exception:
            pass
    return default_isbn

def process_xml_content(xml_content, isbn_num):
    # ==========================================
    # STEP 0: Insert Oxygen Schema PI above <book> tag
    # ==========================================
    if '<book' in xml_content and 'SCHSchema="Stukturerfassung-Lehrwerke-fuer-KI.sch"' not in xml_content:
        xml_content = re.sub(r'(<book\b)', r'<?oxygen SCHSchema="Stukturerfassung-Lehrwerke-fuer-KI.sch"?>\n\1', xml_content, count=1, flags=re.IGNORECASE)

    # ==========================================
    # STEP 0.1: Remove leading zeros in <title-group id="pg007"> -> <title-group id="pg7">
    # ==========================================
    def fix_title_group_id(match):
        prefix = match.group(1)
        num_str = match.group(2)
        suffix = match.group(3)
        cleaned_num = str(int(num_str))
        return f"{prefix}{cleaned_num}{suffix}"

    pattern_title_group_id = r'(<title-group\b[^>]*\bid=["\']pg)0+(\d+)(["\'])'
    xml_content = re.sub(pattern_title_group_id, fix_title_group_id, xml_content, flags=re.IGNORECASE)

    # ==========================================
    # STEP 1: HEAD1 TO <book-part> CONVERSION & PAGESTART SHIFT BELOW </book-part>
    # ==========================================
    active_pg_head1 = ["1"]
    ch_counter = [0]

    head1_page_pattern = r'(<\?pageStart\b[^>]*\bpagination=["\'](\d+)["\'][^>]*\?>|<pageStart\b[^>]*\bpagination=["\'](\d+)["\'][^>]*/>)|(<head1\b[^>]*>(.*?)</head1>)'

    def replace_head1_structures(m):
        if m.group(1):
            p_val = m.group(2) if m.group(2) else m.group(3)
            active_pg_head1[0] = str(int(p_val))
            return m.group(0)
        elif m.group(4):
            head_content = m.group(5)
            clean_title = head_content.replace("<bold>", "").replace("</bold>", "").replace("<bold/>", "").strip()
            
            ch_id = f"ch{ch_counter[0]}"
            ch_counter[0] += 1
            pg_id = f"pg{active_pg_head1[0]}"
            
            prefix_close = "</body>\n</book-part>\n" if ch_counter[0] > 1 else ""
            
            book_part_markup = (
                f'{prefix_close}'
                f'<book-part book-part-type="mod-Lerneinheit" id="{ch_id}">\n'
                f'<book-part-meta>\n'
                f'<book-part-id book-part-id-type="pu-node-id"></book-part-id>\n'
                f'<title-group id="{pg_id}">\n'
                f'<label></label>\n'
                f'<title>{clean_title}</title>\n'
                f'</title-group>\n'
                f'</book-part-meta>\n'
                f'<body>'
            )
            return book_part_markup

        return m.group(0)

    xml_content = re.sub(head1_page_pattern, replace_head1_structures, xml_content, flags=re.DOTALL | re.IGNORECASE)

    if ch_counter[0] > 0:
        if '</book>' in xml_content:
            xml_content = re.sub(r'(\s*</book>)', r'\n</body>\n</book-part>\1', xml_content, count=1, flags=re.IGNORECASE)
        elif '</html>' in xml_content:
            xml_content = re.sub(r'(\s*</html>)', r'\n</body>\n</book-part>\1', xml_content, count=1, flags=re.IGNORECASE)
        else:
            xml_content += "\n</body>\n</book-part>"

    pattern_pagestart_above_body = r'((?:<\?pageStart\b[^>]*\?>|<pageStart\b[^>]*/>))\s*</body>\s*</book-part>'
    xml_content = re.sub(pattern_pagestart_above_body, r'</body>\n</book-part>\n\1', xml_content, flags=re.IGNORECASE)

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
    # STEP 2.5: BOXED-TEXT TO <sec id="pgXXX_sYYY"> CONVERSION
    # ==========================================
    active_pg = ["000"]
    s_counter = [1]

    boxed_pattern = r'(<\?pageStart\b[^>]*\bpagination=["\'](\d+)["\'][^>]*\?>|<pageStart\b[^>]*\bpagination=["\'](\d+)["\'][^>]*/>)|(<boxed-text\b[^>]*>(.*?)</boxed-text>)'

    def process_boxed_text(match):
        if match.group(1):
            p_val = match.group(2) if match.group(2) else match.group(3)
            active_pg[0] = f"{int(p_val):03d}"
            s_counter[0] = 1
            return match.group(0)
        elif match.group(4):
            inner_content = match.group(5).strip()
            
            # Clean orphan </statement> inside boxed-text structure if any
            inner_content = re.sub(r'\s*</statement>\s*', '', inner_content, flags=re.IGNORECASE)
            
            sec_id = f"pg{active_pg[0]}_s{s_counter[0]:03d}"
            s_counter[0] += 1
            
            p_match = re.search(r'<p\b[^>]*>(.*?)</p>', inner_content, flags=re.DOTALL | re.IGNORECASE)
            
            label_text = ""
            if p_match:
                first_p_full = p_match.group(0)
                first_p_inner = p_match.group(1).strip()
                
                bold_match = re.search(r'^\s*<(?:bold\b[^>]*>(?:\s*<italic\b[^>]*>)?|<italic\b[^>]*>\s*<bold\b[^>]*>)(.*?)(?:</italic>\s*)?</bold>(?:</italic>)?', first_p_inner, flags=re.DOTALL | re.IGNORECASE)
                
                if bold_match:
                    raw_label_text = bold_match.group(1).strip()
                    label_text = re.sub(r'<[^>]+>', '', raw_label_text)
                    remaining_p_inner = first_p_inner[bold_match.end():].strip()
                    
                    if remaining_p_inner:
                        updated_first_p = f"<p>{remaining_p_inner}</p>"
                        inner_content = inner_content.replace(first_p_full, updated_first_p, 1)
                    else:
                        inner_content = inner_content.replace(first_p_full, '', 1).strip()

            label_element = f"<label>{label_text}</label>\n" if label_text else ""
            return f'<sec id="{sec_id}">\n{label_element}{inner_content}\n</sec>'
            
        return match.group(0)

    xml_content = re.sub(boxed_pattern, process_boxed_text, xml_content, flags=re.DOTALL | re.IGNORECASE)

    # ==========================================
    # STEP 3: Dynamic Page Track & Image Conversion
    # ==========================================
    fx_counter = [1]
    current_page = ["001"]

    combined_pattern = r'(<\?pageStart\b[^>]*\bpagination=["\'](\d+)["\'][^>]*\?>|<pageStart\b[^>]*\bpagination=["\'](\d+)["\'][^>]*/>)|(<p>\s*<fig>\s*<img\s*/>\s*</fig>\s*</p>)|(<fig>\s*<img\s*/>\s*</fig>)|(<img\s*/?>)|(<graphic\b[^>]*\bxlink:href=["\'][^"\']*["\'][^>]*/>)'

    def replacer(match):
        if match.group(1):
            page_num_val = match.group(2) if match.group(2) else match.group(3)
            current_page[0] = f"{int(page_num_val):03d}"
            fx_counter[0] = 1
            return match.group(0)
            
        elif match.group(4):
            fx_str = f"fx_{fx_counter[0]:03d}"
            fx_counter[0] += 1
            pg_str = f"pg_{current_page[0]}"
            return f'<graphic xmlns:xlink="http://www.w3.org/1999/xlink" xlink:href="img/{isbn_num}_{pg_str}_{fx_str}.jpg"/>'
            
        elif match.group(5):
            fx_str = f"fx_{fx_counter[0]:03d}"
            fx_counter[0] += 1
            pg_str = f"pg_{current_page[0]}"
            return f'<p><graphic xmlns:xlink="http://www.w3.org/1999/xlink" xlink:href="img/{isbn_num}_{pg_str}_{fx_str}.jpg"/></p>'
            
        elif match.group(6):
            fx_str = f"fx_{fx_counter[0]:03d}"
            fx_counter[0] += 1
            pg_str = f"pg_{current_page[0]}"
            return f'<graphic xmlns:xlink="http://www.w3.org/1999/xlink" xlink:href="img/{isbn_num}_{pg_str}_{fx_str}.jpg"/>'

        elif match.group(7):
            fx_str = f"fx_{fx_counter[0]:03d}"
            fx_counter[0] += 1
            pg_str = f"pg_{current_page[0]}"
            return f'<graphic xmlns:xlink="http://www.w3.org/1999/xlink" xlink:href="img/{isbn_num}_{pg_str}_{fx_str}.jpg"/>'

        return match.group(0)

    xml_content = re.sub(combined_pattern, replacer, xml_content, flags=re.IGNORECASE)

    # ==========================================
    # STEP 3.1: GLOBAL REPLACE - Residual 000000000000 ISBN
    # ==========================================
    pattern_global_zeros = r'(xlink:href=["\']img/)000000000000(_)'
    xml_content = re.sub(pattern_global_zeros, rf'\g<1>{isbn_num}\g<2>', xml_content, flags=re.IGNORECASE)

    # ==========================================
    # STEP 3.2: DYNAMIC SECTION PAGE ID FIX
    # ==========================================
    current_pg_id = ["001"]
    sec_page_pattern = r'(<\?pageStart\b[^>]*\bpagination=["\'](\d+)["\'][^>]*\?>|<pageStart\b[^>]*\bpagination=["\'](\d+)["\'][^>]*/>)|(<sec\b[^>]*\bid=["\']pg)\d+(_task[^"\']*["\'][^>]*>)'

    def sec_page_replacer(m):
        if m.group(1):
            p_val = m.group(2) if m.group(2) else m.group(3)
            current_pg_id[0] = f"{int(p_val):03d}"
            return m.group(0)
        elif m.group(4):
            return f"{m.group(4)}{current_pg_id[0]}{m.group(5)}"
        return m.group(0)

    xml_content = re.sub(sec_page_pattern, sec_page_replacer, xml_content, flags=re.IGNORECASE)

    # ==========================================
    # STEP 3.3: PULL ORPHAN GRAPHICS INSIDE PRECEDING SUBTASK <sec>
    # ==========================================
    orphan_graphic_subtask_pattern = r'(<sec\b[^>]*sec-type=["\']subtask["\'][^>]*>[\s\S]*?)</sec>\s*(<p>\s*<graphic\b[^>]*/>\s*</p>|<graphic\b[^>]*/>)'
    while re.search(orphan_graphic_subtask_pattern, xml_content, flags=re.IGNORECASE):
        xml_content = re.sub(orphan_graphic_subtask_pattern, r'\1\n\2\n</sec>', xml_content, flags=re.IGNORECASE)

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
    # STEP 7: STRICT Punctuation check for <statement> tag in Subtasks
    # ==========================================
    def wrap_subtask_statement(match):
        sec_start = match.group(1)
        label_part = match.group(2)
        p_content = match.group(3)
        sec_end = match.group(4)

        inner_text = re.sub(r'^<p\b[^>]*>', '', p_content, flags=re.IGNORECASE)
        inner_text = re.sub(r'</p>$', '', inner_text, flags=re.IGNORECASE).strip()

        if re.search(r'[.;?:!]\s*$', inner_text):
            wrapped_p = f"<statement>\n{p_content}\n</statement>"
            return f"{sec_start}\n{label_part}\n{wrapped_p}\n{sec_end}"
        else:
            return f"{sec_start}\n{label_part}\n{p_content}\n{sec_end}"

    pattern_subtask = r'(<sec\b[^>]*sec-type=["\']subtask["\'][^>]*>)\s*(<label>.*?</label>)\s*(<p>.*?</p>)\s*(</sec>)'
    xml_content = re.sub(pattern_subtask, wrap_subtask_statement, xml_content, flags=re.DOTALL | re.IGNORECASE)

    # ==========================================
    # STEP 7.5: SAFE TASK-LEVEL STATEMENT WRAPPING (With Unmatched Closing Clean-Up)
    # ==========================================
    def fix_task_level_statement(task_match):
        task_sec_open = task_match.group(1)
        label_tag = task_match.group(2)
        rest_content = task_match.group(3)
        task_sec_close = task_match.group(4)

        subtask_pos = re.search(r'<sec\b[^>]*sec-type=["\']subtask["\']', rest_content, flags=re.IGNORECASE)
        
        if subtask_pos:
            before_subtasks = rest_content[:subtask_pos.start()]
            subtasks_and_after = rest_content[subtask_pos.start():]
        else:
            before_subtasks = rest_content
            subtasks_and_after = ""

        clean_before = re.sub(r'</?statement>', '', before_subtasks, flags=re.IGNORECASE).strip()
        
        if clean_before:
            wrapped_statement = f"\n<statement>\n{clean_before}\n</statement>\n"
        else:
            wrapped_statement = "\n"

        return f"{task_sec_open}\n{label_tag}{wrapped_statement}{subtasks_and_after}{task_sec_close}"

    pattern_full_task = r'(<sec\b[^>]*sec-type=["\']task["\'][^>]*>)\s*(<label>.*?</label>)(.*?)(</sec>)'
    xml_content = re.sub(pattern_full_task, fix_task_level_statement, xml_content, flags=re.DOTALL | re.IGNORECASE)

    # Clean orphaned closing </statement> tags outside tasks/subtasks
    xml_content = re.sub(r'</sec>\s*</statement>', r'</sec>', xml_content, flags=re.IGNORECASE)

    while re.search(orphan_graphic_subtask_pattern, xml_content, flags=re.IGNORECASE):
        xml_content = re.sub(orphan_graphic_subtask_pattern, r'\1\n\2\n</sec>', xml_content, flags=re.IGNORECASE)

    # ==========================================
    # STEP 8: ACCURATE Subtask ID Replacement for ALL Children
    # ==========================================
    def fix_subtask_ids_across_file(content):
        parts = re.split(r'(<sec\b[^>]*sec-type=["\']task["\'][^>]*>)', content, flags=re.IGNORECASE)
        new_content = [parts[0]]
        
        for i in range(1, len(parts), 2):
            task_header = parts[i]
            task_body = parts[i+1] if (i+1) < len(parts) else ""
            
            label_match = re.search(r'<label>\s*(\d+)\s*</label>', task_body, flags=re.IGNORECASE)
            if label_match:
                task_num_raw = label_match.group(1)
                formatted_task_num = f"{int(task_num_raw):03d}"
                
                def subtask_id_replacer(m):
                    prefix = m.group(1)
                    sub_letter = m.group(2)
                    quote = m.group(3)
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
    # STEP 9: Remove orphan </fig> inside <p>...</p>
    # ==========================================
    def remove_orphan_fig_close(match):
        p_block = match.group(0)
        if not re.search(r'<fig\b', p_block, flags=re.IGNORECASE):
            return re.sub(r'</fig>', '', p_block, flags=re.IGNORECASE)
        return p_block

    pattern_p_block = r'<p\b[^>]*>.*?</p>'
    xml_content = re.sub(pattern_p_block, remove_orphan_fig_close, xml_content, flags=re.DOTALL | re.IGNORECASE)

    # ==========================================
    # STEP 10: WRAP <p><bold>Tipp</bold>...</p> IN <sec id="pgXXX_sYYY">
    # ==========================================
    tipp_page = ["000"]
    tipp_sec_counter = [1]

    pattern_tipp_track = r'(<\?pageStart\b[^>]*\bpagination=["\'](\d+)["\'][^>]*\?>|<pageStart\b[^>]*\bpagination=["\'](\d+)["\'][^>]*/>|<sec\b[^>]*id=["\']pg(\d+)_task)|(<p\b[^>]*>\s*<bold>\s*Tipp:?\s*</bold>.*?</p>)'

    def tipp_replacer(m):
        if m.group(1):
            if m.group(2):
                p_num = m.group(2)
            elif m.group(3):
                p_num = m.group(3)
            else:
                p_num = m.group(4)
            
            p_formatted = f"{int(p_num):03d}"
            if tipp_page[0] != p_formatted:
                tipp_page[0] = p_formatted
                tipp_sec_counter[0] = 1
            return m.group(0)

        elif m.group(5):
            tipp_p = m.group(5)
            sec_id = f"pg{tipp_page[0]}_s{tipp_sec_counter[0]:03d}"
            tipp_sec_counter[0] += 1
            return f'<sec id="{sec_id}">\n{tipp_p}\n</sec>'

        return m.group(0)

    xml_content = re.sub(pattern_tipp_track, tipp_replacer, xml_content, flags=re.DOTALL | re.IGNORECASE)

    return xml_content

def process_xml_files():
    print("========================================")
    print("      XML Processing Tool Running...    ")
    print("========================================\n")

    if not check_expiry():
        input("\nPress ENTER to exit...")
        return

    if not os.path.exists(input_folder):
        print(f"Error: '{input_folder}' folder illa! First 'input' folder create pannungga.")
        input("\nPress ENTER to exit...")
        return

    if not os.path.exists(output_folder):
        os.makedirs(output_folder)

    isbn_num = get_isbn_number()
    print(f"Loaded ISBN Number: {isbn_num}\n")

    files = [f for f in os.listdir(input_folder) if f.endswith('.xml')]
    
    if not files:
        print(f"'{input_folder}' folder-la XML files edhum illa!")
        input("\nPress ENTER to exit...")
        return

    for file_name in files:
        print(f"File processing: {file_name} ...")
        input_path = os.path.join(input_folder, file_name)
        output_path = os.path.join(output_folder, file_name)

        try:
            content = read_file_safely(input_path)
            updated_content = process_xml_content(content, isbn_num)

            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(updated_content)

            print(f"File run complete: Saved to '{output_folder}/{file_name}'\n")
        except Exception as e:
            print(f"Error in processing {file_name}: {e}\n")

    print("========================================")
    print("     ALL FILES PROCESSED SUCCESSFULLY!  ")
    print("========================================")
    
    input("\nPress ENTER to exit...")

if __name__ == "__main__":
    process_xml_files()