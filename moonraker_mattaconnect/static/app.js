async function saveAll() {
    terminalCmds_value = $("#terminalCmds").val();
    // create a list of commands from input separated by newlines
    terminalCmds_value = terminalCmds_value.split("\n");
    data = {
        "authToken": $("#authToken").val(),
        "terminalCmds": terminalCmds_value,
    }
    json_data = {
        'method': 'POST',
        'url': '/api/save_values',
        'headers': {
            'Content-Type': 'application/json'
        },
        'data': JSON.stringify(data),
    }
    await $.ajax(json_data).done(function(data, status) {
        var resultParagraph = $("<p>").text(data);
        $("#resultContainer").empty().append(resultParagraph);
        return data, status;
    })
};

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

    $("#testAuthTokenButton").click(async function() {
        await saveAll();
        await $.get("/api/test_auth_token", function(data, status) {
            var resultParagraph = $("<p>").text(data);
            $("#resultContainer").empty().append(resultParagraph);
        });
    });

    $("#saveAllBtn").click(saveAll);

    function writeValues(data, status) {
        terminalCmds_value = data.terminalCmds.join("\n");
        authToken.value = data.authToken;
        terminalCmds.value = terminalCmds_value;
    };

    function loadDefaultValues() {
        $.get("/api/get_values", writeValues);
    };

    loadDefaultValues();
});

document.addEventListener('DOMContentLoaded', function() {

// const form = document.getElementById('container');

const saveButton = document.getElementById('saveAllBtn');

// Attach event listeners
saveButton.addEventListener('click', saveAll);

});