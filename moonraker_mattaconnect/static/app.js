$(document).ready(function() {
    $("#homePrinterButton").click(function() {
        $.post("/api/home_printer", function(data, status) {
            // Create a new paragraph element to display the result
            var resultParagraph = $("<p>").text("Printer homing triggered: " + status + data);
            // Append the paragraph to a container element
            $("#resultContainer").empty().append(resultParagraph);
        });
    });
    $("#getPrinterStateButton").click(function() {
        $.get("/api/get_printer_state", function(data, status) {
            var resultParagraph = $("<p>").text("Printer state: " + data);
            $("#resultContainer").empty().append(resultParagraph);
        });
    });
    
    $("#getTempsButton").click(function() {
        $.get("/api/get_temps", function(data, status) {
            var parametersText = JSON.stringify(data, null, 2); // Convert JSON to formatted text
            var resultParagraph = $("<p>").text("Printer temps:\n" + parametersText);
            $("#resultContainer").empty().append(resultParagraph);
        });
    });

    $("#testAuthTokenButton").click(function() {
        $.get("/api/test_auth_token", function(data, status) {
            var resultParagraph = $("<p>").text(data);
            $("#resultContainer").empty().append(resultParagraph);
        });
    });




});
