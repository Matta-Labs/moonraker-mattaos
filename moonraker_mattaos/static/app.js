//---------------------------------------------------
// Constants
//---------------------------------------------------

const IMAGE_PLACEHOLDER = "https://matta-os.fra1.cdn.digitaloceanspaces.com/site-assets/placeholder.png"

//---------------------------------------------------
// Crosshair functions
//---------------------------------------------------

function setXY(event) {
    $.get("/api/get_settings", function(data) {
        let rect = camPreview.getBoundingClientRect();
        rotate = data['rotate'];

        if (rotate == true) {
            let aspectRatio = camPreview.offsetHeight / camPreview.offsetWidth;
            const CAM_PREVIEW_WIDTH = camPreview.offsetWidth;
            let width = CAM_PREVIEW_WIDTH;
            let height = CAM_PREVIEW_WIDTH * aspectRatio;
            let difference = Math.abs(width - height) / 2;
            let x = event.clientX - rect.left + difference;
            let y = event.clientY - rect.top;
            self.updateCrosshairPosition(x, y);
            return
        }
        let x = event.clientX - rect.left;
        let y = event.clientY - rect.top;
        self.updateCrosshairPosition(x, y);
    });
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

    let nozzleX;
    
    if (rotate == true) {
        let aspectRatio = camPreview.offsetHeight / camPreview.offsetWidth;
        const CAM_PREVIEW_WIDTH = camPreview.offsetWidth;
        let width = CAM_PREVIEW_WIDTH;
        let height = CAM_PREVIEW_WIDTH * aspectRatio;
        let difference = Math.abs(width - height) / 2;
        nozzleX = parseInt((x - difference) / clientWidth * naturalWidth);
    } else {
        nozzleX = parseInt(x / clientWidth * naturalWidth);
    }
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
    
    $.get("/api/get_settings", function(data) {
        let flip_h = data['flip_h'];
        let flip_v = data['flip_v'];
        let rotate = data['rotate'];
    });

    $("#snapBtn").click(async function() {
        $("#snapBtn").prop('disabled', true);
        $.get("/api/get_snapshot", function(data, status) {
            // Save the current dimensions of the camPreview image
            // let currentWidth = camPreview.offsetWidth;
            // let currentHeight = camPreview.offsetHeight;
            const image = data.image;

            let camPreview = document.getElementById('camPreview');
            const CAM_PREVIEW_WIDTH = camPreview.offsetWidth;
            const CAM_PREVIEW_HEIGHT = camPreview.offsetHeight;

            $.get("/api/get_settings", function(data) {
                let flip_h = data['flip_h'];
                let flip_v = data['flip_v'];
                let rotate = data['rotate'];
                
                // Create a CSS transform string based on the settings
                let transform = '';
                if (flip_h == true) {
                    transform += 'scaleX(-1) ';
                }
                if (flip_v == true) {
                    transform += 'scaleY(-1) ';
                }
                if (rotate == true) {

                    transform += 'rotate(-90deg)';
                    let camPreview = document.getElementById('camPreview');
                    camPreview.src = 'data:image/jpeg;base64,' + image;
                    camPreview.onload = function() {
                        let aspectRatio = camPreview.offsetHeight / camPreview.offsetWidth;
                        let width = CAM_PREVIEW_WIDTH;
                        let height = CAM_PREVIEW_WIDTH * aspectRatio;
                        let difference = Math.abs(width - height) / 2;                        
                        camPreviewContainer.style.width = CAM_PREVIEW_WIDTH + "px";
                        camPreviewContainer.style.height = width + "px";
                        camPreviewContainer.style.backgroundColor = "black";
                        // round the corners of the container
                        camPreviewContainer.style.borderRadius = "1%";
                        camPreview.style.width = width + "px";
                        camPreview.style.height = height + "px";
                        camPreview.style.maxWidth = width + "px";
                        camPreview.style.maxHeight = height + "px";
                        camPreview.style.position = 'absolute';
                        camPreview.style.top = difference + "px";
                        $('#camPreview').css('transform', transform);
                    }
                } else {
                    let camPreview = document.getElementById('camPreview');
                    camPreview.src = 'data:image/jpeg;base64,' + image;
                    camPreview.onload = function() {
                        let aspectRatio = camPreview.offsetHeight / camPreview.offsetWidth;
                        let width = CAM_PREVIEW_WIDTH;
                        let height = CAM_PREVIEW_WIDTH * aspectRatio;
                        camPreviewContainer.style.width = width + "px";
                        camPreviewContainer.style.height = height + "px";
                        camPreviewContainer.style.marginBottom = "36px";
                        camPreviewContainer.style.backgroundColor = "black";
                        camPreview.style.width = width + "px";
                        camPreview.style.height = height + "px";
                        camPreview.style.maxWidth = width + "px";
                        camPreview.style.maxHeight = height + "px";
                        $('#camPreview').css('transform', transform);
                    }

                }
            });
        });
    });
});

document.addEventListener('DOMContentLoaded', function() {

const saveButton = document.getElementById('saveAllBtn');
saveButton.addEventListener('click', saveXY);

const camPreviewContainer = document.getElementById('camPreviewContainer');
camPreviewContainer.addEventListener('click', setXY);


});