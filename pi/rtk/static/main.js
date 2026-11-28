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
        profiles: [],      // [{file, name}]
        profile: null,     // selected profile file
        profileSaving: false,
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
        if (/fail|error|unexpected|not synced|disconnected/.test(t)) return "err";
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

        // receiver profile
        var sel = $("profile");
        sel.disabled = !c || r || b || state.profileSaving || state.profiles.length < 2;
        $("profile-hint").textContent = !c ? "" : r ? "Stop the rover to change" : "";

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

        renderPosition();
    }

    // ---------- files ----------

    var filesLoading = false;
    var filesReloadPending = false;   // asked again while loading: reload once done
    var deletable = { count: 0, size: 0 };   // files "Delete all" would remove

    function loadFiles() {
        if (filesLoading) { filesReloadPending = true; return; }
        filesLoading = true;
        filesReloadPending = false;
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
                if (filesReloadPending) loadFiles();
            });
    }

    function renderFiles(data) {
        var list = $("files");
        var files = data.files || [];
        list.textContent = "";

        var total = 0;
        deletable = { count: 0, size: 0 };
        files.forEach(function (f) {
            total += f.size;
            if (!f.in_use) { deletable.count++; deletable.size += f.size; }

            var li = document.createElement("li");
            li.className = "file";

            var main = document.createElement("div");
            main.className = "file-main";

            var name = document.createElement("div");
            name.className = "file-name";
            name.textContent = f.name;
            name.title = f.name;
            if (f.in_use) {
                var rec = state.logging && /\.ubx$/i.test(f.name);
                var badge = document.createElement("span");
                badge.className = "badge";
                badge.setAttribute("data-tone", rec ? "err" : "muted");
                badge.textContent = rec ? "REC" : "IN USE";
                badge.title = "Open by a running process, so it can't be deleted";
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

            var del = document.createElement("button");
            del.className = "file-del";
            del.disabled = f.in_use;
            del.title = f.in_use ? "In use, can't be deleted" : "Delete " + f.name;
            del.setAttribute("aria-label", "Delete " + f.name);
            del.innerHTML = '<svg class="icon"><use href="#i-trash"/></svg>';
            del.addEventListener("click", function () {
                confirmDelete("Delete " + f.name + "?",
                    formatBytes(f.size) + ", " + formatDate(new Date(f.mtime * 1000)) + ". This can't be undone.",
                    "Delete",
                    function () {
                        li.classList.add("is-deleting");
                        deleteFiles("/api/files/" + encodeURIComponent(f.name));
                    });
            });

            li.appendChild(main);
            li.appendChild(size);
            li.appendChild(dl);
            li.appendChild(del);
            list.appendChild(li);
        });

        $("delete-all").disabled = deletable.count === 0;
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

    // ---------- position ----------

    var SOLUTION_STALE_MS = 6000;
    var QUALITY_TONE = { FIX: "ok", FLOAT: "warn", DGPS: "accent", SBAS: "accent", PPP: "accent", SINGLE: "err" };

    var pos = {
        sol: null,          // last solution
        at: 0,              // when it arrived (client clock)
        follow: true,       // keep the map centred on the rover
        lastPoint: 0,       // when the last track point was added
        roverSince: 0,      // when the rover was seen starting
        tilesFailed: false
    };

    function toneColor(tone) {
        return getComputedStyle(document.documentElement).getPropertyValue("--" + tone).trim() || "#888";
    }
    function qualityTone(q) { return QUALITY_TONE[q] || "err"; }

    function fmtNum(v, digits, unit) {
        return v === null || v === undefined ? "—" : v.toFixed(digits) + (unit || "");
    }

    function accuracyText(s) {
        if (s.hacc !== null && s.hacc !== undefined) return "±" + fmtNum(s.hacc, s.hacc < 0.1 ? 3 : 2, " m");
        if (s.hdop !== null && s.hdop !== undefined) return "HDOP " + s.hdop.toFixed(1);
        return "";
    }

    // map (Leaflet may be missing if the file failed to load: then no map, stats still work)
    var map = null, trackLayer = null, here = null, accCircle = null;

    function initMap() {
        if (!window.L) { mapNote("Map library failed to load"); return; }

        map = L.map("map", { preferCanvas: true, zoomControl: true, worldCopyJump: true })
            .setView([20, 0], 2);
        L.control.scale({ imperial: false }).addTo(map);

        // tiles come from the internet through the phone, not the Pi
        var tiles = L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
            maxNativeZoom: 19,
            maxZoom: 22,
            attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
        }).addTo(map);
        tiles.on("tileerror", function () {
            if (!pos.tilesFailed) { pos.tilesFailed = true; renderPosition(); }
        });
        tiles.on("tileload", function () {
            if (pos.tilesFailed) { pos.tilesFailed = false; renderPosition(); }
        });

        trackLayer = L.layerGroup().addTo(map);

        // panning by hand stops following until the button is pressed again
        map.on("dragstart", function () { setFollow(false); });
    }

    function mapNote(text) {
        var note = $("map-note");
        note.hidden = !text;
        note.textContent = text || "";
    }

    function addTrackPoint(lat, lon, quality) {
        if (!trackLayer) return;
        L.circleMarker([lat, lon], {
            radius: 4,
            weight: 1,
            color: "rgba(0, 0, 0, .35)",
            fillOpacity: 0.95,
            fillColor: toneColor(qualityTone(quality)),
            interactive: false
        }).addTo(trackLayer);
    }

    function setTrack(points) {
        if (!trackLayer) return;
        trackLayer.clearLayers();
        var qname = { 1: "FIX", 2: "FLOAT", 3: "SBAS", 4: "DGPS", 5: "SINGLE", 6: "PPP" };
        points.forEach(function (p) { addTrackPoint(p[0], p[1], qname[p[2]] || "SINGLE"); });
        if (here) here.bringToFront();
        renderPosition();
    }

    function setFollow(on) {
        pos.follow = on;
        $("map-follow").setAttribute("aria-pressed", on ? "true" : "false");
        if (on && map && pos.sol) map.setView([pos.sol.lat, pos.sol.lon], Math.max(map.getZoom(), 17));
    }

    function onSolution(s) {
        if (!s) {
            pos.sol = null;
            renderPosition();
            return;
        }
        var first = !pos.sol;
        pos.sol = s;
        pos.at = Date.now();

        if (map) {
            var ll = [s.lat, s.lon];
            var color = toneColor(qualityTone(s.quality));
            if (!here) {
                accCircle = L.circle(ll, { radius: 0, weight: 1, fillOpacity: 0.12, interactive: false }).addTo(map);
                here = L.circleMarker(ll, { radius: 7, weight: 2, color: "#fff", fillOpacity: 1, interactive: false }).addTo(map);
            }
            here.setLatLng(ll).setStyle({ fillColor: color });
            accCircle.setLatLng(ll).setRadius(s.hacc || 0).setStyle({ color: color, fillColor: color });

            // same rate as the server's track: one point per second
            if (pos.at - pos.lastPoint >= 1000) {
                addTrackPoint(s.lat, s.lon, s.quality);
                pos.lastPoint = pos.at;
                here.bringToFront();
            }
            if (first && pos.follow) map.setView(ll, 18);
            else if (pos.follow) map.panTo(ll, { animate: false });
        }
        renderPosition();
    }

    function renderPosition() {
        var s = pos.sol;
        var fresh = s && Date.now() - pos.at < SOLUTION_STALE_MS;

        // tile
        if (!state.connected) setTile("t-sol", "—", "muted");
        else if (fresh) setTile("t-sol", s.quality, qualityTone(s.quality));
        else if (state.rover) setTile("t-sol", s ? "Lost" : "Waiting…", s ? "err" : "warn");
        else setTile("t-sol", "Off", "muted");
        $("t-sol").querySelector(".tile-sub").textContent =
            fresh ? s.ns + " sats" + (accuracyText(s) ? " · " + accuracyText(s) : "") : "\u00a0";

        // stats
        $("p-lat").textContent = s ? s.lat.toFixed(8) + "°" : "—";
        $("p-lon").textContent = s ? s.lon.toFixed(8) + "°" : "—";
        $("p-h").textContent = s ? fmtNum(s.h, 3, " m") : "—";
        if (s && s.hacc !== null && s.hacc !== undefined) {
            // 1-sigma: horizontal from north and east, vertical from up
            $("p-acc-label").textContent = "Accuracy H / V";
            $("p-acc").textContent = "±" + fmtNum(s.hacc, 3) + " / ±" + fmtNum(s.sdu, 3) + " m";
            $("p-acc").title = "1σ north " + fmtNum(s.sdn, 3) + " m, east " + fmtNum(s.sde, 3) + " m, up " + fmtNum(s.sdu, 3) + " m";
        } else {
            $("p-acc-label").textContent = "HDOP";
            $("p-acc").textContent = s ? fmtNum(s.hdop, 1) : "—";
        }
        $("p-ns").textContent = s ? String(s.ns) : "—";
        $("p-age").textContent = s ? fmtNum(s.age, 1, " s") + " · " + fmtNum(s.ratio, 1) : "—";
        $("pos-stats").classList.toggle("is-stale", !!s && !fresh);
        $("pos-summary").textContent = s ? "· " + s.quality + (fresh ? "" : " (last)") : "";

        // note over the map
        if (!state.connected) mapNote("");
        else if (!state.rover && !s) mapNote("Start the rover to see its position");
        else if (state.rover && !fresh) {
            var waited = Date.now() - pos.roverSince > 30000;
            mapNote(s ? "No solution for a few seconds"
                : waited ? "No solution yet. RTK modes need corrections from the base: check that NTRIP data is arriving."
                : "Waiting for the first solution…");
        }
        else if (pos.tilesFailed) mapNote("Map tiles need internet on this device. The track is drawn on a grid.");
        else mapNote("");
    }

    setInterval(renderPosition, 1000);   // notices a solution going stale

    $("map-follow").addEventListener("click", function () { setFollow(!pos.follow); });
    $("map-clear").addEventListener("click", function () {
        if (state.connected) socket.emit("clear_track");
    });

    // ---------- deleting ----------

    var deleteDialog = $("confirm-delete");
    var onDeleteConfirmed = null;

    function confirmDelete(title, text, okLabel, onOk) {
        if (typeof deleteDialog.showModal !== "function") {
            if (window.confirm(title + "\n\n" + text)) onOk();
            return;
        }
        $("confirm-delete-title").textContent = title;
        $("confirm-delete-text").textContent = text;
        $("confirm-delete-ok").textContent = okLabel;
        onDeleteConfirmed = onOk;
        deleteDialog.returnValue = "";
        deleteDialog.showModal();
    }

    deleteDialog.addEventListener("close", function () {
        var fn = onDeleteConfirmed;
        onDeleteConfirmed = null;
        if (deleteDialog.returnValue === "ok" && fn) fn();
    });

    function deleteFiles(url) {
        fetch(url, { method: "DELETE" })
            .then(function (r) {
                return r.json().catch(function () { return {}; }).then(function (data) {
                    // success is reported by the server in Messages, to every panel
                    if (!r.ok) log(data.error || "Delete failed: HTTP " + r.status, "err");
                });
            })
            .catch(function (e) { log("Delete failed: " + e.message, "err"); })
            .then(loadFiles);
    }

    $("delete-all").addEventListener("click", function () {
        var n = deletable.count;
        confirmDelete("Delete all log files?",
            n + (n === 1 ? " file, " : " files, ") + formatBytes(deletable.size) +
            ". Files in use (the running recording, the rover's logs, the server's current log) are kept. This can't be undone.",
            "Delete " + n + (n === 1 ? " file" : " files"),
            function () { deleteFiles("/api/files"); });
    });

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
        if (running && (changed || !pos.roverSince)) pos.roverSince = Date.now();
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

    socket.on("profiles", function (data) {
        state.profiles = data.profiles || [];
        state.profile = data.selected;
        state.profileSaving = false;

        var sel = $("profile");
        sel.textContent = "";
        state.profiles.forEach(function (p) {
            var opt = document.createElement("option");
            opt.value = p.file;
            opt.textContent = p.name;
            sel.appendChild(opt);
        });
        if (!state.profiles.length) {
            var none = document.createElement("option");
            none.textContent = "No profiles found";
            sel.appendChild(none);
        }
        sel.value = state.profile;
        render();
    });

    socket.on("files", function () { loadFiles(); });

    socket.on("solution", onSolution);

    socket.on("track", function (points) {
        pos.lastPoint = Date.now();   // the server's track is current up to now
        setTrack(points || []);
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

    $("profile").addEventListener("change", function (e) {
        state.profileSaving = true;
        render();
        socket.emit("profile", e.target.value);
    });

    $("clear-log").addEventListener("click", function () {
        $("output").textContent = "";
    });

    $("refresh-files").addEventListener("click", loadFiles);

    initMap();
    render();
})();
