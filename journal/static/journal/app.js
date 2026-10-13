const MONTHS = ["Январь","Февраль","Март","Апрель","Май","Июнь","Июль","Август","Сентябрь","Октябрь","Ноябрь","Декабрь"];
    const MONTHS_GEN = ["января","февраля","марта","апреля","мая","июня","июля","августа","сентября","октября","ноября","декабря"];
    const DAYS = ["Вс","Пн","Вт","Ср","Чт","Пт","Сб"];

    const BOOT = JSON.parse(document.getElementById("bootstrap-data").textContent);
    let LESSONS = BOOT.journal_lessons || {};
    let canEdit = !!BOOT.can_edit;
    let autoAttend = !!BOOT.auto_attend;
    let pendingCount = Number(BOOT.pending_count || 0);
    const GROUPS = BOOT.groups || [];
    const UNI = BOOT.uni || [];
    const UNI_SVG = BOOT.uni_svg || {};
    const GRADES = BOOT.grades || [];
    const STUDENT = BOOT.student || {};

    let selected = (function () {
        var d = new Date();
        return new Date(d.getFullYear(), d.getMonth(), d.getDate());
    })();
    let pickerCursor = new Date(selected.getFullYear(), selected.getMonth(), 1);
    let pickerTarget = "journal";
    let activeGroup = GROUPS.find(function (g) { return g.id === BOOT.default_group; }) || GROUPS[0] || { id: "", name: "", blurb: "", lessons: {} };
    if (activeGroup && activeGroup.lessons) {
        LESSONS = activeGroup.lessons;
    }
    const HOUR_H = 50;
    const HOUR_START = 9;
    const HOUR_END = 22;

    const $days = document.getElementById("days");
    const $cards = document.getElementById("cards");
    const $weekTitle = document.getElementById("weekTitle");
    const $datePillText = document.getElementById("datePillText");
    const $fab = document.getElementById("fab");

    function pad(n) { return String(n).padStart(2, "0"); }

    function iso(d) {
        return d.getFullYear() + "-" + pad(d.getMonth() + 1) + "-" + pad(d.getDate());
    }

    function copy(d) { return new Date(d.getFullYear(), d.getMonth(), d.getDate()); }

    function mondayOf(d) {
        const x = copy(d);
        const day = x.getDay();
        const diff = day === 0 ? -6 : 1 - day;
        x.setDate(x.getDate() + diff);
        return x;
    }

    function weekOfMonth(monday) {
        const thu = copy(monday);
        thu.setDate(thu.getDate() + 3);
        const first = new Date(thu.getFullYear(), thu.getMonth(), 1);
        const firstMon = mondayOf(first);
        return Math.round((monday - firstMon) / 86400000) / 7 + 1;
    }

    function badgeClass(type) {
        if (type === "ЛК") return "is-lk";
        if (type === "ЛБ") return "is-lb";
        if (type === "СМ") return "is-sm";
        return "";
    }

    function renderWeek() {
        const mon = mondayOf(selected);
        const thu = copy(mon);
        thu.setDate(thu.getDate() + 3);
        const wn = weekOfMonth(mon);
        $weekTitle.textContent = MONTHS[thu.getMonth()] + " " + thu.getFullYear() + " – " + wn + " неделя";

        $days.innerHTML = "";
        for (let i = 0; i < 7; i++) {
            const d = copy(mon);
            d.setDate(mon.getDate() + i);
            const key = iso(d);
            const count = journalList(key).length;
            const btn = document.createElement("button");
            btn.className = "day";
            if (iso(d) === iso(selected)) btn.classList.add("is-active");
            if (count) btn.classList.add("has-lessons");
            if (!count) btn.classList.add("has-none");
            btn.innerHTML = '<span class="day-num">' + d.getDate() + '</span><span class="day-count">' + (count || "") + "</span>";
            btn.addEventListener("click", () => {
                selected = d;
                renderWeek();
                renderCards();
            });
            $days.appendChild(btn);
        }
    }

    function csrfToken() {
        var el = document.querySelector("[name=csrfmiddlewaretoken]");
        return el ? el.value : "";
    }

    function apiJson(url, payload) {
        return fetch(url, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "X-CSRFToken": csrfToken()
            },
            body: JSON.stringify(payload || {})
        }).then(function (r) { return r.json().then(function (d) { d.status = r.status; return d; }); });
    }

    function setEditUi(on) {
        canEdit = !!on;
        var bar = document.getElementById("editBar");
        var cards = document.getElementById("cards");
        var sw = document.getElementById("editSwitch");
        if (bar) bar.classList.toggle("is-on", canEdit);
        if (cards) cards.classList.toggle("is-editing", canEdit);
        if (sw) sw.classList.toggle("off", !canEdit);
        setAutoAttendUi(autoAttend);
        setSyncUi();
        renderWeek();
        renderCards();
    }

    function setSyncUi() {
        var acc = document.getElementById("btnAcceptSync");
        var can = document.getElementById("btnCancelSync");
        if (acc) acc.disabled = pendingCount <= 0;
        if (can) can.disabled = pendingCount <= 0;
    }

    function isPending(item) {
        return item && (item.pending || (item.source === "sync" && item.accepted === false));
    }

    function journalList(key) {
        var list = LESSONS[key] || [];
        if (canEdit) return list;
        return list.filter(function (x) { return !isPending(x); });
    }

    function ordinaryList(key) {
        return (LESSONS[key] || []).filter(function (x) { return !isPending(x); });
    }

    function setAutoAttendUi(on) {
        autoAttend = !!on;
        var sw = document.getElementById("autoAttendSwitch");
        if (sw) sw.classList.toggle("off", !autoAttend);
    }

    function refreshJournal() {
        return fetch("/api/lessons/?journal=1").then(function (r) { return r.json(); }).then(function (d) {
            LESSONS = d.lessons || {};
            var g = GROUPS.find(function (x) { return x.id === d.group; });
            if (g) g.lessons = LESSONS;
            if (activeGroup && d.group && activeGroup.id === d.group) {
                activeGroup.lessons = LESSONS;
            }
            pendingCount = 0;
            Object.keys(LESSONS).forEach(function (k) {
                (LESSONS[k] || []).forEach(function (item) {
                    if (isPending(item)) pendingCount += 1;
                });
            });
            setSyncUi();
            renderWeek();
            renderCards();
        });
    }

    function renderCards() {
        const key = iso(selected);
        const list = journalList(key);
        $datePillText.textContent = DAYS[selected.getDay()] + " - " + selected.getDate() + " " + MONTHS_GEN[selected.getMonth()] + " " + selected.getFullYear();

        if (!list.length) {
            $cards.innerHTML = '<div class="empty"><div class="empty-icon"><svg width="26" height="26" viewBox="0 0 24 24" fill="none"><rect x="4" y="5" width="16" height="15" rx="2.5" stroke="currentColor" stroke-width="1.7"/><path d="M8 3.5v3M16 3.5v3M4 10h16" stroke="currentColor" stroke-width="1.7" stroke-linecap="round"/></svg></div><p>Пар нет</p><span>На этот день занятия не найдены</span></div>';
            return;
        }

        $cards.innerHTML = list.map(function (item) {
            var present = item.week === "+";
            var pending = isPending(item);
            var kind = pending ? "is-pending is-sync" : (item.source === "sync" ? "is-sync" : "is-manual");
            var actions = "";
            if (canEdit) {
                actions = '<div class="card-edit">';
                if (pending) {
                    actions += '<button type="button" class="add" data-accept="' + item.id + '">Добавить в расписание</button>';
                } else {
                    actions += '<button type="button" class="att' + (present ? " is-on" : "") + '" data-attend="' + item.id + '" data-week="' + (present ? "+" : "Н") + '">' +
                        (present ? "Снять +" : "Отметить +") +
                        "</button>";
                }
                actions += '<button type="button" class="ed" data-edit="' + item.id + '">Изменить</button>' +
                    '<button type="button" class="del" data-del="' + item.id + '">Удалить</button>' +
                    "</div>";
            }
            return (
                '<article class="card ' + kind + '" data-lid="' + item.id + '">' +
                    '<div class="card-top">' +
                        '<div class="time-row">' +
                            '<span class="time">' + item.time + "</span>" +
                            '<span class="badge ' + badgeClass(item.type) + '">' + item.type + "</span>" +
                        "</div>" +
                        '<div class="room">' + item.room + "</div>" +
                    "</div>" +
                    '<div class="subject">' + item.subject + "</div>" +
                    '<div class="card-line"></div>' +
                    '<div class="card-footer">' +
                        '<div class="tags">' +
                            '<span class="tag-h' + (item.week === "+" ? " is-plus" : "") + '">' + item.week + "</span>" +
                            '<span class="tag-src">' + (canEdit ? (pending ? "Черновик" : (item.source === "sync" ? "МИРЭА" : "Вручную")) : "Расписание") + "</span>" +
                        "</div>" +
                        '<div class="teacher">' + item.teacher + "</div>" +
                    "</div>" +
                    actions +
                "</article>"
            );
        }).join("");
    }

    function shiftWeek(dir) {
        selected.setDate(selected.getDate() + dir * 7);
        selected = copy(selected);
        renderWeek();
        renderCards();
        if (document.getElementById("view-compare").classList.contains("is-active")) {
            renderCompare();
        }
    }

    function renderPicker() {
        document.getElementById("pickerMonth").textContent = MONTHS[pickerCursor.getMonth()] + " " + pickerCursor.getFullYear();
        const grid = document.getElementById("pickerGrid");
        grid.innerHTML = "";
        ["Пн","Вт","Ср","Чт","Пт","Сб","Вс"].forEach(function (n) {
            const el = document.createElement("div");
            el.className = "ph";
            el.textContent = n;
            grid.appendChild(el);
        });

        const first = new Date(pickerCursor.getFullYear(), pickerCursor.getMonth(), 1);
        const start = mondayOf(first);
        for (let i = 0; i < 42; i++) {
            const d = copy(start);
            d.setDate(start.getDate() + i);
            const btn = document.createElement("button");
            btn.className = "pday";
            if (d.getMonth() !== pickerCursor.getMonth()) btn.classList.add("mute");
            if (journalList(iso(d)).length) btn.classList.add("has");
            if (iso(d) === iso(selected)) btn.classList.add("is-sel");
            btn.textContent = d.getDate();
            btn.addEventListener("click", function () {
                pickerCursor = new Date(d.getFullYear(), d.getMonth(), 1);
                document.getElementById("dateOverlay").classList.remove("is-open");
                selected = d;
                renderWeek();
                renderCards();
                if (document.getElementById("view-compare").classList.contains("is-active")) {
                    renderCompare();
                }
            });
            grid.appendChild(btn);
        }
    }

    document.getElementById("prevWeek").addEventListener("click", function () { shiftWeek(-1); });
    document.getElementById("nextWeek").addEventListener("click", function () { shiftWeek(1); });

    document.getElementById("datePill").addEventListener("click", function () {
        pickerTarget = "journal";
        pickerCursor = new Date(selected.getFullYear(), selected.getMonth(), 1);
        renderPicker();
        document.getElementById("dateOverlay").classList.add("is-open");
    });

    document.getElementById("prevMonth").addEventListener("click", function () {
        pickerCursor.setMonth(pickerCursor.getMonth() - 1);
        renderPicker();
    });
    document.getElementById("nextMonth").addEventListener("click", function () {
        pickerCursor.setMonth(pickerCursor.getMonth() + 1);
        renderPicker();
    });

    document.getElementById("dateOverlay").addEventListener("click", function (e) {
        if (e.target === this) this.classList.remove("is-open");
    });

    document.getElementById("fab").addEventListener("click", function () {
        document.getElementById("qrImg").src = "https://api.qrserver.com/v1/create-qr-code/?size=186x186&margin=8&data=" + encodeURIComponent("JOURNAL|" + iso(selected) + "|ИС-21-1");
        document.getElementById("qrOverlay").classList.add("is-open");
    });
    document.getElementById("closeQr").addEventListener("click", function () {
        document.getElementById("qrOverlay").classList.remove("is-open");
    });
    document.getElementById("qrOverlay").addEventListener("click", function (e) {
        if (e.target === this) this.classList.remove("is-open");
    });

    document.querySelectorAll(".nav-btn").forEach(function (btn) {
        btn.addEventListener("click", function () {
            showView(btn.dataset.view);
        });
    });

    document.getElementById("notifySwitch") && document.getElementById("notifySwitch").addEventListener("click", function () {
        this.classList.toggle("off");
    });

    document.getElementById("grades").innerHTML = GRADES.map(function (g) {
        return '<div class="row-card"><div class="row-ico" style="background:#4b8ef5">' + g.mark + "</div><div><h3>" + g.name + "</h3><p>" + g.sub + "</p></div><div class=\"mark\">" + g.mark + "</div></div>";
    }).join("");

    function showView(name) {
        hideTip();
        document.querySelectorAll(".view").forEach(function (v) { v.classList.remove("is-active"); });
        const id = (name === "sub") ? "view-sub" : "view-" + name;
        document.getElementById(id).classList.add("is-active");
        $fab.classList.toggle("is-hidden", name !== "journal");
        var navName = name;
        if (name === "sub") {
            navName = subReturn === "settings" ? "settings" : (subReturn === "journal" ? "journal" : "grid");
        }
        document.querySelectorAll(".nav-btn").forEach(function (b) {
            b.classList.toggle("is-active", b.dataset.view === navName);
        });
        document.querySelector(".app-scroll").scrollTop = 0;
        if (name === "compare") renderCompare();
        if (name === "journal") {
            renderWeek();
            renderCards();
        }
    }

    function groupLessons() { return LESSONS; }

    function campusPlace(room) {
        var r = (room || "").replace(/\s+/g, " ").trim();
        if (!r) return "(С-20)";
        if (/\(С-20\)/i.test(r)) return r;
        return r + " (С-20)";
    }

    function asCompareLesson(item) {
        var room = item.room || item.location || "";
        return {
            time: item.time,
            type: item.type,
            subject: item.subject,
            room: room,
            location: campusPlace(room),
            teacher: item.teacher_full || item.teacher || ""
        };
    }

    function parseRange(time) {
        const parts = time.split("-").map(function (s) { return s.trim(); });
        function hm(s) {
            const bits = s.split(":");
            return Number(bits[0]) + Number(bits[1] || 0) / 60;
        }
        return { start: hm(parts[0]), end: hm(parts[1]) };
    }

    function renderCompare() {
        hideTip();
        const mon = mondayOf(selected);
        const thu = copy(mon);
        thu.setDate(thu.getDate() + 3);
        const wn = weekOfMonth(mon);
        document.getElementById("cmpWeekTitle").textContent = MONTHS[thu.getMonth()] + " " + thu.getFullYear() + " – " + wn + " неделя";
        document.getElementById("cmpWeekType").textContent = wn + " неделя";
        document.getElementById("groupName").textContent = activeGroup.name;
        document.getElementById("cmpDateText").textContent = DAYS[selected.getDay()] + " - " + selected.getDate() + " " + MONTHS_GEN[selected.getMonth()] + " " + selected.getFullYear();

        const box = document.getElementById("cmpDays");
        box.innerHTML = "";
        for (let i = 0; i < 7; i++) {
            const d = copy(mon);
            d.setDate(mon.getDate() + i);
            const list = ordinaryList(iso(d));
            const btn = document.createElement("button");
            btn.className = "day";
            if (iso(d) === iso(selected)) btn.classList.add("is-active");
            if (list.length) btn.classList.add("has-lessons");
            btn.innerHTML = '<span class="day-num">' + d.getDate() + '</span><span class="day-dot"></span>';
            btn.addEventListener("click", function () {
                selected = d;
                renderCompare();
            });
            box.appendChild(btn);
        }

        const hours = document.getElementById("tlHours");
        hours.innerHTML = "";
        for (let h = HOUR_START; h <= HOUR_END; h++) {
            const el = document.createElement("div");
            el.className = "tl-h";
            el.textContent = h;
            hours.appendChild(el);
        }

        const track = document.getElementById("tlTrack");
        track.style.height = ((HOUR_END - HOUR_START + 1) * HOUR_H) + "px";
        track.innerHTML = "";
        const list = ordinaryList(iso(selected)).map(asCompareLesson);
        list.forEach(function (item, idx) {
            const range = parseRange(item.time);
            const top = (range.start - HOUR_START) * HOUR_H;
            const height = Math.max((range.end - range.start) * HOUR_H - 6, 54);
            const card = document.createElement("button");
            card.className = "tl-card";
            card.style.top = top + "px";
            card.style.height = height + "px";
            card.innerHTML = '<div class="tl-meta">' + item.type + " | " + item.time + "</div>" +
                '<div class="tl-subj">' + item.subject + " " + item.location + "</div>";
            card.addEventListener("click", function (e) {
                e.stopPropagation();
                showTip(card, item);
            });
            track.appendChild(card);
        });
        updateNowLine();
    }

    function isTodaySelected() {
        var t = new Date();
        return selected.getFullYear() === t.getFullYear() && selected.getMonth() === t.getMonth() && selected.getDate() === t.getDate();
    }

    function updateNowLine() {
        var line = document.getElementById("nowLine");
        if (!line) return;
        if (!isTodaySelected()) {
            line.classList.remove("is-on");
            return;
        }
        var now = new Date();
        var hm = now.getHours() + now.getMinutes() / 60;
        if (hm < HOUR_START - 0.05 || hm > HOUR_END + 0.3) {
            line.classList.remove("is-on");
            return;
        }
        line.style.top = ((hm - HOUR_START) * HOUR_H) + "px";
        document.getElementById("nowTimeLabel").textContent = pad(now.getHours()) + ":" + pad(now.getMinutes());
        line.classList.add("is-on");
    }

    function hideTip() {
        document.getElementById("lessonTip").classList.remove("is-open");
        document.getElementById("tipCatch").classList.remove("is-open");
    }

    function showTip(cardEl, lesson) {
        const tip = document.getElementById("lessonTip");
        const catcher = document.getElementById("tipCatch");
        document.getElementById("tipTitle").textContent = lesson.type + " " + lesson.subject;
        document.getElementById("tipTime").textContent = lesson.time.replace(/\s/g, "");
        document.getElementById("tipLoc").textContent = "Локация: " + campusPlace(lesson.room || lesson.location);
        document.getElementById("tipTeacher").textContent = "Преподаватель: " + (lesson.teacher_full || lesson.teacher || "");
        catcher.classList.add("is-open");
        tip.classList.add("is-open");

        const phone = document.querySelector(".phone");
        const pr = phone.getBoundingClientRect();
        const cr = cardEl.getBoundingClientRect();
        const th = tip.offsetHeight || 140;
        let top = cr.top - pr.top - th + 6;
        if (top < 10) {
            document.querySelector(".app-scroll").scrollBy({ top: top - 16, behavior: "smooth" });
            top = 12;
        }
        tip.style.top = top + "px";
        const arrow = tip.querySelector(".lesson-tip-arrow");
        arrow.style.marginLeft = Math.max(24, Math.min(cr.left - pr.left - 16 + 28, 220)) + "px";
    }

    let subReturn = "grid";
    function openSub(title, html, backTo) {
        subReturn = backTo || "grid";
        document.getElementById("subTitle").textContent = title;
        var root = "Сервисы";
        if (backTo === "settings") root = "Настройки";
        if (backTo === "journal") root = "Журнал студента";
        document.getElementById("subCrumb").textContent = root + " / " + title;
        document.getElementById("subBody").innerHTML = html;
        showView("sub");
    }

    function showLessonOverview(item) {
        var day = iso(selected).replace(/-/g, ".");
        var times = (item.time || "").split(" - ");
        var groupName = (STUDENT && STUDENT.group_name) || activeGroup.name || "БСМО-31-25";
        var html = '<div class="ov-group">Из расписания группы : <span>' + groupName + "</span></div>" +
            '<div class="sec-label">Информация о занятии</div>' +
            '<div class="ov-table">' +
            '<div class="ov-row"><div class="ov-k">Дата</div><div class="ov-v">' + day + " " + (times[0] || "") + " -<br>" + (times[1] || "") + "</div></div>" +
            '<div class="ov-row"><div class="ov-k">Тип</div><div class="ov-v"><span class="badge ' + badgeClass(item.type) + '">' + item.type + "</span></div></div>" +
            '<div class="ov-row"><div class="ov-k">Аудитория</div><div class="ov-v"><span class="ov-room">' + (item.room || item.location || "") + "</span></div></div>" +
            '<div class="ov-row"><div class="ov-k">Преподаватель</div><div class="ov-v"><span class="ov-teach">' + (item.teacher || "") + "</span></div></div>" +
            '<div class="ov-row"><div class="ov-k">Статус</div><div class="ov-v"><span class="tag-h' + (item.week === "+" ? " is-plus" : "") + '">' + (item.week || "Н") + "</span></div></div>" +
            "</div>";
        openSub(item.subject, html, "journal");
    }

    var copyBtnIcon = '<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.8"><rect x="8" y="8" width="12" height="12" rx="2"/><path d="M4 16V6a2 2 0 012-2h10"/></svg>';

    var GROUP_MEMBERS = [
        { name: "Анашкин Матвей Дмитриевич", email: "anashkin.m.d@edu.mirea.ru" },
        { name: "Басалыков Иван Вячеславович", email: "basalykov.i.v@edu.mirea.ru", starosta: true },
        { name: "Беликов Григорий Дмитриевич", email: "belikov.g.d@edu.mirea.ru" },
        { name: "Бондарев Иван Сергеевич", email: "bondarev.i.s@edu.mirea.ru" },
        { name: "Брагин Константин Александрович", email: "bragin.k.a@edu.mirea.ru" },
        { name: "Вдовина Анастасия Александровна", email: "vdovina.a.a@edu.mirea.ru" },
        { name: "Гаршник Станислав Николаевич", email: "garshnik.s.n@edu.mirea.ru" },
        { name: "Данилов Дмитрий Владимирович", email: "danilov.d.v@edu.mirea.ru" },
        { name: "Казин Александр Александрович", email: "kazin.a.a@edu.mirea.ru" },
        { name: "Кирчиков Иван Дмитриевич", email: "kirchikov.i.d@edu.mirea.ru" },
        { name: "Князев Семен Андреевич", email: "knyazev.s.a@edu.mirea.ru" },
        { name: "Кононов Артём Сергеевич", email: "kononov.a.s@edu.mirea.ru" },
        { name: "Краев Максим Александрович", email: "kraev.m.a@edu.mirea.ru" },
        { name: "Кузьмин Сергей Александрович", email: "kuzmin.s.a@edu.mirea.ru" },
        { name: "Логунов Артемий Олегович", email: "logunov.a.o@edu.mirea.ru" },
        { name: "Новиков Матвей Сергеевич", email: "novikov.m.s@edu.mirea.ru" },
        { name: "Савенков Илья Анатольевич", email: "savenkov.i.a@edu.mirea.ru" },
        { name: "Саянов Рамазан Жалилович", email: "sayanov.r.z@edu.mirea.ru" },
        { name: "Сердюков Александр Андреевич", email: "serdyukov.a.a2@edu.mirea.ru" },
        { name: "Смирягин Вадим Анатольевич", email: "smiryagin.v.a@edu.mirea.ru" },
        { name: "Стока Иван Павлович", email: "stoka.i.p@edu.mirea.ru" },
        { name: "Тимохин Вячеслав Максимович", email: "timokhin.v.m@edu.mirea.ru" },
        { name: "Турчанинов Даниил Владимирович", email: "turchaninov.d.v@edu.mirea.ru" },
        { name: "Хасанов Владислав Андреевич", email: "khasanov.v.a@edu.mirea.ru" },
        { name: "Хафизов Рустам Айратович", email: "khafizov.r.a@edu.mirea.ru" },
        { name: "Шмаков Фёдор Михайлович", email: "shmakov.f.m@edu.mirea.ru" },
        { name: "Юрков Александр Владимирович", email: "yurkov.a.v1@edu.mirea.ru" }
    ];

    function groupPageHtml() {
        var people = GROUP_MEMBERS.map(function (p, i) {
            var star = p.starosta ? '<span class="grp-star">Староста</span>' : "";
            return '<div class="grp-person"><div class="grp-num">' + (i + 1) + "</div><div><strong>" + p.name + "</strong>" + star +
                '<br><a href="mailto:' + p.email + '">' + p.email + "</a></div></div>";
        }).join("");
        return '<select class="grp-select" disabled><option>БСМО-31-25</option></select>' +
            '<div class="grp-block"><div class="grp-head">Информация об обучении</div><div class="grp-info">' +
            '<div class="grp-label">Мой шифр</div><div class="grp-val">2561919</div>' +
            '<div class="grp-label">Направление подготовки</div><div class="grp-val">09.04.02 Информационные системы и технологии (Проектирование и обслуживание высоконагруженных информационных систем)</div>' +
            '<div class="grp-label">Выпускающее подразделение</div><div class="grp-val">Кафедра КБ-14 «Цифровые технологии обработки данных»</div>' +
            '<div class="grp-label">Вышестоящее подразделение</div><div class="grp-val">Институт кибербезопасности и цифровых технологий</div>' +
            "</div></div>" +
            '<div class="grp-block"><div class="grp-head">Список группы (' + GROUP_MEMBERS.length + ')' +
            '<button type="button" class="grp-copy" id="grpCopy">' + copyBtnIcon + " Копировать</button></div>" +
            '<div class="grp-list">' + people + "</div></div>";
    }

    function myschedHtml() {
        return GROUPS.map(function (g) {
            return '<button class="sched-item" data-open-group="' + g.id + '"><span class="dot"></span><div><h3>' + g.name + "</h3><p>" + g.blurb + "</p></div></button>";
        }).join("");
    }

    document.getElementById("openCompare").addEventListener("click", function () {
        showView("compare");
    });
    document.getElementById("compareBack").addEventListener("click", function () { showView("grid"); });
    document.getElementById("crumbServices").addEventListener("click", function () { showView("grid"); });
    document.getElementById("subBack").addEventListener("click", function () { showView(subReturn || "grid"); });

    document.getElementById("cmpPrevWeek").addEventListener("click", function () { shiftWeek(-1); });
    document.getElementById("cmpNextWeek").addEventListener("click", function () { shiftWeek(1); });

    document.getElementById("cmpDatePill").addEventListener("click", function () {
        pickerTarget = "compare";
        pickerCursor = new Date(selected.getFullYear(), selected.getMonth(), 1);
        renderPicker();
        document.getElementById("dateOverlay").classList.add("is-open");
    });

    document.getElementById("groupRow").addEventListener("click", function () {
        document.getElementById("groupList").innerHTML = GROUPS.map(function (g) {
            return '<button class="sched-item" data-id="' + g.id + '"><span class="dot"></span><div><h3>' + g.name + "</h3><p>" + g.blurb + "</p></div></button>";
        }).join("");
        document.getElementById("groupOverlay").classList.add("is-open");
    });
    document.getElementById("groupOverlay").addEventListener("click", function (e) {
        if (e.target === this) this.classList.remove("is-open");
        const item = e.target.closest("[data-id]");
        if (!item) return;
        activeGroup = GROUPS.find(function (g) { return g.id === item.dataset.id; }) || GROUPS[0];
        LESSONS = activeGroup.lessons || {};
        this.classList.remove("is-open");
        showView("compare");
        renderCompare();
        renderWeek();
        renderCards();
    });

    document.getElementById("openMySched").addEventListener("click", function () {
        openSub("Мои расписания", myschedHtml());
    });

    document.getElementById("subBody").addEventListener("click", function (e) {
        const item = e.target.closest("[data-open-group]");
        if (!item) return;
        activeGroup = GROUPS.find(function (g) { return g.id === item.dataset.openGroup; }) || GROUPS[0];
        LESSONS = activeGroup.lessons || {};
        showView("compare");
        renderCompare();
        renderWeek();
        renderCards();
    });

    document.querySelectorAll("[data-sub]").forEach(function (btn) {
        btn.addEventListener("click", function () {
            const key = btn.dataset.sub;
            if (key === "mysched") {
                openSub("Мои расписания", myschedHtml());
                return;
            }
            if (key === "pass") {
                openSub("Мой пропуск",
                    '<div class="pass-card"><div class="pass-label">Электронный пропуск</div><h2>Кононов А.</h2><p>Группа БСМО-31-25</p><p>Действует до 31.08.2027</p><p style="margin-top:14px;opacity:.8">Покажите QR на вахте или в аудитории</p></div>' +
                    '<button class="close-btn" id="passQr" style="margin-top:16px">Показать QR</button>');
                document.getElementById("passQr").addEventListener("click", function () {
                    document.getElementById("qrImg").src = "https://api.qrserver.com/v1/create-qr-code/?size=186x186&margin=8&data=" + encodeURIComponent("PASS|Кононов|БСМО-31-25");
                    document.getElementById("qrOverlay").classList.add("is-open");
                });
                return;
            }
            if (key === "group") {
                openSub("Учебная группа", groupPageHtml());
                var copyBtn = document.getElementById("grpCopy");
                if (copyBtn) {
                    copyBtn.addEventListener("click", function () {
                        var mails = GROUP_MEMBERS.map(function (p) { return p.email; }).join("\n");
                        if (navigator.clipboard) navigator.clipboard.writeText(mails);
                        copyBtn.textContent = "Скопировано";
                        setTimeout(function () { copyBtn.innerHTML = copyBtnIcon + " Копировать"; }, 1200);
                    });
                }
                return;
            }
            if (key === "disc") {
                const items = [
                    "Системы автоматизированного развертывания",
                    "Управление IT-проектами",
                    "Методы исследования",
                    "Облачные технологии",
                    "Машинное обучение"
                ];
                openSub("Дисциплины", items.map(function (n) {
                    return '<div class="row-card" style="margin-bottom:10px"><div class="row-ico" style="background:#e53935">Д</div><div><h3>' + n + "</h3><p>2026 / 2027 учебный год</p></div></div>";
                }).join(""));
                return;
            }
            if (key === "proj") {
                openSub("Проектная зона", '<p style="color:#666;line-height:1.5">Командные проекты, канбан-доски и репозитории учебной группы. Раздел доступен студентам БСМО-31-25.</p>');
                return;
            }
            if (key === "map") {
                openSub("Карта", '<p style="color:#666;line-height:1.5;margin-bottom:12px">Корпус С-20, аудитория 333 — 3 этаж, правое крыло.</p><div class="row-card"><div class="row-ico" style="background:#8d5a70">С</div><div><h3>Корпус С-20</h3><p>ул. Университетская, 1</p></div></div>');
            }
        });
    });

    document.querySelectorAll("[data-go]").forEach(function (btn) {
        btn.addEventListener("click", function () { showView(btn.dataset.go); });
    });

    // Ссылки цифрового университета — подставьте свои URL вместо Google:
    var UNI_LINKS = {
        lks: "https://lk.mirea.ru/",      // ЛКС
        sdo: "https://online-edu.mirea.ru/",      // СДО
        ibc: "https://ibc.mirea.ru/",      // ИБЦ
        idea: "https://vote.mirea.ru/",     // «Есть идея?»
        sprav: "https://student.mirea.ru/help/",    // Справочник
        stud: "https://student.mirea.ru/services/",     // Студофис
        fond: "https://fund.mirea.ru/",     // Фонд
        vo: "https://ump.mirea.ru/"        // ВО
    };

    document.getElementById("uniGrid").innerHTML = UNI.map(function (u) {
        var href = UNI_LINKS[u.id] || "https://www.google.com";
        return '<a class="uni-card" href="' + href + '" target="_blank" rel="noopener noreferrer">' +
            (UNI_SVG[u.id] || "") + "<span>" + u.name + "</span></a>";
    }).join("");

    document.getElementById("roleSelect").addEventListener("click", function () {
        const roles = ["Студент", "Преподаватель", "Сотрудник"];
        document.getElementById("roleList").innerHTML = roles.map(function (r) {
            return '<button class="sched-item" data-role="' + r + '"><span class="dot"></span><div><h3>' + r + "</h3></div></button>";
        }).join("");
        document.getElementById("roleOverlay").classList.add("is-open");
    });
    document.getElementById("roleOverlay").addEventListener("click", function (e) {
        if (e.target === this) this.classList.remove("is-open");
        const item = e.target.closest("[data-role]");
        if (!item) return;
        document.getElementById("roleLabel").textContent = item.dataset.role;
        this.classList.remove("is-open");
    });

    document.getElementById("tipCatch").addEventListener("click", hideTip);

    function openInfo(title, html) {
        document.getElementById("infoTitle").textContent = title;
        document.getElementById("infoBody").innerHTML = html;
        document.getElementById("infoOverlay").classList.add("is-open");
    }
    document.getElementById("infoClose").addEventListener("click", function () {
        document.getElementById("infoOverlay").classList.remove("is-open");
    });
    document.getElementById("infoOverlay").addEventListener("click", function (e) {
        if (e.target === this) this.classList.remove("is-open");
    });

    function applyTheme(mode) {
        const phone = document.querySelector(".phone");
        const dark = mode === "dark" || (mode === "system" && window.matchMedia("(prefers-color-scheme: dark)").matches);
        phone.classList.toggle("theme-dark", dark);
        document.querySelectorAll("#themeSeg button").forEach(function (b) {
            b.classList.toggle("is-on", b.dataset.theme === mode);
        });
        try { localStorage.setItem("theme", mode); } catch (e) {}
    }

    document.getElementById("themeSeg").addEventListener("click", function (e) {
        const btn = e.target.closest("[data-theme]");
        if (btn) applyTheme(btn.dataset.theme);
    });
    try {
        const saved = localStorage.getItem("theme");
        if (saved) applyTheme(saved);
    } catch (e) {}

    document.getElementById("btnLogout").addEventListener("click", function () {
        var name = (STUDENT.full_name || "аккаунта");
        openInfo("Выход",
            '<p class="set-p">Выйти из аккаунта ' + name + '?</p>' +
            '<form method="post" action="/logout/">' +
            '<input type="hidden" name="csrfmiddlewaretoken" value="' + csrfToken() + '">' +
            '<button type="submit" class="close-btn" style="background:#e53935">Выйти</button></form>');
    });
    document.getElementById("btnGuide").addEventListener("click", function () {
        openSub("Инструкция",
            '<p class="set-p">Журнал студента показывает пары на выбранный день. Сервисы открывают сравнение расписаний, пропуск и сервисы цифрового университета.</p><p class="set-p">В сравнении расписаний нажмите на карточку пары, чтобы увидеть преподавателя и аудиторию.</p><p class="set-p">QR-кнопка в журнале нужна для отметки посещения.</p>',
            "settings");
    });
    document.getElementById("btnBell").addEventListener("click", function () {
        openInfo("Уведомления",
            '<div class="sched-item"><span class="dot"></span><div><h3>Пара через 15 минут</h3><p>Системы автоматизированного развертывания · 333</p></div></div>' +
            '<div class="sched-item"><span class="dot"></span><div><h3>Уважительное отсутствие</h3><p>Заявка рассмотрена · 30.04.2026</p></div></div>' +
            '<div class="sched-item"><span class="dot"></span><div><h3>Изменение расписания</h3><p>Пара 8 сентября перенесена в 333</p></div></div>' +
            '<div class="sched-item"><span class="dot"></span><div><h3>Новое объявление</h3><p>Студофис: приём справок до 18:00</p></div></div>' +
            '<div class="sched-item"><span class="dot"></span><div><h3>Оценка выставлена</h3><p>Практическая работа №1 · 5</p></div></div>');
    });
    document.getElementById("btnAbsences").addEventListener("click", function () {
        openSub("Уважительные отсутствия",
            '<div class="row-card"><div class="row-ico" style="background:#4b8ef5">№</div><div><h3>Шифр 2561919</h3><p>Кононов Артём Сергеевич</p></div></div>' +
            '<div class="row-card" style="margin-top:10px"><div class="row-ico" style="background:#9ccc4d">1</div><div><h3>30.04.2026</h3><p>18:00 – 23:59 · уважительная причина</p></div></div>',
            "settings");
    });
    document.getElementById("btnLang").addEventListener("click", function () {
        openInfo("Иностранный язык",
            '<button class="sched-item" data-lang="Английский"><span class="dot"></span><div><h3>Английский</h3></div></button>' +
            '<button class="sched-item" data-lang="Немецкий"><span class="dot"></span><div><h3>Немецкий</h3></div></button>' +
            '<button class="sched-item" data-lang="Французский"><span class="dot"></span><div><h3>Французский</h3></div></button>');
        document.getElementById("infoBody").addEventListener("click", function langPick(e) {
            const item = e.target.closest("[data-lang]");
            if (!item) return;
            document.getElementById("btnLang").textContent = item.dataset.lang;
            document.getElementById("infoOverlay").classList.remove("is-open");
            document.getElementById("infoBody").removeEventListener("click", langPick);
        });
    });
    document.getElementById("btnVk").addEventListener("click", function () {
        openInfo("ВКонтакте", '<p class="set-p">Группа Центра молодежного техноковоркинга РТУ МИРЭА.</p>');
    });
    document.getElementById("btnTg").addEventListener("click", function () {
        openInfo("Telegram", '<p class="set-p">Чат поддержки сервиса посещаемости. Напишите группу и суть вопроса.</p>');
    });
    document.getElementById("btnChangelog").addEventListener("click", function () {
        openInfo("История изменений",
            '<div class="sched-item"><span class="dot"></span><div><h3>1.9.0</h3><p>Сравнение расписаний и журнал студента</p></div></div>' +
            '<div class="sched-item"><span class="dot"></span><div><h3>1.8.2</h3><p>Уважительные отсутствия, QR посещения</p></div></div>' +
            '<div class="sched-item"><span class="dot"></span><div><h3>1.7.0</h3><p>Сервисы цифрового университета</p></div></div>');
    });
    document.getElementById("quickAccess").addEventListener("click", function () {
        const items = ["Сравнение расписаний", "Мои расписания", "Мой пропуск", "Учебная группа", "Дисциплины"];
        openInfo("Быстрый доступ", items.map(function (n) {
            return '<button class="sched-item" data-quick="' + n + '"><span class="dot"></span><div><h3>' + n + "</h3></div></button>";
        }).join(""));
        document.getElementById("infoBody").addEventListener("click", function quickPick(e) {
            const item = e.target.closest("[data-quick]");
            if (!item) return;
            document.getElementById("quickLabel").textContent = item.dataset.quick;
            document.getElementById("infoOverlay").classList.remove("is-open");
            document.getElementById("infoBody").removeEventListener("click", quickPick);
        });
    });

    function slotOptionsHtml() {
        var slots = BOOT.slots || [];
        if (!slots.length) {
            return '<option value="18:00|19:30">6 пара: 18:00 – 19:30</option><option value="19:40|21:10">7 пара: 19:40 – 21:10</option>';
        }
        return slots.map(function (s) {
            return '<option value="' + s.start + "|" + s.end + '">' + s.label + "</option>";
        }).join("");
    }

    function pickSlot(sel, want) {
        if (!sel) return;
        var found = false;
        for (var i = 0; i < sel.options.length; i++) {
            if (sel.options[i].value === want) { found = true; break; }
        }
        if (found) sel.value = want;
        else if (sel.options.length) sel.value = sel.options[Math.min(5, sel.options.length - 1)].value;
    }

    function findSubject(item) {
        if (!item) return null;
        if (item.subject_id) {
            return (BOOT.subjects || []).find(function (s) { return String(s.id) === String(item.subject_id); }) || null;
        }
        return (BOOT.subjects || []).find(function (s) { return s.name === item.subject; }) || null;
    }

    function findTeacher(item) {
        if (!item) return null;
        if (item.teacher_id) {
            return (BOOT.teachers || []).find(function (t) { return String(t.id) === String(item.teacher_id); }) || null;
        }
        return (BOOT.teachers || []).find(function (t) { return t.short_name === item.teacher; }) || null;
    }

    function fillSubjectSelect(preferredId) {
        var sel = document.getElementById("fSubject");
        if (!sel) return;
        var list = BOOT.subjects || [];
        sel.innerHTML = '<option value="">Выберите дисциплину</option>' + list.map(function (s) {
            return '<option value="' + s.id + '">' + s.name + "</option>";
        }).join("");
        if (preferredId) sel.value = String(preferredId);
    }

    function fillTeacherSelect(subjectId, preferredId) {
        var sel = document.getElementById("fTeacher");
        if (!sel) return;
        var subj = (BOOT.subjects || []).find(function (s) { return String(s.id) === String(subjectId); });
        var list = (subj && subj.teachers && subj.teachers.length) ? subj.teachers : [];
        if (!list.length) list = BOOT.teachers || [];
        var html = "";
        if (list.length !== 1) html += '<option value="">Выберите преподавателя</option>';
        var seen = {};
        list.forEach(function (t) {
            seen[String(t.id)] = true;
            html += '<option value="' + t.id + '">' + t.short_name + "</option>";
        });
        if (preferredId && !seen[String(preferredId)]) {
            var extra = (BOOT.teachers || []).find(function (t) { return String(t.id) === String(preferredId); });
            if (extra) html += '<option value="' + extra.id + '">' + extra.short_name + "</option>";
        }
        sel.innerHTML = html;
        if (preferredId) sel.value = String(preferredId);
        else if (list.length === 1) sel.value = String(list[0].id);
        else sel.value = "";
    }

    function rememberSubjectTeacher(subjectId, teacherId, teacherName) {
        if (!subjectId || !teacherId) return;
        var s = (BOOT.subjects || []).find(function (x) { return String(x.id) === String(subjectId); });
        if (!s) return;
        s.teachers = s.teachers || [];
        if (!s.teachers.some(function (t) { return String(t.id) === String(teacherId); })) {
            s.teachers.push({ id: Number(teacherId), short_name: teacherName, full_name: teacherName });
        }
    }

    function formLessonPayload(dateStr, slotVal) {
        var slot = (slotVal || document.getElementById("fSlot").value || "18:00|19:30").split("|");
        var subSel = document.getElementById("fSubject");
        var teaSel = document.getElementById("fTeacher");
        var subText = (subSel.selectedIndex >= 0 && subSel.value) ? subSel.options[subSel.selectedIndex].text : "";
        var teaText = (teaSel.selectedIndex >= 0 && teaSel.value) ? teaSel.options[teaSel.selectedIndex].text : "";
        return {
            date: dateStr,
            subject_id: subSel.value,
            subject: subText,
            type: document.getElementById("fType").value,
            start: slot[0],
            end: slot[1],
            room: document.getElementById("fRoom").value,
            week: document.getElementById("fWeek").value,
            teacher_id: teaSel.value,
            teacher: teaText
        };
    }

    (function fillLists() {
        var html = slotOptionsHtml();
        var slotSel = document.getElementById("fSlot");
        var copySlot = document.getElementById("fCopySlot");
        if (slotSel) slotSel.innerHTML = html;
        if (copySlot) copySlot.innerHTML = html;
        fillSubjectSelect("");
        fillTeacherSelect("", "");
    })();

    var unlockClicks = 0;
    var unlockTimer = null;
    var quickTitle = document.getElementById("quickTitle");
    if (quickTitle) {
        quickTitle.addEventListener("click", function () {
            unlockClicks += 1;
            clearTimeout(unlockTimer);
            unlockTimer = setTimeout(function () { unlockClicks = 0; }, 1400);
            if (unlockClicks >= 5) {
                unlockClicks = 0;
                document.getElementById("secretEdit").classList.add("is-open");
            }
        });
    }

    function applyEditVisual() {
        setEditUi(canEdit);
        var st = document.getElementById("editStatus");
        if (st) st.textContent = canEdit ? "Редактор включён" : "";
    }

    document.getElementById("editSwitch").addEventListener("click", function () {
        if (canEdit) {
            apiJson("/api/edit-mode/", { enabled: false }).then(function () {
                canEdit = false;
                applyEditVisual();
                refreshJournal();
            });
            return;
        }
        var pass = document.getElementById("editPassword").value;
        if (!pass) {
            document.getElementById("editStatus").textContent = "Введите пароль";
            return;
        }
        apiJson("/api/edit-mode/", { enabled: true, password: pass }).then(function (d) {
            if (d.ok) {
                canEdit = true;
                document.getElementById("editPassword").value = "";
                applyEditVisual();
                refreshJournal();
            } else {
                document.getElementById("editStatus").textContent = d.error || "Ошибка";
            }
        });
    });

    function openLessonForm(item) {
        document.getElementById("lessonFormTitle").textContent = item ? "Изменить пару" : "Новая пара";
        document.getElementById("lessonId").value = item ? item.id : "";
        var subj = findSubject(item);
        var teach = findTeacher(item);
        fillSubjectSelect(subj ? subj.id : "");
        fillTeacherSelect(subj ? subj.id : "", teach ? teach.id : "");
        document.getElementById("fType").value = item ? item.type : "ПР";
        var want = item && item.start && item.end ? (item.start + "|" + item.end) : "18:00|19:30";
        pickSlot(document.getElementById("fSlot"), want);
        document.getElementById("fRoom").value = item ? (item.room || "") : "";
        document.getElementById("fWeek").value = item ? (item.week === "В" ? "+" : item.week) : "Н";
        var box = document.getElementById("copyBox");
        if (box) box.classList.remove("is-open");
        var copySt = document.getElementById("copyStatus");
        if (copySt) copySt.textContent = "";
        var copyDate = document.getElementById("fCopyDate");
        if (copyDate) copyDate.value = iso(selected);
        pickSlot(document.getElementById("fCopySlot"), want);
        document.getElementById("lessonOverlay").classList.add("is-open");
    }

    document.getElementById("fSubject").addEventListener("change", function () {
        fillTeacherSelect(this.value, "");
    });

    document.getElementById("btnCopyToggle").addEventListener("click", function () {
        var box = document.getElementById("copyBox");
        box.classList.toggle("is-open");
        if (box.classList.contains("is-open")) {
            document.getElementById("fCopyDate").value = iso(selected);
            pickSlot(document.getElementById("fCopySlot"), document.getElementById("fSlot").value);
            document.getElementById("copyStatus").textContent = "";
        }
    });

    document.getElementById("btnCopyGo").addEventListener("click", function () {
        var day = document.getElementById("fCopyDate").value;
        var slot = document.getElementById("fCopySlot").value;
        var st = document.getElementById("copyStatus");
        if (!day) {
            st.textContent = "Выберите день";
            return;
        }
        var payload = formLessonPayload(day, slot);
        if (!payload.subject_id || !payload.teacher_id) {
            st.textContent = "Сначала выберите дисциплину и преподавателя";
            return;
        }
        st.textContent = "Копирую…";
        apiJson("/api/lessons/create/", payload).then(function (d) {
            if (d.ok) {
                rememberSubjectTeacher(payload.subject_id, payload.teacher_id, payload.teacher);
                st.textContent = "Скопировано на " + day;
                refreshJournal();
            } else {
                st.textContent = d.error || "Не удалось скопировать";
            }
        });
    });

    document.getElementById("autoAttendSwitch").addEventListener("click", function () {
        var next = !autoAttend;
        apiJson("/api/auto-attend/", { enabled: next }).then(function (d) {
            if (!d.ok) {
                document.getElementById("autoAttendStatus").textContent = d.error || "Не удалось сохранить";
                return;
            }
            setAutoAttendUi(d.auto_attend);
            var st = document.getElementById("autoAttendStatus");
            if (d.auto_attend) {
                st.textContent = d.marked ? ("Включено, отмечено пар: " + d.marked) : "Автоотметка включена";
            } else {
                st.textContent = "Автоотметка выключена";
            }
            if (d.marked) refreshJournal();
        });
    });

    document.getElementById("btnMarkPast").addEventListener("click", function () {
        var st = document.getElementById("autoAttendStatus");
        st.textContent = "Отмечаю…";
        apiJson("/api/auto-attend/", { mark_all: true }).then(function (d) {
            if (!d.ok) {
                st.textContent = d.error || "Не удалось отметить";
                return;
            }
            st.textContent = d.marked ? ("Отмечено пар: " + d.marked) : "Прошедших неотмеченных пар нет";
            if (d.marked) refreshJournal();
        });
    });

    setInterval(function () {
        if (!autoAttend) return;
        apiJson("/api/auto-attend/", { tick: true }).then(function (d) {
            if (!d.ok) return;
            if (typeof d.auto_attend === "boolean") setAutoAttendUi(d.auto_attend);
            if (d.marked) refreshJournal();
        });
    }, 30000);

    document.getElementById("btnAddLesson").addEventListener("click", function () {
        openLessonForm(null);
    });

    function syncStatus(text) {
        var el = document.getElementById("syncStatus");
        if (el) el.textContent = text || "";
    }

    function applySyncResult(d) {
        if (!d.ok) {
            syncStatus(d.error || "Не удалось синхронизировать");
            return;
        }
        pendingCount = Number(d.pending || 0);
        setSyncUi();
        var msg = "Черновиков: " + pendingCount;
        if (d.skipped_manual) msg += ", свои пары не тронуты: " + d.skipped_manual;
        if (d.group) msg += " (" + d.group + ")";
        if (d.source === "file") msg += ", из файла";
        else if (d.source === "api") msg += ", из API МИРЭА";
        syncStatus(msg);
        refreshJournal();
    }

    document.getElementById("btnSyncSchedule").addEventListener("click", function () {
        syncStatus("Загружаю официальное расписание…");
        apiJson("/api/schedule-sync/", { action: "sync" }).then(applySyncResult).catch(function () {
            syncStatus("Сеть недоступна. Загрузите Excel файлом.");
        });
    });

    document.getElementById("btnUploadSync").addEventListener("click", function () {
        var input = document.getElementById("fSyncFile");
        if (!input || !input.files || !input.files[0]) {
            syncStatus("Выберите файл .xlsx");
            return;
        }
        syncStatus("Читаю файл…");
        var body = new FormData();
        body.append("action", "upload");
        body.append("file", input.files[0]);
        fetch("/api/schedule-sync/", {
            method: "POST",
            headers: { "X-CSRFToken": csrfToken() },
            body: body
        }).then(function (r) { return r.json().then(function (d) { d.status = r.status; return d; }); })
            .then(applySyncResult)
            .catch(function () { syncStatus("Не удалось загрузить файл"); });
    });

    document.getElementById("btnAcceptSync").addEventListener("click", function () {
        if (pendingCount <= 0) {
            syncStatus("Нет серых пар для добавления");
            return;
        }
        syncStatus("Добавляю…");
        apiJson("/api/schedule-sync/", { action: "accept" }).then(function (d) {
            if (!d.ok) {
                syncStatus(d.error || "Не удалось добавить");
                return;
            }
            pendingCount = Number(d.pending || 0);
            setSyncUi();
            syncStatus(d.accepted ? ("Добавлено в расписание: " + d.accepted) : "Нечего добавлять");
            refreshJournal();
        });
    });

    document.getElementById("btnCancelSync").addEventListener("click", function () {
        if (pendingCount <= 0) {
            syncStatus("Нет черновиков для отмены");
            return;
        }
        if (!confirm("Убрать все серые пары из синхронизации? Свои пары останутся.")) return;
        syncStatus("Отменяю…");
        apiJson("/api/schedule-sync/", { action: "cancel" }).then(function (d) {
            if (!d.ok) {
                syncStatus(d.error || "Не удалось отменить");
                return;
            }
            pendingCount = 0;
            setSyncUi();
            syncStatus(d.deleted ? ("Удалено черновиков: " + d.deleted) : "Черновиков не было");
            refreshJournal();
        });
    });

    document.getElementById("btnCopyWeekToggle").addEventListener("click", function () {
        var box = document.getElementById("copyWeekBox");
        box.classList.toggle("is-open");
        if (box.classList.contains("is-open")) {
            var next = copy(selected);
            next.setDate(next.getDate() + 7);
            document.getElementById("fCopyWeekDate").value = iso(next);
            document.getElementById("copyWeekStatus").textContent = "";
        }
    });

    document.getElementById("btnCopyWeekGo").addEventListener("click", function () {
        var day = document.getElementById("fCopyWeekDate").value;
        var st = document.getElementById("copyWeekStatus");
        if (!day) {
            st.textContent = "Выберите день нужной недели";
            return;
        }
        st.textContent = "Копирую…";
        apiJson("/api/lessons/copy-week/", { from: iso(selected), to: day }).then(function (d) {
            if (d.ok) {
                var msg = "Скопировано пар: " + d.created;
                if (d.skipped) msg += ", уже были: " + d.skipped;
                st.textContent = msg;
                refreshJournal();
            } else {
                st.textContent = d.error || "Не удалось скопировать неделю";
            }
        });
    });
    document.getElementById("lessonOverlay").addEventListener("click", function (e) {
        if (e.target === this) this.classList.remove("is-open");
    });

    document.getElementById("cards").addEventListener("click", function (e) {
        var del = e.target.closest("[data-del]");
        var ed = e.target.closest("[data-edit]");
        var att = e.target.closest("[data-attend]");
        var acc = e.target.closest("[data-accept]");
        if (del) {
            if (!confirm("Удалить эту пару?")) return;
            apiJson("/api/lessons/" + del.dataset.del + "/delete/", {}).then(function (d) {
                if (d.ok) refreshJournal();
                else alert(d.error || "Не удалось удалить");
            });
            return;
        }
        if (ed) {
            var key = iso(selected);
            var item = (LESSONS[key] || []).find(function (x) { return String(x.id) === String(ed.dataset.edit); });
            if (item) openLessonForm(item);
            return;
        }
        if (att) {
            var next = att.dataset.week === "+" ? "Н" : "+";
            apiJson("/api/lessons/" + att.dataset.attend + "/update/", { week: next }).then(function (d) {
                if (d.ok) refreshJournal();
                else alert(d.error || "Не удалось отметить");
            });
            return;
        }
        if (acc) {
            apiJson("/api/schedule-sync/", { action: "accept", id: acc.dataset.accept }).then(function (d) {
                if (!d.ok) {
                    alert(d.error || "Не удалось добавить");
                    return;
                }
                pendingCount = Number(d.pending || 0);
                setSyncUi();
                refreshJournal();
            });
            return;
        }
        var art = e.target.closest("article.card[data-lid]");
        if (art) {
            var lesson = (LESSONS[iso(selected)] || []).find(function (x) { return String(x.id) === String(art.dataset.lid); });
            if (lesson) showLessonOverview(lesson);
        }
    });

    document.getElementById("lessonForm").addEventListener("submit", function (e) {
        e.preventDefault();
        var id = document.getElementById("lessonId").value;
        var payload = formLessonPayload(iso(selected), document.getElementById("fSlot").value);
        if (!payload.subject_id || !payload.teacher_id) {
            alert("Выберите дисциплину и преподавателя");
            return;
        }
        var url = id ? "/api/lessons/" + id + "/update/" : "/api/lessons/create/";
        apiJson(url, payload).then(function (d) {
            if (d.ok) {
                rememberSubjectTeacher(payload.subject_id, payload.teacher_id, payload.teacher);
                document.getElementById("lessonOverlay").classList.remove("is-open");
                refreshJournal();
            } else {
                alert(d.error || "Не удалось сохранить");
            }
        });
    });

    if (canEdit) {
        document.getElementById("secretEdit").classList.add("is-open");
        applyEditVisual();
    }

    var swipeBusy = false;
    function shiftDay(dir) {
        if (swipeBusy) return;
        swipeBusy = true;
        var onCompare = document.getElementById("view-compare").classList.contains("is-active");
        var pane = document.getElementById(onCompare ? "compareSwipe" : "journalSwipe");
        if (pane) {
            pane.classList.remove("swipe-in-left", "swipe-in-right", "swipe-out-left", "swipe-out-right");
            pane.classList.add(dir > 0 ? "swipe-out-left" : "swipe-out-right");
        }
        setTimeout(function () {
            selected.setDate(selected.getDate() + dir);
            selected = copy(selected);
            renderWeek();
            renderCards();
            if (onCompare) renderCompare();
            if (pane) {
                pane.classList.remove("swipe-out-left", "swipe-out-right");
                pane.classList.add(dir > 0 ? "swipe-in-right" : "swipe-in-left");
            }
            swipeBusy = false;
        }, 160);
    }

    function bindSwipe(el) {
        if (!el) return;
        var x0 = 0, y0 = 0, armed = false;
        function start(x, y) { x0 = x; y0 = y; armed = true; }
        function end(x, y) {
            if (!armed) return;
            armed = false;
            var dx = x - x0, dy = y - y0;
            if (Math.abs(dx) < 56 || Math.abs(dx) < Math.abs(dy) * 1.15) return;
            shiftDay(dx < 0 ? 1 : -1);
        }
        el.addEventListener("touchstart", function (e) {
            var t = e.changedTouches[0];
            start(t.clientX, t.clientY);
        }, { passive: true });
        el.addEventListener("touchend", function (e) {
            var t = e.changedTouches[0];
            end(t.clientX, t.clientY);
        });
        el.addEventListener("pointerdown", function (e) {
            if (e.pointerType === "touch") return;
            start(e.clientX, e.clientY);
        });
        el.addEventListener("pointerup", function (e) {
            if (e.pointerType === "touch") return;
            end(e.clientX, e.clientY);
        });
    }
    bindSwipe(document.getElementById("journalSwipe"));
    bindSwipe(document.getElementById("compareSwipe"));
    setInterval(updateNowLine, 30000);

    renderWeek();
    renderCards();

    (function bootFromUrl() {
        const params = new URLSearchParams(location.search);
        const view = params.get("view");
        if (view === "grid" || view === "compare" || view === "stats" || view === "settings") {
            showView(view);
        }
        if (params.get("tip") === "1") {
            showView("compare");
            setTimeout(function () {
                const card = document.querySelector(".tl-card");
                if (card) card.click();
            }, 80);
        }
    })();
