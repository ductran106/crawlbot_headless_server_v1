from src.utils.config import (
    build_autosave_docx_name,
    build_final_docx_name,
    build_formatted_docx_name,
)


def test_build_autosave_docx_name_uses_canonical_schema():
    assert (
        build_autosave_docx_name("20260319_P1", "duc-ProBook", "return_room_lich")
        == "autosave_20260319_P1_duc-ProBook_return_room_lich.docx"
    )


def test_build_final_docx_name_uses_canonical_schema():
    assert (
        build_final_docx_name("20260319_P1", "duc-ProBook", "return_room_lich", 19)
        == "final_20260319_P1_duc-ProBook_return_room_lich_19mess.docx"
    )


def test_build_formatted_docx_name_uses_canonical_schema():
    assert (
        build_formatted_docx_name("20260319_P1", "duc-ProBook", "return_room_lich", 19)
        == "Lich_20260319_P1_duc-ProBook_return_room_lich_19mess_crawl.docx"
    )
