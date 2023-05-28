$(function () {
    $(".logo-wrapper").load("../../logo.html", complete = function () {
        $(".logo").hide().fadeIn(1500);
    });
});