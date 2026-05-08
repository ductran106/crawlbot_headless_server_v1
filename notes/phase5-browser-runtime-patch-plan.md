# Phase 5A/5B/5C Browser + Runtime Stability Patch Plan

Repo: `/home/farm4bot/ai-workspace/repos/crawlbot_portable_scheduler_lab`

Scope của note này:
- chỉ lập kế hoạch patch, **chưa sửa code**
- tập trung vào độ ổn định browser/runtime khi chạy **3-room mode**
- ưu tiên file theo thứ tự:
  1. `src/browser/navigation.py`
  2. `src/browser/driver.py`
  3. `main.py`
  4. `src/crawler/message_crawler.py`

---

## 0. Executive summary

Scheduler fairness ở Phase 1-4 đã khá ổn, nhưng lane 3-room vẫn còn nguy cơ miss/đứng hình nếu browser layer không đủ chắc. Sau khi review code hiện tại, các vấn đề lớn nhất không còn nằm ở scoring/switching nữa mà nằm ở **navigation verification**, **browser recovery lifecycle**, và **runtime loop behavior khi room chuyển nhanh**.

### Kết luận chính

**Phase 5 nên chia thành 3 lớp:**

- **Phase 5A — Navigation hardening**
  - loại bỏ false-positive “đã vào đúng room”
  - bỏ các điểm dễ phát sinh NameError/verify lệch
  - chuẩn hóa search → click → verify → warmup

- **Phase 5B — Driver/runtime recovery hardening**
  - biến restart/recover thành flow có step rõ ràng, có kiểm tra health/login/group-ready
  - tránh recovery nửa vời khiến main loop tưởng browser đã sống lại nhưng thực ra chưa usable

- **Phase 5C — 3-room crawl-loop stability hardening**
  - giảm dwell cost còn lại ở mỗi room
  - chặn refresh/recovery quá tay trong multi-room mode
  - thêm observability/test để bắt được regressions ngoài thực địa

---

## 1. Root causes đã xác định

## 1.1 `src/browser/navigation.py` có các điểm verify chưa hoàn chỉnh

### Root cause A — `find_and_access_group()` có thể trả `True` dù chưa verify đúng room

**Block:** `find_and_access_group()` phần verify sau click.

Hiện tại:
- click vào `.conv-item`
- chỉ đợi `.header-title` xuất hiện
- nếu header có mặt nhưng verify lỗi/non-browser exception thì vẫn `return True`

Hệ quả ở 3-room mode:
- khi switch room nhanh, DOM/search result có thể trễ hoặc click nhầm item gần giống tên
- scheduler nghĩ đã vào room A nhưng thật ra vẫn ở room cũ / room khác
- `crawl_step()` sau đó mới phát hiện mismatch, làm tăng dwell time và tạo vòng reconnect thừa
- với 3 room, sai một nhịp như vậy dễ kéo starvation room còn lại

### Root cause B — navigation đang có helper dang dở / không đồng nhất

**Các block liên quan:**
- `_normalize_group_text()` dùng `re` nhưng file không import `re`
- `_clear_search_box()` dùng `Keys` nhưng file không import `Keys`
- `reconnect_to_group()` gọi `_wait_until_header_matches()` nhưng method này **không tồn tại** trong file
- đã có `_verify_current_group_title()` nhưng lại không được tận dụng thống nhất

Lưu ý:
- `py_compile` vẫn pass vì các tên này chỉ nổ khi chạy vào code path thực tế
- đây là **runtime bug cứng**, không phải giả thuyết

Hệ quả ở 3-room mode:
- reconnect path là path nóng nhất khi browser rung lắc hoặc room verify fail
- chỉ cần vào nhánh này là có thể phát sinh exception runtime, làm recovery khó đoán

### Root cause C — thao tác search box chưa được chuẩn hóa

**Block:** `find_and_access_group()` và `reconnect_to_group()`.

Hiện tại:
- có lúc dùng `.clear()`, có helper `_clear_search_box()` nhưng không dùng
- search result có thể còn residue query cũ trong SPA/input state

Hệ quả:
- room switching nhanh 3-room dễ gặp query chồng / kết quả stale
- tăng xác suất click nhầm conversation

### Root cause D — warmup sau click còn cứng và hơi đắt

**Block:** phần `time.sleep(2)` + scroll up/down buffer trong `find_and_access_group()`.

Hiện tại:
- sau mỗi lần vào room đều ngủ cứng 2s rồi scroll 2 vòng
- behavior này hợp lý cho an toàn, nhưng khá đắt nếu mỗi cycle đều chạy

Hệ quả:
- 3-room mode tăng revisit latency tổng thể
- nếu room switching dày, browser phải liên tục render + scroll + sleep dù không cần sâu đến vậy

---

## 1.2 `src/browser/driver.py` recovery đang usable nhưng còn “quá coarse”

### Root cause E — `recover_session()` chỉ đảm bảo page mở lại, chưa đảm bảo lane đã usable

**Function:** `BrowserManager.recover_session()`.

Hiện tại flow:
- mở `https://chat.zalo.me`
- chờ `document.readyState == complete`
- sleep 8s
- trả `True`

Vấn đề:
- với Zalo SPA, `readyState=complete` chưa có nghĩa search box/login state đã sẵn sàng
- sleep 8s là fixed wait, vừa chậm vừa không chắc chắn
- caller phải tự check login lại, nhưng pattern chưa đồng nhất ở mọi nơi

Hệ quả:
- restart xong nhưng navigator/crawler vào quá sớm → fail giả
- hoặc sleep quá lâu → dwell/recovery latency tăng mạnh, đặc biệt khi 3-room đang nóng

### Root cause F — restart chưa reset/rehydrate đủ state dùng cho long-running session

**Functions:** `get_chrome_driver()`, `restart_driver()`, `get_driver()`.

Vấn đề cần hardening:
- không có bước clear window handle assumptions / tab assumptions sau restart
- chưa có helper “driver usable for Zalo” tách biệt với “webdriver responds to execute_script”
- `check_driver_health()` hiện chỉ là `execute_script("return document.readyState")`

Hệ quả:
- driver có thể “sống” về mặt Selenium nhưng chưa usable cho workflow Zalo
- main loop/crawler recovery phải tự mò tiếp, gây split responsibility

### Root cause G — close/restart flow có thể để lại residue process hoặc profile contention ngắn hạn

**Blocks:** `_terminate_related_chrome_processes()`, `restart_driver()`.

Nhận xét:
- logic terminate theo profile/port là đúng hướng
- nhưng restart chưa có một bước wait/check nhỏ xác nhận port/profile đã nhả xong trước khi dựng lại

Rủi ro ở 3-room soak:
- recovery liên tiếp trong thời gian ngắn dễ sinh start failure kiểu profile locked / devtools port reuse / zombie chrome

---

## 1.3 `main.py` multi-room runtime loop đã tốt hơn trước nhưng recovery contract còn chưa chặt

### Root cause H — `_recover_browser_and_update_refs()` chỉ recover đến mức login-ready, chưa reopen/verify lại room cụ thể

**Function:** `_recover_browser_and_update_refs()`.

Hiện tại:
- restart driver
- sync refs
- `browser_manager.recover_session()`
- check login / wait_for_login
- trả driver mới

Thiếu:
- chưa reopen room mục tiêu ngay trong recovery helper
- chưa verify navigation usable state trước khi vòng chính tiếp tục

Hệ quả:
- ngay sau recover, loop tiếp tục `find_and_access_group(g)` ở vòng kế tiếp
- recovery bị tách thành hai nửa: “browser sống lại” ở helper, “room usable” ở loop
- nếu loop bị nhiễu hoặc browser vừa hồi, sẽ tăng số lần fail/retry liên tiếp

### Root cause I — fail path của `find_and_access_group()` không short-circuit rõ trong main loop

**Block:** trong `run_multi_group_single_session()`.

Hiện tại:
- gọi `zalo_navigator.find_and_access_group(group_name=g)`
- nếu method trả `False` nhưng không throw browser-dead, code vẫn tiếp tục xuống `crawler.crawl_step()`

Hệ quả:
- crawler lại phải tự check mismatch/reconnect thêm một lần
- gây duplicate recovery work
- làm room cycle tốn thời gian hơn trong 3-room mode

### Root cause J — có symbol chưa tồn tại ở nhánh single-run

**Block:** `run_app()` gọi `build_webdriver_restart_notification()` nhưng không import/không thấy định nghĩa.

Dù đây không phải lane chính của 3-room mode, nó cho thấy runtime surface còn dangling references. Nên fix luôn trong Phase 5 để giảm debt.

---

## 1.4 `src/crawler/message_crawler.py` vẫn còn vài điểm gây lane churn trong 3-room mode

### Root cause K — `crawl_step()` vẫn có path xử lý hơi nặng sau khi đã fairness-first

**Function:** `crawl_step()`.

Hiện tại:
- check status
- nếu lệch group thì navigation lại
- chờ ổn định
- iterate chat items tối đa 100
- append file từng message
- save DB theo batch cuối vòng
- scroll cuối vòng

Điểm còn đắt:
- `append_single_message_to_autosave()` vẫn mở/ghi/move docx cho từng tin nhắn
- status check + verify còn lặp nhiều khi navigation layer chưa đủ chắc
- `wait_for_messages_stable()` vẫn là polling count-based khá mù với SPA

Hệ quả:
- room nóng có thể giữ lane lâu hơn mong muốn
- room lạnh bị revisit chậm hơn dù scheduler logic đã công bằng hơn

### Root cause L — recovery/refresh policy trong crawler vẫn hơi “single-room oriented”

**Blocks:**
- `start_crawling()` periodic refresh mỗi 5 phút
- refresh khi 60s không có data mới
- `_recover_from_status()` có thể refresh/reconnect khá mạnh tay

Trong `run_multi_group_single_session()`, path chính dùng `crawl_step()` nên đỡ hơn nhiều, nhưng các primitive recovery trong class vẫn đang được thiết kế theo tư duy room đơn chạy lâu trong 1 loop.

Hệ quả:
- khi tái dùng/reopen path ở multi-room mode, dễ bị over-recovery

### Root cause M — `wait_for_messages_stable()` chỉ nhìn count, chưa nhìn “header/group unchanged + short settle”

**Function:** `wait_for_messages_stable()`.

Hiện tại:
- chỉ cần `.chat-item` count đứng yên 2 lần là pass

Vấn đề:
- count ổn định chưa chắc room header/render đã xong
- ngược lại, count còn nhảy nhẹ nhưng room đã usable thì vẫn phải đợi

Hệ quả:
- khi room chuyển nhanh giữa 3 tab logic trong cùng 1 SPA, polling này vừa thiếu tin cậy vừa tiêu thời gian

---

## 2. Concrete patch plan theo phase

---

## Phase 5A — Navigation hardening (`src/browser/navigation.py`)

## 5A.1. Hoàn thiện helper layer và loại dangling references

### Sửa các import/helper sau

**File:** `src/browser/navigation.py`

#### A. Thêm import còn thiếu
- thêm `import re`
- thêm `from selenium.webdriver.common.keys import Keys`

#### B. Thay `_wait_until_header_matches()` bằng helper thật sự tồn tại
Có 2 lựa chọn, nên chọn **một** để thống nhất:

**Khuyến nghị:**
- tạo method mới `_wait_until_header_matches(group_name, timeout=6, stable_checks=2)`
- dùng method này cho cả `find_and_access_group()` và `reconnect_to_group()`

Method nên làm:
- poll header text trong timeout ngắn
- normalize text qua `_matches_target_group()`
- yêu cầu match ổn định 1-2 lần liên tiếp
- trả `(matched: bool, header_text: str)`

#### C. Tái sử dụng `_clear_search_box()` thật sự
- bỏ `.clear()` trực tiếp ở search input
- luôn dùng `_clear_search_box(search_box)` trước khi gõ query mới
- sau đó send_keys query mục tiêu
- cân nhắc trigger input event bổ sung nếu cần

### Lý do
Đây là patch “đập nền”. Không làm bước này thì reconnect path vẫn dễ nổ runtime bất ngờ.

---

## 5A.2. Siết contract của `find_and_access_group()`

### Function cần sửa
- `ZaloNavigator.find_and_access_group()`

### Thay đổi đề xuất

#### A. Chuyển từ “header xuất hiện là đủ” sang “header match target mới pass”
Sau khi click conversation item:
- gọi `_wait_until_header_matches(group_name, timeout=6)`
- nếu `matched_header == False`:
  - capture fail artifact
  - log rõ `clicked_item`, `header_text`, `top_results`
  - **return False**, không `return True`

#### B. Chỉ giữ `return True` khi đã verify đúng target group
Điểm này cực quan trọng cho 3-room mode.

#### C. Tách warmup thành helper riêng
Tạo helper kiểu:
- `_warmup_room_after_open(scroll_rounds=1, settle_seconds=0.5)`

Khuyến nghị behavior:
- thay `time.sleep(2)` bằng settle ngắn hơn, ví dụ 0.4-0.8s
- scroll buffer giảm mặc định còn 1 vòng cho multi-room navigation path
- nếu sau này cần deep warmup cho single-room thì expose knob riêng

### Kỳ vọng sau patch
- main loop không còn nhận false-positive “đã vào room”
- mismatch/reconnect giảm rõ
- revisit latency 3-room giảm vì bớt warmup cứng

---

## 5A.3. Chuẩn hóa logic match tên group

### Functions liên quan
- `_normalize_group_text()`
- `_target_tokens()`
- `_matches_target_group()`
- `find_and_access_group()`
- `reconnect_to_group()`
- `check_zalo_status()` trong crawler cũng nên reuse cùng semantics

### Thay đổi đề xuất
- navigation layer và crawler layer dùng chung một chuẩn normalize/match
- tránh chỗ match bằng `target in item_lower`, chỗ khác lại split token thô
- nếu có thể, gom về helper chung trong navigation hoặc util riêng

### Lý do
3-room mode có xác suất đụng các room tên gần giống nhau cao hơn. Match semantics lệch giữa navigation và crawler sẽ tạo behavior khó debug.

---

## Phase 5B — Driver + recovery hardening (`src/browser/driver.py`, `main.py`)

## 5B.1. Nâng `recover_session()` từ page-ready thành app-ready hơn

### Function cần sửa
- `BrowserManager.recover_session()`

### Thay đổi đề xuất

#### A. Thay fixed sleep 8s bằng wait có điều kiện
Flow khuyến nghị:
1. `driver.get("https://chat.zalo.me")`
2. chờ `document.readyState == complete`
3. chờ **một trong hai** marker xuất hiện:
   - `#contact-search-input` (đã login)
   - `.qrcode img` (cần login)
4. chỉ nếu cả hai marker chưa ra trong timeout thì mới fallback sleep ngắn + log warning

#### B. Trả metadata recovery thay vì chỉ bool (khuyến nghị nếu chấp nhận thay contract)
Ví dụ:
```python
{
  "success": True,
  "page_ready": True,
  "login_marker_seen": True,
  "qr_marker_seen": False,
}
```

Nếu muốn ít invasive hơn thì vẫn trả bool, nhưng ít nhất phải log step rõ.

### Lý do
Driver-level recovery nên đảm bảo browser đã quay về trạng thái có thể phân loại tiếp, không chỉ “tab mở được”.

---

## 5B.2. Thêm khái niệm `check_driver_health()` vs `check_zalo_ready()`

### File
- `src/browser/driver.py`
- được gọi từ `main.py` và/hoặc `message_crawler.py`

### Thay đổi đề xuất

#### A. Giữ `check_driver_health()` cho mức transport/WebDriver
- current `execute_script("return document.readyState")` vẫn giữ

#### B. Thêm helper mới kiểu `check_zalo_surface_ready()`
Nên check:
- current URL còn là Zalo/chat surface hợp lệ
- hoặc thấy marker search input / QR
- hoặc ít nhất body + app shell đã hiện

### Lý do
Phân biệt:
- **driver còn sống**
- **ứng dụng Zalo sẵn sàng cho navigation**

3-room stability cần cả hai, không chỉ cái đầu.

---

## 5B.3. Siết `_recover_browser_and_update_refs()` thành recovery trọn gói hơn

### Function cần sửa
- `main._recover_browser_and_update_refs(...)`

### Thay đổi đề xuất

#### A. Nhận thêm `target_group` hoặc `resume_group`
Sau khi:
- restart driver
- sync refs
- recover session
- verify login

thì helper nên:
- `find_and_access_group(target_group)` luôn nếu caller có room hiện tại
- chỉ trả driver mới khi target room đã usable

#### B. Nếu reopen room fail, log failure step riêng
Ví dụ step values:
- `restart_driver`
- `recover_session`
- `wait_login`
- `reopen_group`
- `verify_group`

#### C. Reset hoặc refresh state liên quan crawler sau recovery
Khuyến nghị reset nhẹ các field sau của crawler room hiện tại hoặc tất cả crawler:
- `last_status_reason`
- `group_reconnect_fail_streak`
- `login_unknown_streak`
- `last_health_check`
- `last_reload_time`

### Lý do
Recovery hiện tại còn chia nửa browser/nửa room. Với 3-room mode, recovery cần là atomic unit càng nhiều càng tốt.

---

## 5B.4. Main loop phải short-circuit nếu navigation fail

### Function cần sửa
- `run_multi_group_single_session()` trong `main.py`

### Thay đổi đề xuất

#### A. Xử lý rõ return value của `find_and_access_group()`
Pseudo-flow khuyến nghị:
```python
nav_ok = zalo_navigator.find_and_access_group(group_name=g)
if not nav_ok:
    mark room visit as failed/minimal
    choose next action:
        - nếu là browser-dead exception -> recovery như hiện tại
        - nếu là search/verify fail bình thường -> log + short sleep + continue
    continue
```

#### B. Không gọi `crawler.crawl_step()` ngay sau một navigation fail non-exception
Điểm này sẽ cắt được 1 vòng duplicate verify/reconnect rất tốn ở 3-room mode.

### Lý do
Main loop là coordinator; nếu navigation layer đã báo chưa vào room được thì crawler không nên bị đẩy vào lane đó nữa.

---

## 5B.5. Dọn runtime debt ở `run_app()`

### Function/block cần sửa
- `run_app()` trong `main.py`

### Thay đổi đề xuất
- import hoặc thay thế `build_webdriver_restart_notification()` bằng template thực sự tồn tại
- nếu single-run path không còn là path ưu tiên, vẫn nên sửa để tránh runtime debt tồn tại âm thầm

---

## Phase 5C — 3-room crawl/runtime stability hardening (`src/crawler/message_crawler.py`, `main.py`)

## 5C.1. Làm `crawl_step()` nhẹ hơn nữa cho multi-room mode

### Function cần sửa
- `MessageCrawler.crawl_step()`

### Thay đổi đề xuất

#### A. Hoãn/giảm tần suất autosave docx per-message
Hiện tại mỗi tin nhắn mới đều gọi:
- `append_single_message_to_autosave(data_ok)`

Khuyến nghị:
- chuyển sang batch append theo `db_batch` hoặc `message_batch` cuối `crawl_step()`
- hoặc ít nhất chỉ append file 1 lần / step nếu có tin mới

#### B. Giữ DB batch như hiện tại, nhưng đồng bộ thêm autosave batch
Vì hiện DB đã được tối ưu theo step, docx IO đang trở thành bottleneck còn sót lại.

### Lý do
Trong 3-room mode, IO file Word per-message là rất đắt và không cần thiết để đảm bảo anti-miss.

---

## 5C.2. Nâng `wait_for_messages_stable()` thành settle heuristic hợp hơn cho multi-room

### Function cần sửa
- `wait_for_messages_stable()`

### Thay đổi đề xuất

#### Option khuyến nghị
Giữ function nhưng đổi heuristic:
- timeout ngắn theo room_count như hiện tại
- ngoài `chat-item count`, check thêm một dấu hiệu room đã ổn như:
  - header còn đúng target room
  - ít nhất chat container tồn tại
  - count không giảm/bật loạn trong 2 poll gần nhất

#### Tối ưu thêm
- polling interval có thể giảm còn 0.25-0.35s ở mode 3-room
- required stable checks có thể là 1-2 tùy timeout ngắn

### Lý do
Count-only polling hiện hơi thô; với SPA room switching nhanh, cần settle heuristic chứ không chỉ count heuristic.

---

## 5C.3. Thêm mode-aware recovery trong crawler primitives

### File/function
- `MessageCrawler.__init__`
- `_recover_from_status()`
- `refresh_page_safely()`
- có thể thêm cờ `multi_room_mode`

### Thay đổi đề xuất
- khi `room_count >= 3`, hạn chế các action kiểu refresh/reconnect nặng trong crawler-level path
- ưu tiên trả lỗi/status ra cho main loop coordinator quyết định
- nghĩa là: multi-room mode nên có **coordinator-owned recovery**, không để từng crawler tự quẫy nhiều

### Lý do
3-room mode cần một nơi quyết định recovery để tránh nhiều tầng cùng cố cứu browser một lúc.

---

## 5C.4. Thêm observability cho runtime stability

### `main.py`
Bổ sung vào `ROOM_SWITCH_TRACKER` hoặc event mới các field:
- `navigation_ok`
- `navigation_verify_ms`
- `crawl_step_ms`
- `recovery_attempted`
- `recovery_success`
- `recovery_step`
- `group_open_fail_reason`

### `message_crawler.py`
Bổ sung event/log khi:
- stable wait timeout nhưng vẫn tiếp tục
- reconnect verify fail
- autosave batch duration vượt ngưỡng

### Lý do
Phase 5 là tối ưu runtime thực địa; nếu không đo timing breakdown thì rất khó tune tiếp.

---

## 3. File-by-file exact patch targets

## 3.1 `src/browser/navigation.py` — ưu tiên cao nhất

### Functions/blocks cần sửa trực tiếp
1. import section đầu file
   - thêm `re`
   - thêm `Keys`

2. `_clear_search_box()`
   - biến thành đường chuẩn duy nhất để xóa query

3. thêm mới `_wait_until_header_matches()`
   - hoặc đổi caller sang `_verify_current_group_title()` nhưng nên có phiên bản polling/stable wait thực sự

4. `find_and_access_group()`
   - thay verify block sau click
   - return `False` khi header không match target
   - tách warmup helper, giảm fixed sleep

5. `reconnect_to_group()`
   - bỏ dangling call hiện tại sang helper thật
   - đồng bộ hóa match/verify semantics với `find_and_access_group()`

### Mức độ rủi ro
- **Medium**
- vì đây là path nóng nhất của app
- nhưng lợi ích cao, và patch có thể test tốt bằng unit tests/mock waits

---

## 3.2 `src/browser/driver.py` — ưu tiên cao thứ hai

### Functions/blocks cần sửa trực tiếp
1. `check_driver_health()`
   - giữ nguyên hoặc mở rộng nhẹ, nhưng đừng overload trách nhiệm

2. thêm helper mới:
   - `check_zalo_surface_ready()` hoặc tên tương đương

3. `recover_session()`
   - bỏ fixed sleep 8s đơn thuần
   - chờ marker app/login/QR
   - log step rõ

4. `restart_driver()`
   - cân nhắc thêm wait ngắn sau quit/kill trước khi dựng lại
   - log rõ attempt + failure reason

### Mức độ rủi ro
- **Medium**
- sửa đúng thì recovery sẽ ổn định hơn rõ
- nhưng nếu sửa quá mạnh tay có thể ảnh hưởng cả single-room path

---

## 3.3 `main.py` — ưu tiên cao thứ ba

### Functions/blocks cần sửa trực tiếp
1. `_recover_browser_and_update_refs()`
   - thêm reopen/verify target room
   - log step-specific result

2. `run_multi_group_single_session()`
   - short-circuit khi navigation fail
   - tách navigation failure khỏi crawl failure trong tracker/observability

3. `run_app()`
   - dọn undefined notification builder

### Mức độ rủi ro
- **Medium-Low**
- vì behavior chính đã được structure khá rõ
- chủ yếu là siết contract giữa coordinator và worker

---

## 3.4 `src/crawler/message_crawler.py` — ưu tiên sau cùng nhưng impact lớn trên dwell time

### Functions/blocks cần sửa trực tiếp
1. `wait_for_messages_stable()`
   - nâng heuristic

2. `crawl_step()`
   - batch autosave/docx writes
   - log timing per step
   - tránh recovery lồng nhau khi navigation vừa fail ở main loop

3. `_recover_from_status()` / `refresh_page_safely()`
   - mode-aware behavior khi `room_count >= 3`

### Mức độ rủi ro
- **Medium**
- vì liên quan data persistence và alerting path
- nên patch sau khi navigation/driver contract đã chắc

---

## 4. Patch sequence khuyến nghị

## Step 1 — Navigation layer first
- fix imports/helper dang dở
- thống nhất verify contract
- thêm tests navigation

## Step 2 — Driver recovery second
- upgrade `recover_session()`
- thêm readiness helper
- thêm tests recovery surface

## Step 3 — Main loop contract third
- short-circuit navigation fail
- make recovery atomic hơn
- thêm event fields / tracker fields

## Step 4 — Crawler cost reduction fourth
- batch autosave
- improve stable wait heuristic
- mode-aware recovery behavior

## Step 5 — soak-test guided tuning
- chạy 3-room profile
- đọc `ROOM_SWITCH_TRACKER` + recovery logs
- tune timeout nhỏ sau cùng, không tune từ đầu

---

## 5. Suggested tests

Repo hiện đã có nền test khá tốt (`test_message_crawler_*`, `test_navigation_login_state.py`, `test_portable_long_run_recovery.py`). Phase 5 nên thêm/cập nhật như sau.

## 5.1 Tests cho `navigation.py`

### A. `tests/test_navigation_group_access.py` (mới)
Nên cover:
- `find_and_access_group()` trả `False` khi click xong nhưng header không match target
- `find_and_access_group()` chỉ trả `True` khi header match target
- `reconnect_to_group()` không nổ runtime vì `_wait_until_header_matches` missing nữa
- `_clear_search_box()` được gọi trước khi gõ query mới
- normalization match pass với tên có dấu/khoảng trắng/ký tự đặc biệt nhẹ

### B. Mở rộng `tests/test_navigation_login_state.py`
Thêm case:
- browser-dead khi verify header phải re-raise
- search empty path tạo fail artifact/log đúng reason

---

## 5.2 Tests cho `driver.py`

### A. `tests/test_browser_driver_recovery.py` (mới)
Cover:
- `recover_session()` pass khi search input xuất hiện
- `recover_session()` pass khi QR xuất hiện
- `recover_session()` fail/log warning khi cả hai marker không lên trong timeout
- `restart_driver()` retry đúng số lần khi driver create fail tạm thời

### B. `tests/test_browser_driver_process_cleanup.py` (nếu cần)
Mock `psutil` để verify:
- chỉ terminate process liên quan profile/port
- không quét giết chrome bừa

---

## 5.3 Tests cho `main.py`

### A. `tests/test_multi_room_browser_recovery.py` (mới)
Cover:
- `_recover_browser_and_update_refs()` sync driver refs cho navigator/crawlers
- helper chỉ báo success khi login ok + reopen đúng target group
- nếu navigation reopen fail thì recovery result step=`reopen_group`

### B. `tests/test_scheduler_navigation_short_circuit.py` (mới)
Cover:
- khi `find_and_access_group()` trả `False`, loop không gọi `crawl_step()` cho room đó

---

## 5.4 Tests cho `message_crawler.py`

### A. mở rộng `tests/test_message_crawler_crawl_step.py`
Thêm case:
- `crawl_step()` batch autosave 1 lần/step thay vì per-message
- `wait_for_messages_stable()` timeout ngắn ở 3-room vẫn cho phép tiếp tục
- nếu main loop đã verify navigation fail, crawler không tự over-recover trong cùng nhịp

### B. mở rộng `tests/test_message_crawler_recovery.py`
Thêm case:
- multi-room mode ưu tiên coordinator recovery thay vì refresh lặp
- reconnect verify fail tăng đúng streak nhưng không spam recovery action

### C. mở rộng `tests/test_portable_long_run_recovery.py`
Thêm scenario:
- browser restart giữa lúc room A nóng, room B/C đang chờ
- system recover xong quay lại room target mà không stuck ở login-ready-only state

---

## 6. Risk notes

## Risk 1 — Verify chặt hơn có thể làm tăng số lần `find_and_access_group()` trả `False`
Điều này là **đúng** trong ngắn hạn, vì trước đó code đang có false-positive. Sau patch có thể thấy fail nhiều hơn trên log, nhưng đó là fail thật được lộ ra, không phải regression nếu main loop xử lý đúng.

## Risk 2 — Giảm warmup quá mạnh có thể làm miss tin nhắn mới render chậm
Vì vậy nên:
- giảm từ từ
- default multi-room warmup nhẹ hơn, nhưng vẫn có 1 round scroll/settle
- soak-test để tune

## Risk 3 — Batch autosave thay cho per-message có thể thay đổi durability semantics
Nên giữ nguyên DB batch + add flush-at-end-of-step + final save lock. Nếu lo dữ liệu, có thể cho `autosave batch per step` thay vì `per N seconds`.

## Risk 4 — Recovery contract thay đổi có thể làm một số test cũ fail
Đây là expected refactor cost. Nên sửa test theo contract mới thay vì giữ contract mơ hồ cũ.

## Risk 5 — Driver readiness helper nếu quá strict có thể làm restart chậm
Vì vậy timeout nên ngắn, fallback log rõ, không block quá lâu.

---

## 7. Definition of done cho Phase 5A/5B/5C

### Done cho 5A
- không còn dangling runtime references trong `navigation.py`
- `find_and_access_group()` và `reconnect_to_group()` chỉ success khi verify đúng target group
- search box clearing và group matching thống nhất

### Done cho 5B
- browser recovery không chỉ “mở lại tab” mà đạt mức login/app-ready
- main recovery helper có step-specific outcome
- navigation fail không kéo crawler vào verify thừa

### Done cho 5C
- 3-room mode giảm dwell cost thêm một nấc
- autosave/docx IO không còn per-message trong `crawl_step()`
- có timing/observability đủ để đọc soak-test thực tế

### Done cho toàn Phase 5
- unit tests mới xanh
- regression tests hiện có vẫn xanh sau cập nhật hợp lý
- soak-test 3-room cho log cho thấy:
  - ít reconnect thừa hơn
  - ít browser recovery loop hơn
  - revisit latency ổn định hơn
  - không còn false-positive room-open dẫn tới crawl sai room

---

## 8. Khuyến nghị triển khai thực tế

Nếu triển khai ngay sau note này, em khuyến nghị thứ tự commit như sau:

1. **Commit 1:** `navigation.py` hardening + navigation tests
2. **Commit 2:** `driver.py` recovery readiness + driver tests
3. **Commit 3:** `main.py` recovery contract + short-circuit tests
4. **Commit 4:** `message_crawler.py` batch autosave + stable wait heuristic + crawler tests
5. **Commit 5:** 3-room soak-test notes / env tuning update nếu cần

Cách này giúp isolate regression dễ nhất.

---

## 9. Most important exact fixes to not miss

Nếu cần bản ultra-short checklist để code ngay, đây là 8 mục quan trọng nhất:

1. `navigation.py`: import `re`
2. `navigation.py`: import `Keys`
3. `navigation.py`: implement `_wait_until_header_matches()` thật sự
4. `navigation.py`: `find_and_access_group()` phải `return False` khi verify header fail
5. `navigation.py`: dùng `_clear_search_box()` nhất quán trước mọi search
6. `driver.py`: `recover_session()` phải chờ marker search/QR thay vì sleep 8s cứng
7. `main.py`: nếu navigation trả `False`, **đừng gọi** `crawler.crawl_step()` trong nhịp đó
8. `message_crawler.py`: bỏ autosave docx per-message trong `crawl_step()`, chuyển sang batch per-step

---

## 10. Final assessment

Repo lab hiện đã đi đúng hướng ở scheduler fairness. Điểm cần xử lý tiếp để 3-room mode thật sự ổn định không còn là “chọn room nào”, mà là:
- **mở đúng room một cách đáng tin**
- **khôi phục browser thành usable state thay vì chỉ alive state**
- **giảm chi phí runtime còn sót trong mỗi room visit**

Nếu phải chọn đúng một file để làm đầu tiên, em chọn **`src/browser/navigation.py`**. Đây là chỗ có tỷ lệ “fix ít nhưng giảm nhiễu toàn hệ thống nhiều” cao nhất.
