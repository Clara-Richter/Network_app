from flask import Flask, request, jsonify, render_template
from pyngrok import ngrok
import pandas as pd
from pyvis.network import Network
import json
import html
from uuid import uuid4

app = Flask(__name__)

def validate_excel(df, required_columns):
    """Validate that the Excel sheet contains required columns."""
    missing_cols = [col for col in required_columns if col not in df.columns]
    if missing_cols:
        return False, f"Missing columns: {', '.join(missing_cols)}"
    return True, None

def save_graph_with_legend(net, filename, legend_html):
    """Save the network graph with custom CSS and legend."""
    custom_css = """
    <style>
        .vis-tooltip {
            max-width: 300px;
            white-space: pre-wrap;
            font-family: Arial, sans-serif;
            font-size: 14px;
        }
        .legend {
            position: absolute;
            top: 20px;
            left: 1%;
            background-color: rgba(255, 255, 255, 0.8);
            border: 1px solid #999;
            padding: 8px;
            font-family: Arial, sans-serif;
            font-size: 14px;
        }
        .legend-item {
            margin-bottom: 5px;
        }
        .legend-color {
            display: inline-block;
            width: 10px;
            height: 10px;
            margin-right: 5px;
            border: 1px solid #999;
        }
    </style>
    """
    net.save_graph(filename)
    with open(filename, "w") as f:
        f.write("<html>\n")
        f.write(custom_css)
        f.write(net.html)
        f.write(legend_html)
        f.write("</html>")
    with open(filename, "r") as f:
        return f.read()

@app.route('/')
def index():
    """Render the main page."""
    return render_template('index.html')

@app.route('/generate-graph', methods=['POST'])
def generate_graph():
    """Generate a network graph based on the selected Excel sheet."""
    if 'file' not in request.files:
        return jsonify({"error": "No file uploaded"}), 400
    
    file = request.files['file']
    sheet_name = request.form.get('sheet_name')
    search_term = html.escape(request.form.get('search_term', ''))

    try:
        df = pd.read_excel(file, sheet_name=sheet_name, header=0)
    except Exception as e:
        return jsonify({"error": f"Failed to read Excel sheet '{sheet_name}': {str(e)}"}), 400
    
    # Validate required columns (adjust based on your data structure)
    required_cols = ['Node', 'Status', 'Details']  # Assuming generic columns; adjust as needed
    valid, error = validate_excel(df, required_cols)
    if not valid:
        return jsonify({"error": error}), 400

    # Initialize network
    net = Network(height="590px", width="100%", notebook=True, cdn_resources='remote')
    
    # Add nodes
    nodes = df['Node'].unique()
    for node in nodes:
        color = 'grey'  # Default for parent nodes
        net.add_node(node, color=color)

    # Add child nodes and edges
    for _, row in df.iterrows():
        node_id = f"{row['Node']} - {row['Details']}"
        title = row['Details'] if pd.notnull(row['Details']) else "No details"
        color = {'Green': 'green', 'Yellow': 'yellow', 'Red': 'red'}.get(row['Status'], 'white')
        net.add_node(node_id, color=color, label=str(row['Details']), title=title)
        net.add_edge(row['Node'], node_id)

    # Handle search term (highlight matching nodes)
    if search_term:
        df['Details'] = df['Details'].fillna('')
        net.add_node(search_term, color="purple", label="Search: " + search_term)
        matching_nodes = []
        for node in net.nodes:
            if 'title' in node and search_term.lower() in node['title'].lower():
                matching_nodes.append(node['id'])
        for node_id in matching_nodes:
            net.add_edge(node_id, search_term, color="black")

    # Add a central node (e.g., "Network Core")
    central_node = "Network Core"
    net.add_node(central_node, color="blue", label=central_node)
    for node in nodes:
        net.add_edge(node, central_node, color="grey")

    # Set physics options
    net.set_options(json.dumps({
        "physics": {
            "barnesHut": {"centralGravity": 0},
            "minVelocity": 0.75
        }
    }))

    # Define legend
    legend_html = """
    <div class="legend">
        <div class="legend-item"><div class="legend-color" style="background-color: green;"></div>On Track</div>
        <div class="legend-item"><div class="legend-color" style="background-color: yellow;"></div>Issues</div>
        <div class="legend-item"><div class="legend-color" style="background-color: red;"></div>Critical Issues</div>
    </div>
    """

    # Save and return graph
    filename = f"static/graph_{uuid4().hex}.html"
    graph_html = save_graph_with_legend(net, filename, legend_html)
    return graph_html

if __name__ == '__main__':
    public_url = ngrok.connect(5000)
    print(f"Public URL: {public_url}")
    app.run(port=5000)
