# Module lấy cấu trúc trang Zalo Web (elements, selectors) để phát triển tính năng sau
# src/tools/zalo_structure_capture.py
import os
import json
from datetime import datetime
from selenium.webdriver.common.by import By

# Selectors đang dùng trong codebase (để kiểm tra tồn tại + mô tả)
ZALO_SELECTORS_REF = [
    {"selector": "#contact-search-input", "by": "id", "desc": "Ô tìm kiếm liên hệ / nhóm"},
    {"selector": ".qrcode img", "by": "css", "desc": "Ảnh QR đăng nhập"},
    {"selector": ".qrcode-expired", "by": "css", "desc": "QR hết hạn"},
    {"selector": ".qrcode-expired .btn", "by": "css", "desc": "Nút làm mới QR"},
    {"selector": ".conv-item", "by": "css", "desc": "Mỗi item trong danh sách hội thoại (kết quả tìm kiếm)"},
    {"selector": ".header-title", "by": "css", "desc": "Tiêu đề nhóm chat (trong room chat)"},
    {"selector": ".header-title.flx.flx-al-c.flex-1", "by": "css", "desc": "Tiêu đề nhóm (selector đầy đủ)"},
    {"selector": ".chat-item", "by": "css", "desc": "Mỗi tin nhắn trong khung chat"},
    {"selector": ".chat-container", "by": "css", "desc": "Khung chứa danh sách tin nhắn"},
    {"selector": ".conversation-list", "by": "css", "desc": "Danh sách hội thoại (alias)"},
    {"selector": "[data-component='bubble-message']", "by": "css", "desc": "Bubble tin nhắn"},
    {"selector": ".message-sender-name-content .truncate", "by": "css", "desc": "Tên người gửi (content)"},
    {"selector": ".message-sender-name-bubble .truncate", "by": "css", "desc": "Tên người gửi (bubble)"},
    {"selector": "[data-component='message-content-view']", "by": "css", "desc": "Nội dung tin nhắn"},
    {"selector": "[data-component='text-container']", "by": "css", "desc": "Container chữ"},
    {"selector": "span.text, a.mention-name, a.text-is-phone-number", "by": "css", "desc": "Đoạn chữ / mention / SĐT"},
    {"selector": ".overflow-hidden", "by": "css", "desc": "Container overflow"},
    {"selector": ".card-send-time__sendTime", "by": "css", "desc": "Thời gian gửi (card)"},
    {"selector": ".bubble-message-time", "by": "css", "desc": "Thời gian gửi (bubble)"},
]


def _safe_get(driver, by, selector, is_single=True):
    try:
        if by == "id":
            elements = driver.find_elements(By.ID, selector.lstrip("#"))
        else:
            elements = driver.find_elements(By.CSS_SELECTOR, selector)
        if is_single:
            return (len(elements), elements[0] if elements else None)
        return (len(elements), elements[:5] if len(elements) > 5 else elements)
    except Exception as e:
        return (0, None, str(e))


def _element_summary(el):
    if el is None:
        return None
    try:
        tag = el.tag_name
        eid = el.get_attribute("id") or ""
        classes = (el.get_attribute("class") or "").strip()
        text = (el.text or "")[:200].replace("\n", " ")
        return {"tag": tag, "id": eid, "class": classes[:150], "text_preview": text[:100]}
    except Exception:
        return {"error": "cannot_inspect"}


def capture_zalo_structure(driver, output_dir=None):
    """
    Lấy cấu trúc trang Zalo Web hiện tại (URL, selectors, số lượng element, mẫu thuộc tính).
    Ghi ra file .md và .json trong data/logs/ để sau dễ phát triển thêm tính năng.

    Args:
        driver: Selenium WebDriver đang mở Zalo Web (đã vào trang chat.zalo.me).
        output_dir: Thư mục ghi file (mặc định: data/logs).

    Returns:
        (path_md, path_json) hoặc (None, None) nếu lỗi.
    """
    from ..utils.config import DATA_FOLDER
    from ..utils.logger import log
    import logging

    if output_dir is None:
        output_dir = os.path.join(DATA_FOLDER, "logs")
    os.makedirs(output_dir, exist_ok=True)
    path_md, path_json = build_structure_capture_paths(datetime.now(), output_dir=output_dir)

    out = {
        "captured_at": datetime.now().isoformat(),
        "url": None,
        "title": None,
        "selectors": [],
        "page_classes_sample": [],
        "body_info": {},
    }

    try:
        out["url"] = driver.current_url
        out["title"] = driver.title
    except Exception as e:
        out["url"] = f"(error: {e})"
        out["title"] = "(error)"

    # Kiểm tra từng selector tham chiếu
    for ref in ZALO_SELECTORS_REF:
        sel = ref["selector"]
        by = ref.get("by", "css")
        desc = ref.get("desc", "")
        try:
            if by == "id":
                elements = driver.find_elements(By.ID, sel.lstrip("#"))
            else:
                elements = driver.find_elements(By.CSS_SELECTOR, sel)
            count = len(elements)
            sample = None
            if elements:
                el = elements[0]
                sample = _element_summary(el)
            out["selectors"].append({
                "selector": sel,
                "by": by,
                "desc": desc,
                "count": count,
                "sample": sample,
            })
        except Exception as e:
            out["selectors"].append({
                "selector": sel,
                "by": by,
                "desc": desc,
                "error": str(e),
                "count": 0,
            })

    # Lấy mẫu class có trên page (để tìm selector mới)
    try:
        classes_js = """
        var seen = {};
        document.querySelectorAll('[class]').forEach(function(el) {
            (el.className || '').split(/\\s+/).forEach(function(c) {
                if (c && c.length < 80) seen[c] = (seen[c] || 0) + 1;
            });
        });
        return Object.keys(seen).sort().slice(0, 150);
        """
        out["page_classes_sample"] = driver.execute_script(classes_js) or []
    except Exception as e:
        out["page_classes_sample"] = [f"(error: {e})"]

    # Thông tin body / container chính
    try:
        body = driver.find_element(By.TAG_NAME, "body")
        out["body_info"] = {
            "children_count": len(body.find_elements(By.XPATH, "./*")),
            "innerHTML_length": len((body.get_attribute("innerHTML") or "")),
        }
    except Exception as e:
        out["body_info"] = {"error": str(e)}

    # Ghi JSON
    try:
        with open(path_json, "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=2)
    except Exception as e:
        log(f"Không ghi được file JSON cấu trúc Zalo: {e}", level=logging.ERROR)
        path_json = None

    # Ghi Markdown (dễ đọc, dễ gửi cho dev)
    try:
        lines = [
            "# Cấu trúc trang Zalo Web",
            "",
            f"**Thời điểm:** {out['captured_at']}",
            f"**URL:** {out['url']}",
            f"**Title:** {out['title']}",
            "",
            "## Selectors đang dùng trong crawler",
            "",
            "| Selector | Mô tả | Số lượng | Mẫu (tag/id/class) |",
            "|----------|-------|----------|--------------------|",
        ]
        for s in out["selectors"]:
            desc = (s.get("desc") or "").replace("|", "\\|")
            sel = (s.get("selector") or "").replace("|", "\\|")
            cnt = s.get("count", "?")
            err = s.get("error")
            if err:
                sample = f"error: {err[:50]}"
            else:
                sm = s.get("sample")
                sample = ""
                if sm and isinstance(sm, dict):
                    sample = f"{sm.get('tag','')} #{sm.get('id','')} .{sm.get('class','')[:30]}"
            lines.append(f"| `{sel}` | {desc} | {cnt} | {sample} |")
        lines.extend([
            "",
            "## Mẫu class có trên trang (để tham khảo selector mới)",
            "",
            "```",
            ", ".join(out["page_classes_sample"][:80]),
            "```",
            "",
            "## Body",
            "",
            f"- Số node con trực tiếp của body: {out['body_info'].get('children_count', 'N/A')}",
            f"- Độ dài innerHTML (ký tự): {out['body_info'].get('innerHTML_length', 'N/A')}",
            "",
        ])
        with open(path_md, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
    except Exception as e:
        log(f"Không ghi được file MD cấu trúc Zalo: {e}", level=logging.ERROR)
        path_md = None

    log(f"Đã lưu cấu trúc Zalo: MD={path_md}, JSON={path_json}", level=logging.INFO)
    return (path_md, path_json)
