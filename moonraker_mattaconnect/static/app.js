//---------------------------------------------------
// Constants
//---------------------------------------------------

const CAM_PREVIEW_WIDTH = 400;
const IMAGE_PLACEHOLDER = "https://matta-os.fra1.cdn.digitaloceanspaces.com/site-assets/placeholder.png"

const camPreviewContainer = document.getElementById('camPreview');

//---------------------------------------------------
// Crosshair functions
//---------------------------------------------------

function setXY(event) {
        let rect = camPreview.getBoundingClientRect();
        let x = event.clientX - rect.left;
        let y = event.clientY - rect.top;
        self.updateCrosshairPosition(x, y);
    };

self.updateCrosshairPosition = (x, y) => {
    crosshair.style.left = x + 'px';
    crosshair.style.top = y + 'px';
    crosshair.style.display = "block";
    self.calculateAndUpdateNozzleCoords(x, y);
}

self.calculateAndUpdateNozzleCoords = (x, y) => {
    let naturalWidth = camPreview.naturalWidth;
    let naturalHeight = camPreview.naturalHeight;

    let clientWidth = camPreview.clientWidth;
    let clientHeight = camPreview.clientHeight;
    
    let nozzleX = parseInt(x / clientWidth * naturalWidth);
    let nozzleY = parseInt(y / clientHeight * naturalHeight);

    nozzle_tip_coords_x.textContent = nozzleX;
    nozzle_tip_coords_y.textContent = nozzleY;

    self.nozzle_tip_coords_x.textContent = nozzleX;
    self.nozzle_tip_coords_y.textContent = nozzleY;
}

//---------------------------------------------------
// Save function
//---------------------------------------------------


async function saveXY() {
    // Get the coordinates
    let nozzleX = self.nozzle_tip_coords_x.textContent;
    let nozzleY = self.nozzle_tip_coords_y.textContent;

    // Include the coordinates in the data object
    let data = {
        "nozzleX": nozzleX,
        "nozzleY": nozzleY
    }

    let json_data = {
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

    $("#snapBtn").click(async function() {
        $.get("/api/get_snapshot", function(data, status) {
            // Save the current dimensions of the camPreview image
            let currentWidth = camPreview.offsetWidth;
            let currentHeight = camPreview.offsetHeight;
    
            // Set the src of the camPreview image to the new image
            camPreview.src = 'data:image/jpeg;base64,' + data.image;
    
            // Wait for the new image to load before getting its natural dimensions
            camPreview.onload = function() {
                // Get the natural dimensions of the new image
                let naturalWidth = camPreview.naturalWidth;
                let naturalHeight = camPreview.naturalHeight;
    
                // Calculate the scaling factor
                let scaleFactorWidth = currentWidth / naturalWidth;
                let scaleFactorHeight = currentHeight / naturalHeight;
    
                // Set the dimensions of the new image to the saved dimensions
                camPreview.style.width = currentWidth + "px";
                camPreview.style.height = currentHeight + "px";
            }
        });
    });

    // $("#homePrinterButton").click(function() {
    //     $.post("/api/home_printer", function(data, status) {
    //         // Create a new paragraph element to display the result
    //         var resultParagraph = $("<p>").text("Printer homing triggered: " + status + data);
    //         // Append the paragraph to a container element
    //         $("#resultContainer").empty().append(resultParagraph);
    //     });
    // });
    // $("#getPrinterStateButton").click(function() {
    //     $.get("/api/get_printer_state", function(data, status) {
    //         var resultParagraph = $("<p>").text("Printer state: " + data);
    //         $("#resultContainer").empty().append(resultParagraph);
    //     });
    // });
    
    // $("#getTempsButton").click(function() {
    //     $.get("/api/get_temps", function(data, status) {
    //         var parametersText = JSON.stringify(data, null, 2); // Convert JSON to formatted text
    //         var resultParagraph = $("<p>").text("Printer temps:\n" + parametersText);
    //         $("#resultContainer").empty().append(resultParagraph);
    //     });
    // });

    // $("#testAuthTokenButton").click(async function() {
    //     await saveAll();
    //     await $.get("/api/test_auth_token", function(data, status) {
    //         var resultParagraph = $("<p>").text(data);
    //         $("#resultContainer").empty().append(resultParagraph);
    //     });
    // });
});

document.addEventListener('DOMContentLoaded', function() {

const saveButton = document.getElementById('saveAllBtn');
saveButton.addEventListener('click', saveXY);

const camPreviewContainer = document.getElementById('camPreview');
camPreviewContainer.addEventListener('click', setXY);


});