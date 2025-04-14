// script.js
function generateGraph() {
    // Send AJAX request to Python backend
    var xhr = new XMLHttpRequest();
    xhr.open("GET", "/generate-graph", true);
    xhr.onreadystatechange = function () {
        if (xhr.readyState == 4 && xhr.status == 200) {
            // Retrieve graph data from response
            var graphData = JSON.parse(xhr.responseText);

            // Update graph container with the new graph
            document.getElementById("graphContainer").innerHTML = graphData;
        }
    };
    xhr.send();
}




