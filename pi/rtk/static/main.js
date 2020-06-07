$(document).ready(function () {
    namespace = "/test";

    socket = io.connect("http://" + document.domain + ":" + location.port + namespace);

    socket.on("connect", function () {
        $("#start").prop('disabled', true);
        $("#stop").prop('disabled', true);
        $("#output").append('<p class="m-0 p-0 text-success">Connected</p>');
    });

    socket.on('disconnect', function () {
        $("#start").prop('disabled', true);
        $("#stop").prop('disabled', true);
        $("#output").append('<p class="m-0 p-0 text-danger">Disconnected</p>');
    });

    socket.on('state', function (state) {
        if (state) {
            $("#start").prop('disabled', true);
            $("#stop").prop('disabled', false);
        } else {
            $("#start").prop('disabled', false);
            $("#stop").prop('disabled', true);
        }
    });

    socket.on("message", function (message) {
        $("#output")
            .append('<p class="m-0 p-0 text-info">' + message + '</p>')
            .stop()
            .animate({
                scrollTop: $('#output')[0].scrollHeight,
            });
    });

    $("#sync").click(function () {
        socket.emit("sync");
    });

    $("#start").click(function () {
        socket.emit("start");
    });

    $("#stop").click(function () {
        socket.emit("stop");
    });

    $("#restart").click(function () {
        socket.emit("restart");
    });

    $("#shutdown").click(function () {
        socket.emit("shutdown");
    });
});