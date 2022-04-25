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

    socket.on('str2str', function (state) {
        if (state) {
            $("#sync").prop('disabled', true);
            $("#start").prop('disabled', true);
            $("#stop").prop('disabled', true);
	    $("#restart").prop('disabled', true);
            $("#shutdown").prop('disabled', true);
        } else {
            $("#sync").prop('disabled', false);
            $("#start").prop('disabled', false);
            $("#stop").prop('disabled', false);
	    $("#restart").prop('disabled', false);
            $("#shutdown").prop('disabled', false);
        }
    });

    socket.on('state', function (state) {
        if (state) {
            $("#str2str").prop('disabled', true);
            $("#sync").prop('disabled', true);
            $("#start").prop('disabled', true);
            $("#stop").prop('disabled', false);
        } else {
            $("#str2str").prop('disabled', false);
            $("#sync").prop('disabled', false);
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

    $("#str2str").click(function () {
        socket.emit("str2str");
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

    $(function () {
	$('[data-toggle="tooltip"]').tooltip();
    });
});
