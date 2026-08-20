import os
import re

# Folder configuration
INPUT_DIR = "input"
OUTPUT_DIR = "output"

os.makedirs(OUTPUT_DIR, exist_ok=True)

# Regex 1: Match <p> tags starting with list prefixes: a), a., 1), 1., i), i. etc.
P_TAG_RE = re.compile(
    r"<p(?P<attrs>[^>]*)>\s*(?P<label>[a-zA-Z0-9]+[\.\)])\s*(?P<content>.*?)</p>",
    re.DOTALL,
)

# Regex 2: Track pageStart processing instructions like <?pageStart ... pagination="6"?>
PAGE_RE = re.compile(r'<\?pageStart\b[^>]*pagination=["\'](\d+)["\'][^>]*\?>')

# Regex 3: Detect if inner content contains <fig...> or <img...> tags
FIG_RE = re.compile(r"<(fig|img)\b[^>]*>.*?(</\1>|/>)", re.DOTALL)

# Regex 4: Match FULL standalone <fig>...</fig> or <img.../> tags precisely
STANDALONE_FIG_RE = re.compile(
    r"<fig\b[^>]*>.*?</fig>|<img\b[^>]*/?>", re.DOTALL | re.IGNORECASE
)

# Regex 5: Match 'Seite <page_num>' optional with 'Nr. <task_numbers>' pattern
SEITE_RE = re.compile(
    r"\b(Seite\s+(\d+)(?:\s+Nr\.\s+([\d\s,]+))?)\b",
    re.IGNORECASE,
)

# Regex 6: Match &#x25B8; followed by task number
NEXTLEVEL_RE = re.compile(r"&#x25B8;\s*(\d+)", re.IGNORECASE)

# Regex 7: Cleanup for any <sec-meta> tags completely
SEC_META_RE = re.compile(r"<sec-meta>.*?</sec-meta>", re.IGNORECASE | re.DOTALL)


def process_seite_links(text):
    """Transforms 'Seite 196 Nr. 4, 5' or 'Seite 204' into exact <xref> link tags."""

    def replace_seite(match):
        full_match = match.group(1)
        page_num = int(match.group(2))
        page_str = f"{page_num:03d}"  # 196 -> "196", 6 -> "006"
        nums_part = match.group(3)

        # Case 1: Only "Seite <num>" without "Nr." (e.g. Seite 204)
        if not nums_part:
            rid_val = f"pg{page_str}"
            return f'<xref ref-type="link-LookItUp" rid="{rid_val}">{full_match}</xref>'

        # Case 2: "Seite <num> Nr. <tasks>" (e.g. Seite 196 Nr. 4, 5)
        nums_part = nums_part.strip()
        raw_nums = [n.strip() for n in nums_part.split(",") if n.strip()]

        if not raw_nums:
            rid_val = f"pg{page_str}"
            return f'<xref ref-type="link-LookItUp" rid="{rid_val}">{full_match}</xref>'

        xref_list = []
        for idx, num_str in enumerate(raw_nums):
            num_val = int(num_str)
            task_str = f"{num_val:03d}"  # 4 -> "004", 36 -> "036"
            rid_val = f"pg{page_str}_task{task_str}"

            if idx == 0:
                # First element gets full prefix: "Seite 196 Nr. 4"
                text_content = f"Seite {match.group(2)} Nr. {num_str}"
            else:
                # Subsequent elements get only the number: "5"
                text_content = num_str

            xref_tag = f'<xref ref-type="link-LookItUp" rid="{rid_val}">{text_content}</xref>'
            xref_list.append(xref_tag)

        # Join generated xref tags with comma space
        return ", ".join(xref_list)

    return SEITE_RE.sub(replace_seite, text)


def process_nextlevel_tasks(text, current_page_fn, pos_offset=0):
    """Transforms '&#x25B8;12' into standard <xref> format."""

    def replace_nextlevel(match):
        start_pos = pos_offset + match.start()
        pg_str = current_page_fn(start_pos)

        task_num = int(match.group(1))
        task_str = f"{task_num:03d}"  # 12 -> "012", 9 -> "009"

        rid_val = f"pg{pg_str}_task{task_str}"

        return f'&#x25B8; <xref ref-type="nextlevel_task" rid="{rid_val}">{task_num}</xref>'

    # Replace all matches using NEXTLEVEL_RE
    text = NEXTLEVEL_RE.sub(replace_nextlevel, text)

    return text


def process_xml_text(content):
    # FIRST STEP: Clean all <sec-meta>...</sec-meta> tags from content completely
    content = SEC_META_RE.sub("", content)

    current_page = "001"
    task_count = 1

    # Pre-find all pageStart tag positions in the file
    page_matches = list(PAGE_RE.finditer(content))

    # Page-wise counter dictionary to track image order for each page separately
    page_img_counters = {}

    def get_page_for_pos(pos):
        """Finds the active page number before the current element position."""
        pg = "001"
        for m in page_matches:
            if m.start() <= pos:
                pg = f"{int(m.group(1)):03d}"  # Converts "6" to "006"
            else:
                break
        return pg

    def replace_p(match):
        nonlocal task_count

        start_pos = match.start()
        pg_str = get_page_for_pos(start_pos)

        attrs = match.group("attrs")
        label = match.group("label")  # e.g., "a)"
        inner_content = match.group("content").strip()  # Content after prefix

        # Process Seite links if present in the paragraph
        inner_content = process_seite_links(inner_content)

        # Process Nextlevel Tasks (&#x25B8;12)
        inner_content = process_nextlevel_tasks(
            inner_content, get_page_for_pos, start_pos
        )

        # Extract only alphanumeric character for ID suffix (e.g., "a)" -> "a")
        clean_label = re.sub(r"\W+", "", label)

        # Construct subtask ID format: pg006_task001a
        sec_id = f"pg{pg_str}_task{task_count:03d}{clean_label}"

        # Check if inner content is an image/fig tag inside list
        if FIG_RE.search(inner_content):
            if pg_str not in page_img_counters:
                page_img_counters[pg_str] = 1
            else:
                page_img_counters[pg_str] += 1

            img_seq = page_img_counters[pg_str]
            img_seq_str = f"{img_seq:03d}"  # 1 -> "001"

            href_val = f"img/000000000000_pg_{pg_str}_fx_{img_seq_str}.jpg"

            body_content = (
                f'<fig fig-type="exerciseImage">\n'
                f'<graphic xmlns:xlink="http://www.w3.org/1999/xlink" xlink:href="{href_val}"/>\n'
                f"</fig>"
            )
        else:
            body_content = f"<p{attrs}>{inner_content}</p>"

        res = (
            f'<sec sec-type="subtask" id="{sec_id}">\n'
            f"<label>{label}</label>\n"
            f"{body_content}\n"
            f"</sec>"
        )
        return res

    # 1. Process List items (<p>a) ... </p>)
    updated_content = P_TAG_RE.sub(replace_p, content)

    # 2. Process Seite links and Nextlevel tasks in non-list <p> tags
    def replace_regular_p(match):
        full_p = match.group(0)
        start_pos = match.start()

        # Skip if already inside a <sec> block from previous pass
        if "<sec" in full_p:
            return full_p

        p_processed = process_seite_links(full_p)
        p_processed = process_nextlevel_tasks(
            p_processed, get_page_for_pos, start_pos
        )
        return p_processed

    updated_content = re.sub(
        r"<p\b[^>]*>.*?</p>", replace_regular_p, updated_content, flags=re.DOTALL
    )

    # 3. Process Standalone <fig><img/></fig> tags (outside list <p>)
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
            f"<p><graphic xmlns:xlink=\"http://www.w3.org/1999/xlink\" "
            f'xlink:href="{href_val}"/></p>'
        )

    # Replace standalone figures that are not inside <sec> tags
    def process_figures_outside_sec(content_str):
        parts = re.split(r"(<sec\b[^>]*>.*?</sec>)", content_str, flags=re.DOTALL)
        for i in range(len(parts)):
            if not parts[i].startswith("<sec"):
                parts[i] = STANDALONE_FIG_RE.sub(replace_standalone_fig, parts[i])
        return "".join(parts)

    updated_content = process_figures_outside_sec(updated_content)

    return updated_content


def main():
    if not os.path.exists(INPUT_DIR):
        print(
            f"Error: '{INPUT_DIR}' folder illai! Folder create panni XML files-a athula podunga."
        )
        return

    files = [f for f in os.listdir(INPUT_DIR) if f.endswith(".xml")]

    if not files:
        print(f"'{INPUT_DIR}' folder-kulla XML files edhum illai.")
        return

    for filename in files:
        in_path = os.path.join(INPUT_DIR, filename)
        out_path = os.path.join(OUTPUT_DIR, filename)

        try:
            with open(in_path, "r", encoding="utf-8") as f:
                content = f.read()

            updated_xml = process_xml_text(content)

            with open(out_path, "w", encoding="utf-8") as f:
                f.write(updated_xml)

            print(f"Successfully processed: {filename} -> {out_path}")

        except Exception as e:
            print(f"Error in processing {filename}: {e}")


if __name__ == "__main__":
    main()