# main.py - đặt ở thư mục gốc CrawlZalo_tonghop
import sys
import time
import asyncio
import random
from datetime import datetime

from src.utils.logger import log, logging
from src.utils.error_logger import log_error
from src.utils.signals import init_signal_handlers, is_terminating
from src.utils.config import (
    ensure_data_folder,
    GROUP_NAMES,
    get_group_data_folder,
    GROUP_SWITCH_MIN_SEC,
    GROUP_SWITCH_MAX_SEC,
    SCHED_MAX_CONSECUTIVE_VISITS,
    SCHED_STARVATION_SEC_2ROOM,
    SCHED_STARVATION_SEC_3ROOM,
    SCHED_HOT_SLEEP_SEC,
    SCHED_PRESSURE_SLEEP_SEC,
    SCHED_NORMAL_SLEEP_MIN_SEC_2ROOM,
    SCHED_NORMAL_SLEEP_MAX_SEC_2ROOM,
    SCHED_NORMAL_SLEEP_MIN_SEC_3ROOM,
    SCHED_NORMAL_SLEEP_MAX_SEC_3ROOM,
    HEADLESS,
)
from src.ui.control_window import start_control_window, stop_control_window
from src.utils.browser_errors import is_browser_dead_error
from src.utils.observability import (
    build_browser_recovery_payload,
    build_room_switch_tracker_snapshot,
    format_event_log,
    log_event,
)
from src.browser.driver import browser_manager
from src.browser.navigation import ZaloNavigator
from src.auth.login import ZaloAuthManager
from src.crawler.message_crawler import MessageCrawler
from src.notification.telegram import send_notification, send_error, send_alert, check_telegram_connection
from src.notification.messages import build_alert_ready_notification, build_save_document_notification
from src.storage.docx_handler import DocxHandler

def countdown(seconds):
    """Đếm ngược trong console"""
    for i in range(seconds, 0, -1):
        sys.stdout.write(f"\rĐang đợi {i} giây...")
        sys.stdout.flush()
        time.sleep(1)
    sys.stdout.write("\rHoàn thành đợi!            \n")
    sys.stdout.flush()

async def crawl_messages():
    """Hàm chính crawler tin nhắn Zalo"""
    driver = None
    try:
        # Đảm bảo thư mục dữ liệu tồn tại
        ensure_data_folder()
        
        # Khởi động Chrome
        driver = browser_manager.get_chrome_driver()
        
        # Khởi tạo các module
        zalo_navigator = ZaloNavigator(driver)
        zalo_auth = ZaloAuthManager(driver)
        
        # Mở trang Zalo Web
        zalo_navigator.open_zalo_web()
        
        # Kiểm tra đăng nhập
        if not zalo_auth.check_login_status():
            # Đợi đăng nhập
            login_success = zalo_auth.wait_for_login()
            if not login_success:
                return False
        
        # Tìm và truy cập nhóm chat
        group_access = zalo_navigator.find_and_access_group()
        if not group_access:
            return False
        
        # Khởi tạo và bắt đầu crawler
        crawler = MessageCrawler(driver, zalo_navigator)
        
        # Chuyển biến is_terminating vào crawler
        crawler.external_stop_flag = is_terminating
        
        # Chạy crawler và chờ kết quả
        file_path = crawler.start_crawling()
        
        return file_path
        
    except Exception as e:
        error_message = f"❌ Lỗi hệ thống: {str(e)}"
        log(error_message, level=logging.ERROR)
        log_error(e, context={"phase": "crawl_messages"}, extra_message="Lỗi trong crawl_messages")
        send_error(error_message)
        return False
    finally:
        # Dọn dẹp
        if driver:
            try:
                driver.quit()
            except:
                pass

def _recover_browser_and_update_refs(browser_manager, zalo_navigator, crawlers, groups, zalo_auth, target_group=None, recovery_reason=None):
    """
    Khởi động lại Chrome, cập nhật driver cho navigator và mọi crawler, mở lại Zalo.
    Nếu có target_group thì chỉ báo success khi đã reopen/verify lại được room mục tiêu.
    Trả về driver mới nếu thành công, None nếu thất bại.
    """
    try:
        log("Phát hiện browser/tab lỗi, đang khởi động lại Chrome...", level=logging.WARNING)
        log_event(
            "browser_recovery_requested",
            build_browser_recovery_payload("browser_recovery_requested", groups=groups),
            prefix="BROWSER_RECOVERY_REQUESTED",
            level=logging.WARNING,
        )
        if not browser_manager.restart_driver(reason=recovery_reason):
            log_event(
                "browser_recovery_result",
                build_browser_recovery_payload(
                    "browser_recovery_result",
                    groups=groups,
                    success=False,
                    step="restart_driver",
                ),
                prefix="BROWSER_RECOVERY_RESULT",
                level=logging.ERROR,
            )
            return None
        driver = browser_manager.get_driver()
        zalo_navigator.driver = driver
        zalo_auth.driver = driver
        for g in groups:
            if g in crawlers:
                crawlers[g].driver = driver
                crawlers[g].browser_navigation.driver = driver
                crawlers[g].message_processor.driver = driver
        recovered = browser_manager.recover_session()
        if not recovered:
            log_event(
                "browser_recovery_result",
                build_browser_recovery_payload(
                    "browser_recovery_result",
                    groups=groups,
                    success=False,
                    step="recover_session",
                ),
                prefix="BROWSER_RECOVERY_RESULT",
                level=logging.ERROR,
            )
            return None

        for attempt in range(3):
            if zalo_auth.check_login_status():
                break
            if attempt < 2:
                time.sleep(5)
        if not zalo_auth.check_login_status():
            if not zalo_auth.wait_for_login(timeout_seconds=90):
                log("Không thể đăng nhập lại sau khi khôi phục (đã thử 90s)", level=logging.ERROR)
                log_event(
                    "browser_recovery_result",
                    build_browser_recovery_payload(
                        "browser_recovery_result",
                        groups=groups,
                        success=False,
                        step="wait_for_login",
                    ),
                    prefix="BROWSER_RECOVERY_RESULT",
                    level=logging.ERROR,
                )
                return None

        if target_group:
            reopen_ok = bool(zalo_navigator.find_and_access_group(group_name=target_group))
            if not reopen_ok:
                log(
                    f"Khôi phục browser xong nhưng chưa reopen được room mục tiêu '{target_group}'",
                    level=logging.ERROR,
                )
                log_event(
                    "browser_recovery_result",
                    build_browser_recovery_payload(
                        "browser_recovery_result",
                        groups=groups,
                        success=False,
                        step="reopen_group",
                    ),
                    prefix="BROWSER_RECOVERY_RESULT",
                    level=logging.ERROR,
                )
                return None

        log("Khôi phục browser thành công, tiếp tục crawl.", level=logging.INFO)
        log_event(
            "browser_recovery_result",
            build_browser_recovery_payload(
                "browser_recovery_result",
                groups=groups,
                success=True,
                step="ready" if not target_group else "reopen_group",
            ),
            prefix="BROWSER_RECOVERY_RESULT",
            level=logging.INFO,
        )
        return driver
    except Exception as ex:
        log(f"Lỗi khi khôi phục browser: {str(ex)}", level=logging.ERROR)
        log_event(
            "browser_recovery_result",
            build_browser_recovery_payload(
                "browser_recovery_result",
                groups=groups,
                success=False,
                step="exception",
                error=str(ex),
            ),
            prefix="BROWSER_RECOVERY_RESULT",
            level=logging.ERROR,
        )
        return None


def _update_group_backlog_tracker(group_tracker, *, backlog_pressure, possible_gap):
    """Persist anti-miss pressure/gap streak theo từng group ở scheduler level."""
    tracker = dict(group_tracker or {})
    pressure_streak = int(tracker.get("pressure_streak", 0) or 0)
    gap_streak = int(tracker.get("gap_streak", 0) or 0)
    was_hot = bool(tracker.get("backlog_hot", False))

    if backlog_pressure:
        pressure_streak += 1
    else:
        pressure_streak = 0

    if possible_gap:
        gap_streak += 1
    else:
        gap_streak = 0

    backlog_hot = pressure_streak >= 2 or gap_streak >= 2
    if not backlog_hot:
        hot_stay_granted = False
    elif not was_hot:
        hot_stay_granted = False
    else:
        hot_stay_granted = bool(tracker.get("hot_stay_granted", False))

    tracker["pressure_streak"] = pressure_streak
    tracker["gap_streak"] = gap_streak
    tracker["backlog_hot"] = backlog_hot
    tracker["hot_stay_granted"] = hot_stay_granted
    return tracker


def _build_scheduler_policy(room_count):
    room_count = max(1, int(room_count or 1))
    if room_count <= 2:
        return {
            "room_count": room_count,
            "max_consecutive_visits": max(1, int(SCHED_MAX_CONSECUTIVE_VISITS or 2)),
            "starvation_threshold_seconds": max(1, int(SCHED_STARVATION_SEC_2ROOM or 6)),
            "hot_sleep_seconds": max(1, int(SCHED_HOT_SLEEP_SEC or 1)),
            "pressure_sleep_seconds": max(1, int(SCHED_PRESSURE_SLEEP_SEC or 2)),
            "normal_sleep_min_seconds": max(1, int(SCHED_NORMAL_SLEEP_MIN_SEC_2ROOM or 2)),
            "normal_sleep_max_seconds": max(1, int(SCHED_NORMAL_SLEEP_MAX_SEC_2ROOM or 3)),
        }
    return {
        "room_count": room_count,
        "max_consecutive_visits": max(1, int(SCHED_MAX_CONSECUTIVE_VISITS or 2)),
        "starvation_threshold_seconds": max(1, int(SCHED_STARVATION_SEC_3ROOM or 8)),
        "hot_sleep_seconds": max(1, int(SCHED_HOT_SLEEP_SEC or 1)),
        "pressure_sleep_seconds": max(1, int(SCHED_PRESSURE_SLEEP_SEC or 2)),
        "normal_sleep_min_seconds": max(1, int(SCHED_NORMAL_SLEEP_MIN_SEC_3ROOM or 2)),
        "normal_sleep_max_seconds": max(1, int(SCHED_NORMAL_SLEEP_MAX_SEC_3ROOM or 4)),
    }


def _compute_room_priority(group_name, room_state, policy):
    state = room_state if isinstance(room_state, dict) else {}
    starvation_seconds = float(state.get("starvation_seconds", 0) or 0)
    possible_gap = bool(state.get("possible_gap", False))
    backlog_hot = bool(state.get("backlog_hot", False))
    backlog_pressure = bool(state.get("backlog_pressure", False))
    consecutive_visits = int(state.get("consecutive_visits", 0) or 0)
    never_visited = bool(state.get("never_visited", False) or not float(state.get("last_visited_at", 0.0) or 0.0))

    verify_mode = state.get("last_verify_mode")
    gap_risk_reason = state.get("last_gap_risk_reason")
    revisit_boost_hint = bool(state.get("revisit_boost_hint", False))

    score = starvation_seconds
    if never_visited:
        score += max(float(policy.get("starvation_threshold_seconds", 1)), 1.0) + 10
    if possible_gap:
        score += 6
    if backlog_hot:
        score += 4
    if backlog_pressure:
        score += 2
    if verify_mode == "usable":
        score += 2
    if gap_risk_reason == "unverified_navigation":
        score += 4
    if gap_risk_reason == "navigation_stall":
        score += 5
    if revisit_boost_hint:
        score += 3
    if consecutive_visits >= int(policy.get("max_consecutive_visits", 2)):
        score -= 100
    elif consecutive_visits > 0:
        score -= consecutive_visits * 3
    return score


def _select_next_group(groups, room_state, current_group=None):
    groups = [g for g in (groups or []) if str(g).strip()]
    if not groups:
        return None, "no_groups", None
    if len(groups) == 1:
        return groups[0], "single_group", None

    policy = _build_scheduler_policy(len(groups))
    starvation_threshold = float(policy["starvation_threshold_seconds"])
    current_index = groups.index(current_group) if current_group in groups else -1

    bootstrap_candidates = [
        g for g in groups
        if g != current_group and bool((room_state.get(g) or {}).get("never_visited", False))
    ]
    if bootstrap_candidates:
        return bootstrap_candidates[0], "bootstrap_never_visited", None

    starvation_candidates = [
        g for g in groups
        if float((room_state.get(g) or {}).get("starvation_seconds", 0) or 0) >= starvation_threshold
        and int((room_state.get(g) or {}).get("consecutive_visits", 0) or 0) < int(policy["max_consecutive_visits"])
    ]
    if starvation_candidates:
        selected = max(
            starvation_candidates,
            key=lambda g: float((room_state.get(g) or {}).get("starvation_seconds", 0) or 0),
        )
        return selected, "starvation_guard", None

    scored = []
    for g in groups:
        state = room_state.get(g) or {}
        if g == current_group and int(state.get("consecutive_visits", 0) or 0) >= int(policy["max_consecutive_visits"]):
            continue
        score = _compute_room_priority(g, state, policy)
        scored.append((score, g))

    if scored:
        scored.sort(key=lambda item: (item[0], -groups.index(item[1])), reverse=True)
        best_score, best_group = scored[0]
        if best_score > 0:
            return best_group, "priority_score", best_score

    if current_index >= 0:
        return groups[(current_index + 1) % len(groups)], "round_robin", None
    return groups[0], "round_robin", None


def _select_sleep_seconds(room_snapshot, policy):
    snapshot = room_snapshot if isinstance(room_snapshot, dict) else {}
    if bool(snapshot.get("possible_gap", False)) or bool(snapshot.get("backlog_hot", False)):
        return int(policy["hot_sleep_seconds"])
    if bool(snapshot.get("backlog_pressure", False)):
        return int(policy["pressure_sleep_seconds"])
    return random.randint(int(policy["normal_sleep_min_seconds"]), int(policy["normal_sleep_max_seconds"]))


def _format_room_switch_tracker_log(snapshot):
    """Chuẩn hóa room-switch tracker thành JSON-line cố định để grep/ship observability."""
    return format_event_log("room_switch_tracker", payload=snapshot, prefix="ROOM_SWITCH_TRACKER")


def run_multi_group_single_session(groups):
    """
    Chạy nhiều group trong 1 process / 1 session Zalo Web.
    Luân phiên round-robin, random 3-7s để giảm hành vi bot.
    Tuyệt đối không đọc tin nhắn nếu chưa xác nhận đúng group.
    Khi gặp tab crashed / timeout sẽ tự khởi động lại Chrome và tiếp tục.
    """
    driver = None
    crawlers = {}
    try:
        ensure_data_folder()

        # Chuẩn bị folder dữ liệu riêng cho từng group
        for g in groups:
            ensure_data_folder(get_group_data_folder(g))

        driver = browser_manager.get_chrome_driver()
        zalo_navigator = ZaloNavigator(driver)
        zalo_auth = ZaloAuthManager(driver)

        zalo_navigator.open_zalo_web()
        if not zalo_auth.check_login_status():
            if not zalo_auth.wait_for_login():
                return False

        # Ghi nhận thời gian bắt đầu phiên multi-group (dùng đặt tên file & phiên theo thời điểm START)
        session_start_time = datetime.now()

        # Tạo crawler riêng cho từng group (trạng thái + autosave tách biệt)
        for g in groups:
            crawlers[g] = MessageCrawler(
                driver,
                zalo_navigator,
                group_name=g,
                data_folder=get_group_data_folder(g),
                room_count=len(groups),
            )
            crawlers[g].external_stop_flag = is_terminating

        idx = 0
        room_cycle = 0
        min_s = max(1, int(GROUP_SWITCH_MIN_SEC or 3))
        max_s = max(min_s, int(GROUP_SWITCH_MAX_SEC or 7))
        consecutive_recover_failures = 0
        max_recover_failures = 3  # Dừng recover sau 3 lần thất bại liên tiếp để tránh loop
        backlog_trackers = {
            g: {
                "pressure_streak": 0,
                "gap_streak": 0,
                "backlog_hot": False,
                "last_verify_mode": None,
                "last_gap_risk_reason": None,
                "revisit_boost_applied": False,
            }
            for g in groups
        }
        room_state = {
            g: {
                "last_visited_at": 0.0,
                "never_visited": True,
                "consecutive_visits": 0,
                "starvation_seconds": 0.0,
                "backlog_pressure": False,
                "possible_gap": False,
                "backlog_hot": False,
                "last_processed_count": 0,
                "last_visible_count": 0,
                "last_verify_mode": None,
                "last_gap_risk_reason": None,
                "navigation_possible_gap": False,
                "crawler_possible_gap": False,
                "revisit_boost_hint": False,
                "last_retry_attempt": 0,
                "last_navigation_status_code": None,
            }
            for g in groups
        }
        current_group = None
        policy = _build_scheduler_policy(len(groups))
        last_nav_result = {g: {"ok": False, "verify_mode": None, "possible_gap": False, "gap_risk_reason": None, "revisit_boost_hint": False, "retry_attempt": 0, "status_code": None} for g in groups}

        while not is_terminating():
            room_cycle += 1
            g = current_group or groups[idx % len(groups)]

            should_recycle, recycle_reason = browser_manager.should_proactively_recycle(room_cycle=room_cycle)
            if should_recycle:
                log(
                    f"Proactive recycle browser trước nhịp room '{g}' (reason={recycle_reason}, room_cycle={room_cycle})",
                    level=logging.WARNING,
                )
                new_driver = _recover_browser_and_update_refs(
                    browser_manager,
                    zalo_navigator,
                    crawlers,
                    groups,
                    zalo_auth,
                    target_group=g,
                    recovery_reason=f"proactive_recycle:{recycle_reason}",
                )
                if new_driver is not None:
                    driver = new_driver
                    consecutive_recover_failures = 0
                else:
                    consecutive_recover_failures += 1
                    if consecutive_recover_failures >= max_recover_failures:
                        log(
                            f"Proactive recycle thất bại liên tiếp {consecutive_recover_failures} lần; dừng loop để tránh churn vô hạn",
                            level=logging.ERROR,
                        )
                        break
                    time.sleep(2)
                    continue

            # Điều hướng sang group và chỉ crawl khi xác nhận đúng group
            navigation_ok = False
            nav_result = {"ok": False, "verify_mode": None, "possible_gap": False, "gap_risk_reason": None, "revisit_boost_hint": False, "retry_attempt": 0, "status_code": None}
            try:
                nav_result = zalo_navigator.find_and_access_group(group_name=g) or nav_result
                last_nav_result[g] = nav_result
                navigation_ok = bool(nav_result.get("ok"))
                consecutive_recover_failures = 0
                if navigation_ok:
                    log(
                        f"({g}) Navigation ok; verify_mode={nav_result.get('verify_mode')}; status_code={nav_result.get('status_code')}; composer_match={nav_result.get('composer_match')}; retry_attempt={nav_result.get('retry_attempt')}",
                        level=logging.INFO if nav_result.get("verify_mode") == "strong" else logging.WARNING,
                    )
                else:
                    log(
                        f"({g}) Navigation failed; verify_mode={nav_result.get('verify_mode')}; status_code={nav_result.get('status_code')}; gap_risk_reason={nav_result.get('gap_risk_reason')}; retry_attempt={nav_result.get('retry_attempt')}",
                        level=logging.WARNING,
                    )
            except Exception as e:
                ctx = {"phase": "find_and_access_group", "group": g}
                try:
                    ctx["current_url"] = driver.current_url
                    ctx["page_title"] = driver.title
                except Exception:
                    pass
                log_error(e, context=ctx, extra_message="Lỗi khi tìm nhóm")
                if is_browser_dead_error(e):
                    log(f"Lỗi browser khi tìm nhóm: {str(e)}", level=logging.ERROR)
                    if consecutive_recover_failures < max_recover_failures:
                        new_driver = _recover_browser_and_update_refs(
                            browser_manager,
                            zalo_navigator,
                            crawlers,
                            groups,
                            zalo_auth,
                            target_group=g,
                            recovery_reason="browser_dead_during_navigation",
                        )
                        if new_driver is not None:
                            driver = new_driver
                            nav_result = zalo_navigator.find_and_access_group(group_name=g) or nav_result
                            last_nav_result[g] = nav_result
                            navigation_ok = bool(nav_result.get("ok"))
                            consecutive_recover_failures = 0
                        else:
                            consecutive_recover_failures += 1
                else:
                    consecutive_recover_failures = 0

            crawler = crawlers[g]
            crawler.rotate_session_if_needed()
            processed_count = 0
            if navigation_ok:
                try:
                    processed_count = crawler.crawl_step()
                    consecutive_recover_failures = 0
                except Exception as e:
                    ctx = {"phase": "crawl_step", "group": g}
                    try:
                        ctx["current_url"] = driver.current_url
                        ctx["page_title"] = driver.title
                    except Exception:
                        pass
                    log_error(e, context=ctx, extra_message="Lỗi trong crawl_step")
                    if is_browser_dead_error(e):
                        log(f"Lỗi browser trong crawl_step: {str(e)}", level=logging.ERROR)
                        if consecutive_recover_failures < max_recover_failures:
                            new_driver = _recover_browser_and_update_refs(
                                browser_manager,
                                zalo_navigator,
                                crawlers,
                                groups,
                                zalo_auth,
                                target_group=g,
                                recovery_reason="browser_dead_during_crawl_step",
                            )
                            if new_driver is not None:
                                driver = new_driver
                                consecutive_recover_failures = 0
                            else:
                                consecutive_recover_failures += 1
                    else:
                        log(f"({g}) Lỗi crawl_step: {str(e)}", level=logging.ERROR)
                        consecutive_recover_failures = 0

            backlog_pressure = bool(getattr(crawler, "backlog_pressure", False))
            crawler_possible_gap = bool(getattr(crawler, "possible_gap", False))
            navigation_possible_gap = bool(nav_result.get("possible_gap", False))
            possible_gap = bool(crawler_possible_gap or navigation_possible_gap)

            backlog_trackers[g] = _update_group_backlog_tracker(
                backlog_trackers.get(g),
                backlog_pressure=backlog_pressure,
                possible_gap=possible_gap,
            )
            backlog_trackers[g]["last_verify_mode"] = nav_result.get("verify_mode")
            backlog_trackers[g]["last_gap_risk_reason"] = nav_result.get("gap_risk_reason")
            backlog_trackers[g]["revisit_boost_applied"] = bool(nav_result.get("revisit_boost_hint", False))
            now_ts = time.time()
            for room_name in groups:
                previous = room_state.get(room_name) or {}
                if room_name == g:
                    previous_visits = int(previous.get("consecutive_visits", 0) or 0)
                    room_state[room_name] = {
                        **previous,
                        "last_visited_at": now_ts,
                        "never_visited": False,
                        "starvation_seconds": 0.0,
                        "consecutive_visits": previous_visits + 1 if current_group == room_name else 1,
                        "backlog_pressure": backlog_pressure,
                        "possible_gap": possible_gap,
                        "navigation_possible_gap": navigation_possible_gap,
                        "crawler_possible_gap": crawler_possible_gap,
                        "backlog_hot": bool(backlog_trackers[g].get("backlog_hot", False)),
                        "last_processed_count": processed_count,
                        "last_visible_count": int(getattr(crawler, "last_visible_count", 0) or 0),
                        "last_verify_mode": nav_result.get("verify_mode"),
                        "last_gap_risk_reason": nav_result.get("gap_risk_reason"),
                        "revisit_boost_hint": bool(nav_result.get("revisit_boost_hint", False)),
                        "last_retry_attempt": int(nav_result.get("retry_attempt", 0) or 0),
                        "last_navigation_status_code": nav_result.get("status_code"),
                    }
                else:
                    prev = dict(previous)
                    last_seen = float(prev.get("last_visited_at", 0.0) or 0.0)
                    prev["starvation_seconds"] = max(0.0, now_ts - last_seen) if last_seen else float(policy["starvation_threshold_seconds"])
                    prev["consecutive_visits"] = 0
                    room_state[room_name] = prev

            next_group, selected_by, priority_score = _select_next_group(groups, room_state, current_group=g)
            sleep_s = _select_sleep_seconds(room_state.get(g), policy)

            if selected_by != "round_robin":
                log(
                    f"({g}) fairness scheduler: next={next_group}, selected_by={selected_by}, score={priority_score}, processed={processed_count}, backlog_pressure={backlog_pressure}, possible_gap={possible_gap}, navigation_possible_gap={navigation_possible_gap}, crawler_possible_gap={crawler_possible_gap}, verify_mode={nav_result.get('verify_mode')}, gap_risk_reason={nav_result.get('gap_risk_reason')}, backlog_hot={room_state[g]['backlog_hot']}, consecutive_visits={room_state[g]['consecutive_visits']}",
                    level=logging.INFO,
                )

            next_idx = groups.index(next_group) if next_group in groups else idx
            tracker_snapshot = build_room_switch_tracker_snapshot(
                g,
                backlog_trackers.get(g),
                processed_count=processed_count,
                backlog_pressure=backlog_pressure,
                possible_gap=possible_gap,
                stay_budget=max(1, int(policy["max_consecutive_visits"]) - int(room_state[g]["consecutive_visits"]) + 1),
                next_idx=next_idx,
                sleep_s=sleep_s,
                room_cycle=room_cycle,
                verify_mode=nav_result.get("verify_mode"),
                gap_risk_reason=nav_result.get("gap_risk_reason"),
                navigation_possible_gap=navigation_possible_gap,
                crawler_possible_gap=crawler_possible_gap,
                revisit_boost_hint=bool(nav_result.get("revisit_boost_hint", False)),
                retry_attempt=int(nav_result.get("retry_attempt", 0) or 0),
                navigation_status_code=nav_result.get("status_code"),
            )
            tracker_snapshot["starvation_seconds"] = round(float(room_state[g].get("starvation_seconds", 0.0) or 0.0), 2)
            tracker_snapshot["consecutive_visits"] = int(room_state[g].get("consecutive_visits", 0) or 0)
            tracker_snapshot["selected_by"] = selected_by
            if priority_score is not None:
                tracker_snapshot["priority_score"] = round(float(priority_score), 2)
            log_event("room_switch_tracker", tracker_snapshot, prefix="ROOM_SWITCH_TRACKER", level=logging.INFO)

            current_group = next_group
            idx = next_idx
            time.sleep(sleep_s)

        # Khi dừng: chốt file cho từng group
        # Dùng session_start_time để tên file & phiên phản ánh thời điểm BẮT ĐẦU chạy, không phải lúc kết thúc
        for g, crawler in crawlers.items():
            try:
                with crawler.save_lock:
                    final_path = crawler.save_document(session_start_time)
                if final_path:
                    crawler.docx_handler.process_docx_format(final_path)
            except Exception:
                pass

        return True
    finally:
        try:
            if driver:
                driver.quit()
        except Exception:
            pass

def run_app(times=1):
    """Chạy ứng dụng một số lần nhất định"""
    for i in range(times):
        if is_terminating():
            log(f"Dừng thực thi sau {i}/{times} lượt chạy", level=logging.WARNING)
            break
            
        log(f"Lần chạy thứ {i+1}/{times}")
        
        try:
            # Khởi động chuỗi quy trình
            file_path = asyncio.run(crawl_messages())
            
            if file_path:
                countdown(3)
                browser_manager.close_chrome()
                countdown(3)
                docx_handler = DocxHandler()
                processed_file = docx_handler.process_docx_format(file_path)
                # File đã được gửi trong process_docx_format
        
        except Exception as run_error:
            log(f"Lỗi khi chạy crawler: {str(run_error)}", level=logging.ERROR)
            log_error(run_error, context={"phase": "run_app"}, extra_message="Lỗi khi chạy crawler (run_app)")
            
            # Kiểm tra xem có phải lỗi liên quan đến WebDriver không
            error_str = str(run_error).lower()
            if any(err in error_str for err in ["webdriver", "chrome", "connection", "timeout"]):
                log("Phát hiện lỗi WebDriver, đang khởi động lại toàn bộ...", level=logging.WARNING)
                
                # Gửi thông báo lỗi qua Telegram
                send_notification(build_webdriver_restart_notification())
            
            # Đảm bảo Chrome được đóng
            try:
                browser_manager.close_chrome()
            except:
                pass
            
            # Đợi một chút trước khi thử lại
            countdown(30)
        
        if is_terminating():
            break
            
        countdown(3)
        

def run_capture_structure():
    """
    Chạy Chrome, mở Zalo Web, đăng nhập (nếu cần), lấy cấu trúc trang (selectors, elements)
    và lưu ra file .md + .json trong data/logs/ để sau phát triển thêm tính năng.
    """
    from src.tools.zalo_structure_capture import capture_zalo_structure
    ensure_data_folder()
    driver = None
    try:
        log("Chế độ --capture-structure: khởi động Chrome, mở Zalo Web...", level=logging.INFO)
        driver = browser_manager.get_chrome_driver()
        zalo_navigator = ZaloNavigator(driver)
        zalo_auth = ZaloAuthManager(driver)
        zalo_navigator.open_zalo_web()
        if not zalo_auth.check_login_status():
            log("Chưa đăng nhập. Vui lòng quét QR (hoặc đăng nhập) trong vài phút...", level=logging.WARNING)
            if not zalo_auth.wait_for_login():
                log("Hết thời gian đăng nhập. Thoát.", level=logging.ERROR)
                return
        groups = [g for g in (GROUP_NAMES or []) if str(g).strip()]
        if groups:
            zalo_navigator.find_and_access_group(group_name=groups[0])
        path_md, path_json = capture_zalo_structure(driver)
        log(f"Đã lưu cấu trúc Zalo. Gửi file sau cho dev khi cần phát triển thêm:", level=logging.INFO)
        if path_md:
            log(f"  MD:  {path_md}", level=logging.INFO)
        if path_json:
            log(f"  JSON: {path_json}", level=logging.INFO)
    except Exception as e:
        log(f"Lỗi khi capture cấu trúc: {str(e)}", level=logging.ERROR)
        log_error(e, context={"phase": "run_capture_structure"}, extra_message="Lỗi trong --capture-structure")
    finally:
        if driver:
            try:
                driver.quit()
            except Exception:
                pass
        browser_manager.close_chrome()


def main():
    """Hàm chính điều khiển toàn bộ ứng dụng"""
    try:
        # Chế độ lấy cấu trúc Zalo Web (để phát triển thêm tính năng)
        if "--capture-structure" in sys.argv:
            init_signal_handlers()
            ensure_data_folder()
            run_capture_structure()
            return
        
        # Khởi tạo xử lý tín hiệu
        init_signal_handlers()
        
        # Log timezone đang sử dụng
        from src.utils.config import TIMEZONE, TIMEZONE_NAME
        if TIMEZONE:
            log(f"Timezone được cấu hình: {TIMEZONE_NAME}", level=logging.INFO)
        else:
            import time
            offset = time.timezone if (time.daylight == 0) else time.altzone
            offset_hours = offset / -3600
            log(f"Timezone: Hệ thống (UTC{offset_hours:+.0f})", level=logging.INFO)
        
        # Đảm bảo thư mục dữ liệu tồn tại
        ensure_data_folder()

        # Chỉ bật Crawlbot Control ở chế độ non-headless
        if not HEADLESS:
            start_control_window()
        
        # Kiểm tra kết nối Telegram
        telegram_connected = check_telegram_connection()

        # Thêm vào sau phần kiểm tra kết nối Telegram thành công
        if telegram_connected:
            log("Kết nối Telegram thành công!")
            # Gửi thông báo khởi động về các kênh
            send_notification("🚀 Hệ thống Zalo Crawler đã khởi động")
            
            # Thử gửi cảnh báo với chat_id cụ thể
            try:
                log("Đang gửi tin nhắn cảnh báo test...", level=logging.INFO)
                from src.notification.telegram import ALERT_CHAT_ID
                send_alert(build_alert_ready_notification(), chat_id=ALERT_CHAT_ID)
                log(f"Đã gửi tin nhắn test đến {ALERT_CHAT_ID}", level=logging.INFO)

            except Exception as e:
                log(f"Lỗi khi gửi tin nhắn test: {str(e)}", level=logging.ERROR)

        else:
            log("Không thể kết nối đến Telegram, thông báo sẽ chỉ ghi vào log", level=logging.WARNING)
        
        # Nếu cấu hình nhiều nhóm, chạy song song theo nhóm
        groups = [g for g in (GROUP_NAMES or []) if str(g).strip()]
        if len(groups) > 1:
            log(f"Chạy chế độ multi-group: {groups}", level=logging.INFO)
            run_multi_group_single_session(groups)
        else:
            # Single-group (giữ nguyên hành vi cũ)
            times_to_run = 1  # Mặc định chạy 1 lần
            run_app(times_to_run)
        
    except KeyboardInterrupt:
        # KeyboardInterrupt sẽ được xử lý bởi signal_handler
        pass
    except Exception as e:
        error_message = f"❌ Lỗi không xử lý được: {str(e)}"
        log(error_message, level=logging.CRITICAL)
        log_error(e, context={"phase": "main"}, extra_message="Lỗi không xử lý được trong main")
        send_error(error_message)
    finally:
        # Dừng browser
        try:
            browser_manager.close_chrome()
        except:
            pass
        
        log("Hệ thống đã dừng hoàn toàn.")

if __name__ == "__main__":
    main()
