import os
import re
from datetime import datetime

# ==========================================
# STEP 1: FOLDER CONFIGURATION & SETUP
# Input & Output folder-a create panrom
# ==========================================
INPUT_DIR = "input"
OUTPUT_DIR = "output"

os.makedirs(OUTPUT_DIR, exist_ok=True)


# ==========================================
# STEP 2: REGEX PATTERNS DEFINITION
# Constant patterns ellam inge define panrom
# ==========================================

# Regex 1: Subtask list patterns match panna (e.g., a), b), 1., 2))
P_TAG_RE = re.compile(
    r"(?<!<td>)\s*<p(?P<attrs>[^>]*)>\s*(?P<label>[a-zA-Z0-9]{1,3}[\.\)])\s*(?P<content>.*?)</p>",
    re.DOTALL | re.IGNORECASE,
)

# Regex 2: Page numbers track panna <?pageStart ... pagination="24"?> match panna
PAGE_RE = re.compile(r'<\?pageStart\b[^>]*pagination=["\'](\d+)["\'][^>]*\?>')

# Regex 3: Paragraph-kulla irukkura inner <fig> or <img> tags match panna
FIG_RE = re.compile(r"<fig\b[^>]*>.*?</fig>|<img\b[^>]*/?>", re.DOTALL | re.IGNORECASE)

# Regex 4: Separate-a standalone-a irukkura full <fig> or <img> tags match panna
STANDALONE_FIG_RE = re.compile(
    r"<fig\b[^>]*>.*?</fig>|<img\b[^>]*/?>", re.DOTALL | re.IGNORECASE
)

# Regex 5: Page number & task refs match panna (e.g., Seite 24, S. 24, Nr. 1)
SEITE_RE = re.compile(
    r"\b((?:Seite|S\.)\s+(\d+)(?:,?\s+Nr\.\s+([\d\s,]+(?:\.\s*)?))?)",
    re.IGNORECASE,
)

# Regex 6: &#x25B8; vaitchu varra NextLevel task links match panna
NEXTLEVEL_RE = re.compile(r"&#x25B8;\s*(\d+)", re.IGNORECASE)

# Regex 7: Unwanted <sec-meta> tags clean/remove panna
SEC_META_RE = re.compile(r"<sec-meta>.*?</sec-meta>", re.IGNORECASE | re.DOTALL)

# Regex 8: Table-kulla irukkura empty <p></p> tags remove panna
EMPTY_TD_P_RE = re.compile(
    r"(<td\b[^>]*>)\s*<p(?:\s+[^>]*)?>\s*</p>\s*(</td>)",
    re.IGNORECASE | re.DOTALL,
)

# Regex 9: Circled numbers match panna (e.g., &#x2460; = ①)
CIRCLED_P_RE = re.compile(
    r"<p(?P<attrs>[^>]*)>\s*(?P<entity>&#x24[67][0-9a-fA-F];)\s*(?P<content>.*?)</p>",
    re.DOTALL | re.IGNORECASE,
)

# Regex 10: Solution link pattern (Lösungen / L&#x00F6;sungen ab S. XXX)
SOLUTION_LINK_RE = re.compile(
    r"(?:<italic>)?\s*(L(?:&#x00F6;|ö)sungen\s+ab\s+(?:Seite|S\.)\s+(\d+))\s*(?:</italic>)?",
    re.IGNORECASE,
)

# Regex 11: Blank space mattum irukkura empty <p> tags remove panna
EMPTY_OR_SPACE_P_RE = re.compile(
    r"<p(?:\s+[^>]*)?>\s*(?:&#x00A0;|&nbsp;|&#160;|\s)*\s*</p>",
    re.IGNORECASE | re.DOTALL,
)


# ==========================================
# STEP 3: CONVERT SOLUTION LINKS
# 'Lösungen ab S. 218' aa solution <xref> link-a maatha
# ==========================================
def process_solution_links(text):
    """Transforms 'L&#x00F6;sungen ab S. 218' inside <italic> into <italic><xref ref-type="link-toSolution" rid="pg218">...</xref></italic>."""

    def replace_solution(match):
        full_text = match.group(1)
        page_num = int(match.group(2))
        rid_val = f"pg{page_num}"

        return f'<italic><xref ref-type="link-toSolution" rid="{rid_val}">{full_text}</xref></italic>'

    return SOLUTION_LINK_RE.sub(replace_solution, text)


# ==========================================
# STEP 4: CONVERT PAGE & LOOK-IT-UP LINKS
# 'Seite 24', 'S. 24 Nr. 1' aa LookItUp <xref> link-a maatha
# ==========================================
def process_seite_links(text):
    """Transforms 'Seite 24' into <xref ref-type="link-LookItUp" rid="pg24">Seite 24</xref> without leading zeroes in rid."""

    def replace_seite(match):
        full_match = match.group(1)
        prefix_str = "S." if "S." in full_match else "Seite"
        page_num = int(match.group(2))
        page_str = str(page_num)
        nums_part = match.group(3)

        if not nums_part:
            rid_val = f"pg{page_str}"
            return f'<xref ref-type="link-LookItUp" rid="{rid_val}">{full_match.strip()}</xref>'

        has_trailing_dot = nums_part.rstrip().endswith(".")

        trailing_spaces_count = len(nums_part) - len(nums_part.rstrip())
        trailing_spaces = " " * trailing_spaces_count

        nums_part_clean = nums_part.rstrip(". ")
        raw_nums = [n.strip() for n in nums_part_clean.split(",") if n.strip()]

        if not raw_nums:
            rid_val = f"pg{page_str}"
            return f'<xref ref-type="link-LookItUp" rid="{rid_val}">{full_match.strip()}</xref>'

        xref_list = []
        for idx, num_str in enumerate(raw_nums):
            num_val = int(num_str)
            task_str = f"{num_val:03d}"
            rid_val = f"pg{page_str}_task{task_str}"

            if idx == 0:
                sep = ", " if prefix_str == "S." else " "
                text_content = f"{prefix_str} {page_num}{sep}Nr. {num_str}"
            else:
                text_content = num_str

            xref_tag = (
                f'<xref ref-type="link-LookItUp" rid="{rid_val}">{text_content}</xref>'
            )
            xref_list.append(xref_tag)

        res = ", ".join(xref_list)
        if has_trailing_dot:
            res += "."

        return res + trailing_spaces

    return SEITE_RE.sub(replace_seite, text)


# ==========================================
# STEP 5: CONVERT NEXTLEVEL TASK REFERENCES
# '&#x25B8;12' symbols-a nextlevel_task <xref> link-a maatha
# ==========================================
def process_nextlevel_tasks(text, current_page_fn, pos_offset=0):
    """Transforms '&#x25B8;12' into standard <xref> format."""

    def replace_nextlevel(match):
        start_pos = pos_offset + match.start()
        pg_str = current_page_fn(start_pos)

        task_num = int(match.group(1))
        task_str = f"{task_num:03d}"

        rid_val = f"pg{pg_str}_task{task_str}"

        return f'&#x25B8; <xref ref-type="nextlevel_task" rid="{rid_val}">{task_num}</xref>'

    text = NEXTLEVEL_RE.sub(replace_nextlevel, text)
    return text


# ==========================================
# STEP 6: CONVERT KOMPETENZ SECTIONS
# Kompetenz / Lernziel sections-a auto ID potu <sec> maatha
# ==========================================
def process_kompetenz_sections(content, get_page_for_pos, sec_counter):
    """Transforms Kompetenz <sec> blocks resetting section IDs per page starting from s001."""

    kompetenz_re = re.compile(
        r"<sec\b[^>]*>\s*<label>\s*(\d+[^<]*)</label>\s*<p(?P<pattrs>[^>]*)>(?P<pcontent>.*?)</p>\s*</sec>",
        re.DOTALL | re.IGNORECASE,
    )

    matches = list(kompetenz_re.finditer(content))
    if not matches:
        return content

    def get_sec_id(pg_str):
        if pg_str not in sec_counter:
            sec_counter[pg_str] = 1
        else:
            sec_counter[pg_str] += 1
        return f"pg{pg_str}_s{sec_counter[pg_str]:03d}"

    new_content = []
    last_idx = 0
    in_kompetenz_group = False
    current_group_page = None

    for i, m in enumerate(matches):
        start_pos = m.start()
        pg_str = get_page_for_pos(start_pos)

        lbl_content = m.group(1).strip()
        p_content = m.group("pcontent").strip()

        if in_kompetenz_group and current_group_page != pg_str:
            new_content.append("\n</sec>")
            in_kompetenz_group = False

        outer_id = get_sec_id(pg_str) if not in_kompetenz_group else None
        inner_id = get_sec_id(pg_str)

        new_content.append(content[last_idx : m.start()])

        block_out = ""
        if not in_kompetenz_group:
            block_out += f'<sec id="{outer_id}">\n'
            in_kompetenz_group = True
            current_group_page = pg_str

        block_out += (
            f'<sec id="{inner_id}">\n'
            f"<label>{lbl_content}</label>\n"
            f'<p specific-use="mer-Lernziel">{p_content}</p>\n'
            f"</sec>"
        )

        is_next_kompetenz = False
        if i + 1 < len(matches):
            next_pg = get_page_for_pos(matches[i + 1].start())
            between_text = content[m.end() : matches[i + 1].start()].strip()
            if not between_text and next_pg == pg_str:
                is_next_kompetenz = True

        if not is_next_kompetenz:
            block_out += "\n</sec>"
            in_kompetenz_group = False
            current_group_page = None

        new_content.append(block_out)
        last_idx = m.end()

    new_content.append(content[last_idx:])
    return "".join(new_content)
# ==========================================
# STEP 6.1: CONVERT 'Lies und übe:' SECTIONS
# <sec><label>Lies und &#x00FC;be:</label>...-kku auto ID (pgXXX_sYYY) sethu convert panna
# ==========================================
def process_lies_und_uebe_sections(content, get_page_for_pos, sec_counter):
    """Adds id="pgXXX_sYYY" to <sec> blocks containing <label>Lies und &#x00FC;be:</label>."""

    lies_sec_re = re.compile(
        r"<sec(?P<attrs>[^>]*)>\s*<label>(?P<label_content>\s*Lies\s+und\s+(?:&#x00FC;|ü)be:?\s*)</label>",
        re.DOTALL | re.IGNORECASE,
    )

    def get_sec_id(pg_str):
        if pg_str not in sec_counter:
            sec_counter[pg_str] = 1
        else:
            sec_counter[pg_str] += 1
        return f"pg{pg_str}_s{sec_counter[pg_str]:03d}"

    def replace_lies_sec(match):
        start_pos = match.start()
        pg_str = get_page_for_pos(start_pos)
        sec_id = get_sec_id(pg_str)
        lbl_content = match.group("label_content")

        return f'\n<sec id="{sec_id}">\n<label>{lbl_content}</label>'

    return lies_sec_re.sub(replace_lies_sec, content)

# ==========================================
# STEP 7: CONVERT MAIN TASKS
# Main Tasks (Task 1, Task 2...) sec-type="task" -a maatha
# ==========================================
def process_task_sections(content, get_page_for_pos):
    """Parses task <sec> blocks AND standalone <p><bold>N ...</bold>...</p> tags into task <sec> format."""

    TASK_P_RE = re.compile(
        r"<p(?P<pattrs>[^>]*)>\s*<bold>(?:Task\s*)?(?P<num>\d+)[\.:]?(?P<bold_tail>.*?)</bold>\s*(?P<pcontent>.*?)</p>",
        re.DOTALL | re.IGNORECASE,
    )

    # 7.1 Text-kulla already irukkura <sec> block task-a convert panna
    sec_block_re = re.compile(r"<sec\b[^>]*>(.*?)</sec>", re.DOTALL | re.IGNORECASE)

    def transform_sec(match):
        start_pos = match.start()
        pg_str = get_page_for_pos(start_pos)
        sec_inner = match.group(1)

        if 'specific-use="mer-Lernziel"' in sec_inner or 'sec-type="task"' in match.group(0):
            return match.group(0)

        first_p_match = TASK_P_RE.search(sec_inner)
        if not first_p_match:
            return match.group(0)

        task_num = int(first_p_match.group("num"))
        task_str = f"{task_num:03d}"
        sec_id = f"pg{pg_str}_task{task_str}"

        p_attrs = first_p_match.group("pattrs")
        bold_tail = first_p_match.group("bold_tail").strip()
        p_content = first_p_match.group("pcontent").strip()

        full_title_text = f"{bold_tail} {p_content}".strip()

        clean_inner = re.sub(
            r"^\s*<label>[^<]*</label>\s*", "", sec_inner, flags=re.IGNORECASE
        )

        first_p_full = first_p_match.group(0)
        new_first_p = f"<p{p_attrs}>{full_title_text}</p>" if full_title_text else ""

        clean_inner = clean_inner.replace(first_p_full, new_first_p, 1)

        subtask_split = re.split(
            r"(?=(?<!<td>)\s*<p\b[^>]*>\s*[a-zA-Z0-9]{1,3}[\.\)])",
            clean_inner,
            maxsplit=1,
            flags=re.IGNORECASE,
        )

        statement_part = subtask_split[0].strip()
        remaining_part = subtask_split[1].strip() if len(subtask_split) > 1 else ""

        res = (
            f'\n<sec sec-type="task" id="{sec_id}">\n'
            f"<label>{task_num}</label>\n"
            f"<statement>\n{statement_part}\n</statement>\n"
        )
        if remaining_part:
            res += f"{remaining_part}\n"
        res += "</sec>"

        return res

    content = sec_block_re.sub(transform_sec, content)

    # 7.2 Standalone <p><bold>N ...</bold>...</p> ah irukkura Tasks-a convert panna
    matches = list(TASK_P_RE.finditer(content))
    if not matches:
        return content

    new_content = []
    last_idx = 0

    for i, m in enumerate(matches):
        start_pos = m.start()

        prev_text = content[:start_pos]
        open_secs = len(re.findall(r"<sec\b", prev_text, re.IGNORECASE))
        close_secs = len(re.findall(r"</sec>", prev_text, re.IGNORECASE))
        if open_secs > close_secs:
            continue

        pg_str = get_page_for_pos(start_pos)
        task_num = int(m.group("num"))
        task_str = f"{task_num:03d}"
        sec_id = f"pg{pg_str}_task{task_str}"

        p_attrs = m.group("pattrs")
        bold_tail = m.group("bold_tail").strip()
        p_content = m.group("pcontent").strip()

        full_title_text = f"{bold_tail} {p_content}".strip()
        first_statement_p = f"<p{p_attrs}>{full_title_text}</p>" if full_title_text else ""

        new_content.append(content[last_idx:start_pos])

        next_pos = matches[i + 1].start() if i + 1 < len(matches) else len(content)
        following_content = content[m.end() : next_pos]

        subtask_split = re.split(
            r"(?=(?<!<td>)\s*<p\b[^>]*>\s*[a-zA-Z0-9]{1,3}[\.\)])",
            following_content,
            maxsplit=1,
            flags=re.IGNORECASE,
        )

        statement_tail = subtask_split[0].strip()
        subtask_part = subtask_split[1].strip() if len(subtask_split) > 1 else ""

        full_statement = f"{first_statement_p}\n{statement_tail}".strip()

        res = (
            f'\n<sec sec-type="task" id="{sec_id}">\n'
            f"<label>{task_num}</label>\n"
            f"<statement>\n{full_statement}\n</statement>\n"
        )
        if subtask_part:
            res += f"{subtask_part}\n"
        res += "</sec>"

        last_idx = next_pos
        new_content.append(res)

    if last_idx < len(content):
        new_content.append(content[last_idx:])

    return "".join(new_content)

# ==========================================
# STEP 8: CONVERT BOOK PARTS & HEADINGS
# Headings & Specific Words-a <book-part> structure-a convert panna
# ==========================================
def process_book_parts(content, get_page_for_pos):
    """Processes <head1>+<head2> text-only, <head1>+<head1>, <head1>+<head2>,
    standalone <head2>, and specific keywords into <book-part> wrappers."""

    # 8.0a Page start + <head1> (Text) + <head2> (Title) -> Nested book-part
    head1_text_head2_re = re.compile(
        r'(<\?pageStart\b[^>]*pagination=["\'](\d+)["\'][^>]*\?>)\s*'
        r'<head1>(?:<bold>)?([^\d<][^<]*?)(?:</bold>)?</head1>\s*'
        r'<head2>(?:<bold>)?(.*?)(?:</bold>)?</head2>',
        re.DOTALL | re.IGNORECASE,
    )

    def replace_head1_text_head2(match):
        page_start_tag = match.group(1)
        pg_num = int(match.group(2))
        pg_str = str(pg_num)

        head1_label_text = match.group(3).strip()
        head2_title_text = match.group(4).strip()

        book_part_structure = (
            f"{page_start_tag}\n"
            f'<book-part book-part-type="mod-Lerneinheit">\n'
            f"<book-part-meta>\n"
            f'<book-part-id book-part-id-type="pu-node-id"></book-part-id>\n'
            f'<title-group id="pg{pg_str}">\n'
            f"<title>{head2_title_text}</title>\n"
            f"</title-group>\n"
            f"</book-part-meta>\n"
            f"<body>\n"
            f'<book-part book-part-type="mod-Lerneinheit">\n'
            f"<book-part-meta>\n"
            f'<book-part-id book-part-id-type="pu-node-id"></book-part-id>\n'
            f'<title-group id="pg{pg_str}">\n'
            f"<label>{head1_label_text}</label>\n"
            f"</title-group>\n"
            f"</book-part-meta>\n"
            f"<body>\n"
            f"</body>\n"
            f"</book-part>\n"
            f"</body>\n"
            f"</book-part>"
        )
        return book_part_structure

    content = head1_text_head2_re.sub(replace_head1_text_head2, content)

    # 8.0b Page start + <head1> (Number) + <head1> (Title) pattern
    head1_head1_re = re.compile(
        r'(<\?pageStart\b[^>]*pagination=["\'](\d+)["\'][^>]*\?>)\s*'
        r'<head1>(?:<bold>)?(\d+)(?:</bold>)?</head1>\s*'
        r'<head1>(?:<bold>)?(.*?)(?:</bold>)?</head1>',
        re.DOTALL | re.IGNORECASE,
    )

    def replace_head1_head1(match):
        page_start_tag = match.group(1)
        pg_num = int(match.group(2))
        pg_str = str(pg_num)

        ch_num = match.group(3).strip()
        title_text = match.group(4).strip()

        book_part_structure = (
            f"{page_start_tag}\n"
            f'<book-part book-part-type="mod-Lerneinheit" id="ch{ch_num}">\n'
            f"<book-part-meta>\n"
            f'<book-part-id book-part-id-type="pu-node-id"></book-part-id>\n'
            f'<title-group id="pg{pg_str}">\n'
            f"<label>{ch_num}</label>\n"
            f"<title>{title_text}</title>\n"
            f"</title-group>\n"
            f"</book-part-meta>\n"
            f"<body>\n"
            f"</body>\n"
            f"</book-part>"
        )
        return book_part_structure

    content = head1_head1_re.sub(replace_head1_head1, content)

    # 8.0c Page start + <head1> (Number) + <head2> (Title) pattern
    head1_head2_re = re.compile(
        r'(<\?pageStart\b[^>]*pagination=["\'](\d+)["\'][^>]*\?>)\s*'
        r'<head1>(?:<bold>)?(\d+)(?:</bold>)?</head1>\s*'
        r'<head2>(?:<bold>)?(.*?)(?:</bold>)?</head2>',
        re.DOTALL | re.IGNORECASE,
    )

    def replace_head1_head2(match):
        page_start_tag = match.group(1)
        pg_num = int(match.group(2))
        pg_str = str(pg_num)

        ch_num = match.group(3).strip()
        title_text = match.group(4).strip()

        book_part_structure = (
            f"{page_start_tag}\n"
            f'<book-part book-part-type="mod-Lerneinheit" id="ch{ch_num}">\n'
            f"<book-part-meta>\n"
            f'<book-part-id book-part-id-type="pu-node-id"></book-part-id>\n'
            f'<title-group id="pg{pg_str}">\n'
            f"<label>{ch_num}</label>\n"
            f"<title>{title_text}</title>\n"
            f"</title-group>\n"
            f"</book-part-meta>\n"
            f"<body>\n"
            f"</body>\n"
            f"</book-part>"
        )
        return book_part_structure

    content = head1_head2_re.sub(replace_head1_head2, content)

    # 8.1 Page start apparam varra standalone <head2> (With Page Start Tag)
    book_part_re = re.compile(
        r'(<\?pageStart\b[^>]*pagination=["\'](\d+)["\'][^>]*\?>)\s*'
        r'<head2>(?:<bold>)?(.*?)(?:</bold>)?</head2>'
        r'(?:\s*<head2>(?:<bold>)?(.*?)(?:</bold>)?</head2>)?',
        re.DOTALL | re.IGNORECASE,
    )

    def replace_book_part(match):
        page_start_tag = match.group(1)
        pg_num = int(match.group(2))
        pg_str = str(pg_num)

        first_head = match.group(3).strip()
        second_head = match.group(4)

        if second_head is not None:
            second_head = second_head.strip()
            title_group_inner = (
                f"<label>{first_head}</label>\n" f"<title>{second_head}</title>"
            )
        else:
            title_group_inner = f"<title>{first_head}</title>"

        book_part_structure = (
            f"{page_start_tag}\n"
            f'<book-part book-part-type="mod-Lerneinheit">\n'
            f"<book-part-meta>\n"
            f'<title-group id="pg{pg_str}">\n'
            f"{title_group_inner}\n"
            f"</title-group>\n"
            f'<related-object content-type=""/>\n'
            f"</book-part-meta>\n"
            f"<body>\n"
            f"</body>\n"
            f"</book-part>"
        )
        return book_part_structure

    content = book_part_re.sub(replace_book_part, content)

    # 8.2 Page start illamal thaniya varra <head2> (Standalone <head2>)
    standalone_head2_re = re.compile(
        r'<head2>(?:<bold>)?(.*?)(?:</bold>)?</head2>'
        r'(?:\s*<head2>(?:<bold>)?(.*?)(?:</bold>)?</head2>)?',
        re.DOTALL | re.IGNORECASE,
    )

    def replace_standalone_head2(match):
        start_pos = match.start()
        pg_str = get_page_for_pos(start_pos)

        first_head = match.group(1).strip()
        second_head = match.group(2)

        if second_head is not None:
            second_head = second_head.strip()
            title_group_inner = (
                f"<label>{first_head}</label>\n" f"<title>{second_head}</title>"
            )
        else:
            title_group_inner = f"<title>{first_head}</title>"

        book_part_structure = (
            f'<book-part book-part-type="mod-Lerneinheit">\n'
            f"<book-part-meta>\n"
            f'<title-group id="pg{pg_str}">\n'
            f"{title_group_inner}\n"
            f"</title-group>\n"
            f'<related-object content-type=""/>\n'
            f"</book-part-meta>\n"
            f"<body>\n"
            f"</body>\n"
            f"</book-part>"
        )
        return book_part_structure

    content = standalone_head2_re.sub(replace_standalone_head2, content)

    # 8.3 Specific Words (<p><bold>ENTDECKEN/VERSTEHEN/ANWENDEN</bold></p>) -> <book-part>
    words_book_part_re = re.compile(
        r'<p(?:\s+[^>]*)?>\s*(?:<bold>)?\s*(ENTDECKEN|VERSTEHEN|ANWENDEN)\s*(?:</bold>)?\s*</p>',
        re.IGNORECASE,
    )

    def replace_words_book_part(match):
        start_pos = match.start()
        pg_str = get_page_for_pos(start_pos)
        word = match.group(1).strip()

        book_part_structure = (
            f'<book-part book-part-type="mod-Lerneinheit">\n'
            f"<book-part-meta>\n"
            f'<title-group id="pg{pg_str}">\n'
            f"<title>{word}</title>\n"
            f"</title-group>\n"
            f'<related-object content-type=""/>\n'
            f"</book-part-meta>\n"
            f"<body>\n"
            f"</body>\n"
            f"</book-part>"
        )
        return book_part_structure

    content = words_book_part_re.sub(replace_words_book_part, content)

    return content

# ==========================================
# STEP 9: CONVERT CIRCLED NUMBER LISTS
# Circled number <p> tags-a <list> format-a maatha
# ==========================================
def process_circled_num_lists(
    content, get_page_for_pos, sec_counter, page_img_counters
):
    """Groups contiguous <p>&#x2460;...</p> elements into <sec id="pgXXX_sYYY"><list> blocks."""

    def get_next_sec_id(pg_str):
        if pg_str not in sec_counter:
            sec_counter[pg_str] = 1
        else:
            sec_counter[pg_str] += 1
        return f"pg{pg_str}_s{sec_counter[pg_str]:03d}"

    matches = list(CIRCLED_P_RE.finditer(content))
    if not matches:
        return content

    groups = []
    current_group = []

    for m in matches:
        if not current_group:
            current_group.append(m)
        else:
            prev = current_group[-1]
            between = content[prev.end() : m.start()].strip()
            if not between:
                current_group.append(m)
            else:
                groups.append(current_group)
                current_group = [m]

    if current_group:
        groups.append(current_group)

    new_content = []
    last_idx = 0

    for grp in groups:
        first_m = grp[0]
        last_m = grp[-1]

        start_pos = first_m.start()
        pg_str = get_page_for_pos(start_pos)
        sec_id = get_next_sec_id(pg_str)

        new_content.append(content[last_idx:start_pos])

        items_str = []
        for m in grp:
            attrs = m.group("attrs")
            entity = m.group("entity")
            p_content = m.group("content").strip()

            if FIG_RE.search(p_content):
                if pg_str not in page_img_counters:
                    page_img_counters[pg_str] = 1
                else:
                    page_img_counters[pg_str] += 1

                img_seq = page_img_counters[pg_str]
                img_seq_str = f"{img_seq:03d}"
                href_val = f"img/000000000000_pg_{pg_str}_fx_{img_seq_str}.jpg"

                graphic_tag = f'<graphic xmlns:xlink="http://www.w3.org/1999/xlink" xlink:href="{href_val}"/>'
                p_content = FIG_RE.sub(graphic_tag, p_content)

            items_str.append(
                f"<list-item><p{attrs}>{entity} {p_content}</p></list-item>"
            )

        items_joined = "\n".join(items_str)
        list_block = (
            f'\n<sec id="{sec_id}">\n'
            f'<list list-type="simple">\n'
            f"{items_joined}\n"
            f"</list>\n"
            f"</sec>"
        )

        new_content.append(list_block)
        last_idx = last_m.end()

    new_content.append(content[last_idx:])
    return "".join(new_content)


# ==========================================
# STEP 10: CONVERT TASK STATEMENT IMAGES
# Task <statement> kulla irukkura images-a <graphic> tag-a maatha
# ==========================================
def process_task_statement_images(content, get_page_for_pos, page_img_counters):
    """Converts <fig><img.../></fig> inside/after task <statement> into <p><graphic .../></p>."""
    task_sec_re = re.compile(
        r'(<sec\b[^>]*sec-type="task"[^>]*>.*?</statement>\s*)(<fig\b[^>]*>.*?</fig>|<img\b[^>]*/?>)',
        re.DOTALL | re.IGNORECASE,
    )

    def replace_task_img(match):
        prefix = match.group(1)
        start_pos = match.start()
        pg_str = get_page_for_pos(start_pos)

        if pg_str not in page_img_counters:
            page_img_counters[pg_str] = 1
        else:
            page_img_counters[pg_str] += 1

        img_seq = page_img_counters[pg_str]
        img_seq_str = f"{img_seq:03d}"

        href_val = f"img/000000000000_pg_{pg_str}_fx_{img_seq_str}.jpg"

        graphic_tag = (
            f'<p><graphic xmlns:xlink="http://www.w3.org/1999/xlink" '
            f'xlink:href="{href_val}"/></p>'
        )

        return f"{prefix}\n{graphic_tag}"

    return task_sec_re.sub(replace_task_img, content)


# ==========================================
# STEP 11: MAIN XML PIPELINE / PROCESSOR
# Ella process-ayum correct-a order-padi execute panna
# ==========================================
def process_xml_text(content):
    # 11.1 Unwanted empty <p> & <sec-meta> remove panna
    content = EMPTY_OR_SPACE_P_RE.sub("", content)
    content = SEC_META_RE.sub("", content)
    content = EMPTY_TD_P_RE.sub(r"\1\2", content)

    page_matches = list(PAGE_RE.finditer(content))
    sec_counter = {}
    page_img_counters = {}

    # Helper function page number edukka
    def get_page_for_pos(pos):
        pg = "1"
        for m in page_matches:
            if m.start() <= pos:
                pg = str(int(m.group(1)))
            else:
                break
        return pg

    # 11.2 Headings-a book-part-a convert panna
    content = process_book_parts(content, get_page_for_pos)

    # 11.3 Kompetenz sections convert panna
    content = process_kompetenz_sections(content, get_page_for_pos, sec_counter)

    # 11.3b 'Lies und übe:' sections-ukku ID convert panna
    content = process_lies_und_uebe_sections(content, get_page_for_pos, sec_counter)

    # 11.4 Circled number lists convert panna
    content = process_circled_num_lists(
        content, get_page_for_pos, sec_counter, page_img_counters
    )

    # 11.5 Main Tasks convert panna
    content = process_task_sections(content, get_page_for_pos)

    # 11.6 Subtasks (a, b, c...) detect panni sec-type="subtask" maatha
    subtask_trackers = {}

    def replace_p(match):
        start_pos = match.start()
        pg_str = get_page_for_pos(start_pos)

        subtask_trackers[pg_str] = subtask_trackers.get(pg_str, 0) + 1
        task_count = subtask_trackers[pg_str]

        attrs = match.group("attrs")
        label = match.group("label")
        inner_content = match.group("content").strip()

        inner_content = process_solution_links(inner_content)
        inner_content = process_seite_links(inner_content)
        inner_content = process_nextlevel_tasks(
            inner_content, get_page_for_pos, start_pos
        )

        clean_label = re.sub(r"\W+", "", label)
        sec_id = f"pg{pg_str}_task{task_count:03d}{clean_label}"

        text_without_imgs = FIG_RE.sub("", inner_content).strip()

        # Image mattum irukkura subtask
        if not text_without_imgs and FIG_RE.search(inner_content):
            if pg_str not in page_img_counters:
                page_img_counters[pg_str] = 1
            else:
                page_img_counters[pg_str] += 1

            img_seq_str = f"{page_img_counters[pg_str]:03d}"
            href_val = f"img/000000000000_pg_{pg_str}_fx_{img_seq_str}.jpg"

            body_content = (
                f'<fig fig-type="exerciseImage">\n'
                f'<graphic xmlns:xlink="http://www.w3.org/1999/xlink" xlink:href="{href_val}"/>\n'
                f"</fig>"
            )

        # Text irukkura subtask
        else:

            def replace_inline_graphic(fig_match):
                if pg_str not in page_img_counters:
                    page_img_counters[pg_str] = 1
                else:
                    page_img_counters[pg_str] += 1

                img_seq_str = f"{page_img_counters[pg_str]:03d}"
                href_val = f"img/000000000000_pg_{pg_str}_fx_{img_seq_str}.jpg"
                return f'<graphic xmlns:xlink="http://www.w3.org/1999/xlink" xlink:href="{href_val}"/>'

            inner_content = FIG_RE.sub(replace_inline_graphic, inner_content)

            clean_end_text = re.sub(r"<[^>]+>", "", inner_content).strip()
            has_ending_punctuation = bool(re.search(r"[\.:;\?]$", clean_end_text))

            if has_ending_punctuation:
                body_content = (
                    f"<statement>\n<p{attrs}>{inner_content}</p>\n</statement>"
                )
            else:
                body_content = f"<p{attrs}>{inner_content}</p>"

        # Enforced newline before <sec> to guarantee separate lines
        res = (
            f'\n<sec sec-type="subtask" id="{sec_id}">\n'
            f"<label>{label}</label>\n"
            f"{body_content}\n"
            f"</sec>"
        )
        return res

    updated_content = P_TAG_RE.sub(replace_p, content)
    updated_content = process_task_statement_images(
        updated_content, get_page_for_pos, page_img_counters
    )

    # 11.7 Regular <p> tags-kulla irukkura page links-a maatha
    def replace_regular_p(match):
        full_p = match.group(0)
        start_pos = match.start()

        if '<sec sec-type="subtask"' in full_p:
            return full_p

        p_processed = process_solution_links(full_p)
        p_processed = process_seite_links(p_processed)
        p_processed = process_nextlevel_tasks(
            p_processed, get_page_for_pos, start_pos
        )
        return p_processed

    updated_content = re.sub(
        r"<p\b[^>]*>.*?</p>", replace_regular_p, updated_content, flags=re.DOTALL
    )

    # 11.8 Section veliye irukkura standalone images-a <graphic> tag-a maatha
    def replace_standalone_fig(match):
        start_pos = match.start()
        pg_str = get_page_for_pos(start_pos)

        if pg_str not in page_img_counters:
            page_img_counters[pg_str] = 1
        else:
            page_img_counters[pg_str] += 1

        img_seq = page_img_counters[pg_str]
        img_seq_str = f"{img_seq:03d}"

        href_val = f"img/000000000000_pg_{pg_str}_fx_{img_seq_str}.jpg"

        return (
            f'<p><graphic xmlns:xlink="http://www.w3.org/1999/xlink" '
            f'xlink:href="{href_val}"/></p>'
        )

    def process_figures_outside_sec(content_str):
        parts = re.split(r"(<sec\b[^>]*>.*?</sec>)", content_str, flags=re.DOTALL)
        for i in range(len(parts)):
            if not parts[i].startswith("<sec"):
                parts[i] = STANDALONE_FIG_RE.sub(replace_standalone_fig, parts[i])
        return "".join(parts)

    updated_content = process_figures_outside_sec(updated_content)

    return updated_content


# ==========================================
# STEP 12: MAIN EXECUTION ENTRY POINT
# Files read panni, process panni output save panna
# ==========================================
def main():
    try:
        # 12.1 Expiry Date check panna
        EXPIRY_DATE = datetime(2026, 9, 30, 23, 59, 59)

        if datetime.now() > EXPIRY_DATE:
            print(
                "This tool has expired on September 30, 2026. Please contact support/developer."
            )
            return

        # 12.2 Input folder check panna
        if not os.path.exists(INPUT_DIR):
            print(
                f"Error: '{INPUT_DIR}' folder illai! Create panni files podunga."
            )
            return

        files = [f for f in os.listdir(INPUT_DIR) if f.endswith(".xml")]

        if not files:
            print(f"'{INPUT_DIR}' folder-kulla XML files edhum illai.")
            return

        print("Processing started...\n")

        # 12.3 Ovvoru XML file-a edutthu multiple encodings moolama read panni process panna
        for filename in files:
            print(f"Processing: {filename}")
            in_path = os.path.join(INPUT_DIR, filename)
            out_path = os.path.join(OUTPUT_DIR, filename)

            try:
                content = None
                # Multi-encoding check
                for enc in ["utf-8-sig", "utf-8", "latin-1", "cp1252"]:
                    try:
                        with open(in_path, "r", encoding=enc) as f:
                            content = f.read()
                        break
                    except UnicodeDecodeError:
                        continue

                if content is None:
                    raise Exception(
                        "File encoding non-compatible. Unable to read file."
                    )

                # XML processing call
                updated_xml = process_xml_text(content)

                # Output file save panna
                with open(out_path, "w", encoding="utf-8") as f:
                    f.write(updated_xml)

                print(f"Successfully processed: {filename} -> {out_path}\n")

            except Exception as e:
                print(f"Error in processing {filename}: {e}\n")

        print("All files processed successfully!")

    finally:
        input("\nPress ENTER to exit...")


if __name__ == "__main__":
    main()