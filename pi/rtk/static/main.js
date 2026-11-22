(function () {
    "use strict";

    var NAMESPACE = "/test";
    var MAX_LINES = 500;
    var BUSY_TIMEOUT_MS = 20000;

    var $ = function (id) { return document.getElementById(id); };

    var state = {
        connected: false,
        rover: false,      // rtkrcv running
        logging: false,    // str2str recording
        timesync: false,   // false | "pending" | true
        busy: null         // id of the button waiting for a reply
    };
    var busyTimer = null;

    // ---------- helpers ----------

    function setTone(el, tone) { el.setAttribute("data-tone", tone); }

    function setTile(id, value, tone, meter) {
        var tile = $(id);
        tile.querySelector(".tile-value").textContent = value;
        setTone(tile, tone);
        if (meter !== undefined) {
            tile.querySelector(".meter span").style.width = Math.max(0, Math.min(100, meter)) + "%";
        }
    }

    function formatBytes(n) {
        var units = ["B", "KB", "MB", "GB", "TB"];
        var i = 0;
        while (n >= 1024 && i < units.length - 1) { n /= 1024; i++; }
        return (i === 0 ? n : n.toFixed(n < 10 ? 1 : 0)) + " " + units[i];
    }

    function pad(n) { return (n < 10 ? "0" : "") + n; }

    function clock(d) {
        return pad(d.getHours()) + ":" + pad(d.getMinutes()) + ":" + pad(d.getSeconds());
    }

    function formatDate(d) {
        var today = new Date();
        var sameDay = d.toDateString() === today.toDateString();
        var hm = pad(d.getHours()) + ":" + pad(d.getMinutes());
        if (sameDay) return "Today " + hm;
        return d.getFullYear() + "-" + pad(d.getMonth() + 1) + "-" + pad(d.getDate()) + " " + hm;
    }

    // ---------- messages ----------

    function toneFor(text) {
        var t = text.toLowerCase();
        if (/fail|error|not synced|disconnected/.test(t)) return "err";
        if (/success|started|synced|connected|launched/.test(t)) return "ok";
        if (/attempting|stopp|shutdown/.test(t)) return "muted";
        return "accent";
    }

    function log(text, tone) {
        var out = $("output");
        var stick = out.scrollHeight - out.scrollTop - out.clientHeight < 40;

        var line = document.createElement("div");
        line.className = "line";
        setTone(line, tone || toneFor(text));

        var time = document.createElement("time");
        time.textContent = clock(new Date());
        var span = document.createElement("span");
        span.textContent = text;

        line.appendChild(time);
        line.appendChild(span);
        out.appendChild(line);

        while (out.childNodes.length > MAX_LINES) out.removeChild(out.firstChild);
        if (stick) out.scrollTop = out.scrollHeight;
    }

    // ---------- buttons ----------

    function setBusy(id) {
        state.busy = id;
        clearTimeout(busyTimer);
        if (id) {
            busyTimer = setTimeout(function () { setBusy(null); }, BUSY_TIMEOUT_MS);
        }
        render();
    }

    function render() {
        var c = state.connected, r = state.rover, l = state.logging, b = !!state.busy;
        var syncing = state.timesync === "pending";

        var enabled = {
            start:    c && !b && !r && !l && !syncing,
            stop:     c && !b && r && !l,
            restart:  c && !b && r && !l,
            str2str:  c && !b && !r && !syncing,
            sync:     c && !b && !r && !l && state.timesync !== true && !syncing,
            shutdown: c && !b && !l
        };

        Object.keys(enabled).forEach(function (id) {
            var btn = $(id);
            btn.disabled = !enabled[id];
            btn.classList.toggle("is-busy", state.busy === id || (id === "sync" && syncing));
        });

        var rec = $("str2str");
        rec.classList.toggle("is-active", l);
        setTone(rec, l ? "err" : "accent");
        rec.querySelector(".action-label").textContent = l ? "Stop recording" : "Record raw";

        $("start").classList.toggle("is-active", r);

        // status tiles
        if (!c) {
            setTile("t-rover", "—", "muted");
            setTile("t-raw", "—", "muted");
            setTile("t-time", "—", "muted");
        } else {
            setTile("t-rover", r ? "Running" : "Stopped", r ? "ok" : "muted");
            setTile("t-raw", l ? "Recording" : "Idle", l ? "err" : "muted");
            if (state.timesync === true) setTile("t-time", "Synced", "ok");
            else if (syncing) setTile("t-time", "Syncing…", "warn");
            else setTile("t-time", "Not synced", "warn");
        }
    }

    // ---------- files ----------

    var filesLoading = false;

    function loadFiles() {
        if (filesLoading) return;
        filesLoading = true;
        $("refresh-files").classList.add("is-busy");

        fetch("/api/files", { cache: "no-store" })
            .then(function (r) {
                if (!r.ok) throw new Error("HTTP " + r.status);
                return r.json();
            })
            .then(renderFiles)
            .catch(function (e) { log("Could not load file list: " + e.message, "err"); })
            .then(function () {
                filesLoading = false;
                $("refresh-files").classList.remove("is-busy");
            });
    }

    function renderFiles(data) {
        var list = $("files");
        var files = data.files || [];
        list.textContent = "";

        var total = 0;
        files.forEach(function (f, i) {
            total += f.size;

            var li = document.createElement("li");
            li.className = "file";

            var main = document.createElement("div");
            main.className = "file-main";

            var name = document.createElement("div");
            name.className = "file-name";
            name.textContent = f.name;
            name.title = f.name;
            if (i === 0 && state.logging && /\.ubx$/i.test(f.name)) {
                var badge = document.createElement("span");
                badge.className = "badge";
                badge.setAttribute("data-tone", "err");
                badge.textContent = "REC";
                name.appendChild(badge);
            }

            var meta = document.createElement("div");
            meta.className = "file-meta";
            meta.textContent = formatDate(new Date(f.mtime * 1000));

            main.appendChild(name);
            main.appendChild(meta);

            var size = document.createElement("div");
            size.className = "file-size";
            size.textContent = formatBytes(f.size);

            var dl = document.createElement("a");
            dl.className = "file-dl";
            dl.href = "/download/" + encodeURIComponent(f.name);
            dl.title = "Download " + f.name;
            dl.setAttribute("aria-label", "Download " + f.name);
            dl.setAttribute("download", "");
            dl.innerHTML = '<svg class="icon"><use href="#i-download"/></svg>';

            li.appendChild(main);
            li.appendChild(size);
            li.appendChild(dl);
            list.appendChild(li);
        });

        $("files-empty").hidden = files.length > 0;
        $("files-summary").textContent = files.length
            ? "· " + files.length + " files, " + formatBytes(total)
            : "";

        if (data.disk && data.disk.total) {
            var freePct = data.disk.free / data.disk.total * 100;
            var tone = freePct < 5 ? "err" : freePct < 15 ? "warn" : "ok";
            setTile("t-disk", formatBytes(data.disk.free), tone, 100 - freePct);
            $("t-disk").title = formatBytes(data.disk.free) + " free of " + formatBytes(data.disk.total);
        }
    }

    // ---------- socket ----------

    var socket = io(NAMESPACE);

    function setConnection(tone, label) {
        var pill = $("conn");
        setTone(pill, tone);
        pill.querySelector(".label").textContent = label;
    }

    socket.on("connect", function () {
        state.connected = true;
        setConnection("ok", "Connected");
        log("Connected", "ok");
        render();
        loadFiles();
        poll();
    });

    socket.on("disconnect", function () {
        state.connected = false;
        setBusy(null);
        setConnection("err", "Disconnected");
        log("Disconnected", "err");
        setTile("t-cpu", "—", "muted");
        setTile("t-load", "—", "muted", 0);
        render();
    });

    socket.io.on("reconnect_attempt", function () {
        setConnection("warn", "Reconnecting…");
    });

    socket.on("state", function (running) {
        var changed = state.rover !== !!running;
        state.rover = !!running;
        if (state.busy !== "restart" || !changed || running) setBusy(null);
        else render();
        if (changed) setTimeout(loadFiles, 1000);
    });

    socket.on("str2str", function (recording) {
        var changed = state.logging !== !!recording;
        state.logging = !!recording;
        setBusy(null);
        if (changed) setTimeout(loadFiles, 1000);
    });

    socket.on("timesync", function (synced) {
        state.timesync = synced;
        if (synced !== "pending") setBusy(null);
        else render();
    });

    socket.on("message", function (message) {
        log(String(message));
    });

    socket.on("cpu", function (temp) {
        var tone = temp >= 75 ? "err" : temp >= 65 ? "warn" : "ok";
        setTile("t-cpu", temp.toFixed(1) + " °C", tone);
    });

    socket.on("load", function (load) {
        var tone = load >= 90 ? "err" : load >= 70 ? "warn" : "ok";
        setTile("t-load", load.toFixed(0) + " %", tone, load);
    });

    function poll() {
        if (!state.connected) return;
        socket.emit("cpu");
        socket.emit("load");
    }
    setInterval(poll, 2500);
    setInterval(function () { if (state.connected) loadFiles(); }, 15000);

    // ---------- actions ----------

    ["start", "stop", "restart", "str2str", "sync"].forEach(function (id) {
        $(id).addEventListener("click", function () {
            setBusy(id);
            socket.emit(id);
        });
    });

    var dialog = $("confirm-shutdown");
    $("shutdown").addEventListener("click", function () {
        if (typeof dialog.showModal === "function") {
            dialog.returnValue = "";
            dialog.showModal();
        } else if (window.confirm("Shut down the device?")) {
            shutdown();
        }
    });
    dialog.addEventListener("close", function () {
        if (dialog.returnValue === "ok") shutdown();
    });

    function shutdown() {
        setBusy("shutdown");
        log("Shutdown requested. The device will power off.", "warn");
        socket.emit("shutdown");
    }

    $("clear-log").addEventListener("click", function () {
        $("output").textContent = "";
    });

    $("refresh-files").addEventListener("click", loadFiles);

    render();
})();
